"""KOSPI 펀더멘털 — OpenDART(전자공시). 미국판 09_fetch_fundamentals_edgar 의 국내 버전.

유니버스(kr_01 산출) 각 종목의 분기 재무제표에서 추출:
  - ppent  = 유형자산        (BS)
  - cash   = 현금및현금성자산 (BS)
  - assets = 자산총계         (BS)
  - cashflow_op = 영업활동현금흐름 (CF)
  - shares = 현재 발행주식수 (FDR, cap 계산용 — 분기별 동일값 근사)
섹터(업종) = company.json 의 induty_code → kospi_sectors.csv
출력: data/kospi_fundamentals.parquet  (index=(symbol, quarter_end))
"""
import io
import os
import sys
import time
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import requests
import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
load_dotenv(ROOT / ".env")
KEY = os.environ["OPENDART_API_KEY"]
BASE = "https://opendart.fss.or.kr/api"

# (bsns_year, reprt_code) → (분기말 월, 일, 공시지연일)
REPORTS = [
    ("2023", "11011", 12, 31, 90),
    ("2024", "11013", 3, 31, 45), ("2024", "11012", 6, 30, 45),
    ("2024", "11014", 9, 30, 45), ("2024", "11011", 12, 31, 90),
    ("2025", "11013", 3, 31, 45), ("2025", "11012", 6, 30, 45),
    ("2025", "11014", 9, 30, 45), ("2025", "11011", 12, 31, 90),
    ("2026", "11013", 3, 31, 45),
]
# IFRS 표준 account_id 우선 매칭 (회사별 계정명 표기차 흡수 → robust)
WANT_ID = {
    "ifrs-full_PropertyPlantAndEquipment": ("ppent", "BS"),
    "ifrs-full_CashAndCashEquivalents": ("cash", "BS"),
    "ifrs-full_Assets": ("assets", "BS"),
    "ifrs-full_CashFlowsFromUsedInOperatingActivities": ("cashflow_op", "CF"),
}
# account_nm(공백제거) 보강 — account_id 표준코드 미사용 회사 대비
WANT_NM = {
    "유형자산": ("ppent", "BS"),
    "현금및현금성자산": ("cash", "BS"),
    "자산총계": ("assets", "BS"),
    "영업활동현금흐름": ("cashflow_op", "CF"),
    "영업활동으로인한현금흐름": ("cashflow_op", "CF"),
    "영업활동순현금흐름": ("cashflow_op", "CF"),
    "영업활동으로부터의현금흐름": ("cashflow_op", "CF"),
}


def corp_code_map(sess):
    r = sess.get(f"{BASE}/corpCode.xml", params={"crtfc_key": KEY}, timeout=60)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    root = ET.fromstring(z.read(z.namelist()[0]))
    m = {}
    for el in root.iter("list"):
        sc = (el.findtext("stock_code") or "").strip()
        cc = (el.findtext("corp_code") or "").strip()
        if sc and len(sc) == 6 and cc:
            m[sc] = cc
    return m


def _num(s):
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def fetch_statement(sess, corp, year, reprt):
    """fnlttSinglAcntAll: CFS(연결) 우선, 없으면 OFS(별도). {필드:값} 반환."""
    for fs in ("CFS", "OFS"):
        try:
            r = sess.get(f"{BASE}/fnlttSinglAcntAll.json", params={
                "crtfc_key": KEY, "corp_code": corp, "bsns_year": year,
                "reprt_code": reprt, "fs_div": fs}, timeout=20).json()
        except Exception:
            continue
        if r.get("status") != "000":
            continue
        items = r.get("list", [])
        out = {}
        # 1) IFRS 표준 account_id 우선
        for it in items:
            aid = (it.get("account_id") or "").strip()
            if aid in WANT_ID:
                field, sj = WANT_ID[aid]
                if (it.get("sj_div") or "") == sj and field not in out:
                    v = _num(it.get("thstrm_amount"))
                    if v is not None:
                        out[field] = v
        # 2) account_nm 보강 (표준코드 미사용분)
        for it in items:
            nm = (it.get("account_nm") or "").replace(" ", "")
            if nm in WANT_NM:
                field, sj = WANT_NM[nm]
                if (it.get("sj_div") or "") == sj and field not in out:
                    v = _num(it.get("thstrm_amount"))
                    if v is not None:
                        out[field] = v
        if out:
            return out
    return {}


def fetch_sector(sess, corp):
    try:
        r = sess.get(f"{BASE}/company.json", params={"crtfc_key": KEY, "corp_code": corp}, timeout=15).json()
        if r.get("status") == "000":
            ind = (r.get("induty_code") or "").strip()
            return ind[:2] if ind else "기타"   # KSIC 2자리(중분류) → 적당한 업종 그룹
    except Exception:
        pass
    return "기타"


def main():
    uni = pd.read_csv(DATA / "kospi_universe.csv", dtype={"Symbol": str})
    uni["Symbol"] = uni["Symbol"].str.zfill(6)
    shares_map = dict(zip(uni["Symbol"], uni["Stocks"]))
    syms = list(uni["Symbol"])
    sess = requests.Session()

    print(f"[1/3] corpCode 매핑...")
    cmap = corp_code_map(sess)
    resolved = {s: cmap[s] for s in syms if s in cmap}
    print(f"   {len(resolved)}/{len(syms)} 매핑됨")

    print(f"[2/3] 재무제표 + 업종 수집 ({len(resolved)}종목 × {len(REPORTS)}리포트)...")
    rows, sectors = [], {}
    t0 = time.time()
    for i, (sym, corp) in enumerate(resolved.items()):
        sectors[sym] = fetch_sector(sess, corp)
        for (year, reprt, mm, dd, lag) in REPORTS:
            vals = fetch_statement(sess, corp, year, reprt)
            if not vals:
                continue
            qe = pd.Timestamp(f"{year}-{mm:02d}-{dd:02d}")
            rows.append({
                "symbol": sym, "quarter_end": qe,
                "announcement_date": qe + pd.Timedelta(days=lag),
                "shares": shares_map.get(sym), **vals,
            })
        if (i + 1) % 25 == 0:
            print(f"    {i+1}/{len(resolved)} ({time.time()-t0:.0f}s, rows={len(rows)})")

    fund = pd.DataFrame(rows)
    for c in ("ppent", "cash", "assets", "cashflow_op", "shares"):
        if c not in fund.columns:
            fund[c] = pd.NA
    fund = fund.set_index(["symbol", "quarter_end"]).sort_index()
    fund.to_parquet(DATA / "kospi_fundamentals.parquet")
    pd.DataFrame(sorted(sectors.items()), columns=["Symbol", "Sector"]).to_csv(
        DATA / "kospi_sectors.csv", index=False, encoding="utf-8-sig")

    print(f"[3/3] 저장 완료. rows={len(fund)}, 종목={fund.index.get_level_values('symbol').nunique()}")
    print("   필드 커버리지(non-null %):")
    for c in ("ppent", "cash", "assets", "cashflow_op", "shares"):
        print(f"     {c:12s}: {100*fund[c].notna().mean():.0f}%")
    print(f"   업종 그룹 수: {len(set(sectors.values()))}")


if __name__ == "__main__":
    main()
