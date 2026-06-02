"""S&P 500 union 유니버스의 분기 펀더멘털을 SEC EDGAR 에서 전체 재생성.

배경:
  - yfinance quarterly 는 최근 ~5분기만 줘서 백테스트(2023~) 초반이 비어 있었다.
  - SEC EDGAR companyfacts API 는 무료이고 전체 이력을 제공한다.
  - 기존 sp500_fundamentals.parquet 과 *동일한 스키마* 로 통째로 다시 만든다.
    (alpha_eval._build_pit_fundamentals 는 수정 불필요)

데이터 소스:
  https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json
  - instant 개념(재무상태표): 분기말 스냅샷 그대로
  - duration 개념(손익/현금흐름): 3개월(분기) 기간 값만 추출,
    Q4 는 연간 - (Q1+Q2+Q3) 으로 도출
  - announcement_date = 'filed' (실제 공시일) → PIT 정확도 ↑

CIK: 현재 CSV(CIK 컬럼) + SEC company_tickers.json + 수동 override
"""

import sys
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import pandas as pd

from lib.sp500_universe import load_data, get_sp500_members_at

ROOT = Path(__file__).parent.parent
OUTPUT_FILE = ROOT / "data" / "sp500_fundamentals.parquet"
START_DATE = "2023-01-01"           # 백테스트 시작일
CUTOFF = pd.Timestamp("2022-06-30")  # 이 분기말 이후만 저장 (초반 PIT 여유분 포함)
MAX_WORKERS = 5                      # SEC 권고 10 req/s 준수
UA = {"User-Agent": "SNU Quant Project 1000balls@gmail.com"}

# 상장폐지/피인수로 ticker→CIK 매핑에 없는 종목 수동 CIK
CIK_OVERRIDES = {
    "ATVI": 718877,    # Activision Blizzard
    "FRC":  1132979,   # First Republic Bank
    "SIVB": 719739,    # SVB Financial Group
    "SBNY": 1288776,   # Signature Bank
    "ABMD": 815094,    # Abiomed
    "PXD":  1038357,   # Pioneer Natural Resources
    "CTLT": 1596783,   # Catalent
    "SPLK": 1353283,   # Splunk
    "WRK":  1732845,   # WestRock
    "RE":   1095073,   # Everest Re
    "DISH": 1001082,   # DISH Network
    "MRO":  101778,    # Marathon Oil
    "ANSS": 1013462,   # Ansys
    "JNPR": 1043604,   # Juniper Networks
    "HES":  4447,      # Hess
}

# === 개념 매핑 (fallback 순서) ===
# instant (재무상태표 + 주식수) — us-gaap, dei
INSTANT = {
    "cash":       ("us-gaap", ["CashAndCashEquivalentsAtCarryingValue",
                               "CashCashEquivalentsAndShortTermInvestments"]),
    "assets":     ("us-gaap", ["Assets"]),
    "ppent":      ("us-gaap", ["PropertyPlantAndEquipmentNet"]),
    "equity":     ("us-gaap", ["StockholdersEquity",
                               "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]),
    "inventory":  ("us-gaap", ["InventoryNet"]),
    "retained_earnings":   ("us-gaap", ["RetainedEarningsAccumulatedDeficit"]),
    "current_assets":      ("us-gaap", ["AssetsCurrent"]),
    "current_liabilities": ("us-gaap", ["LiabilitiesCurrent"]),
}

# 주식수 — dei 표지일은 분기말과 며칠 어긋나므로 '근사일 매칭'으로 별도 처리
SHARES_SOURCES = [
    ("us-gaap", ["CommonStockSharesOutstanding", "CommonStockSharesIssued"]),
    ("dei",     ["EntityCommonStockSharesOutstanding"]),
]

# duration (손익 + 현금흐름) — 분기값 추출
DURATION = {
    "revenue":       ["RevenueFromContractWithCustomerExcludingAssessedTax",
                      "Revenues", "SalesRevenueNet"],
    "ni":            ["NetIncomeLoss"],
    "op_income":     ["OperatingIncomeLoss"],
    "ebit":          ["OperatingIncomeLoss"],
    "gross_profit":  ["GrossProfit"],
    "cost_of_revenue": ["CostOfGoodsAndServicesSold", "CostOfRevenue"],
    "eps":           ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
    "capex":         ["PaymentsToAcquirePropertyPlantAndEquipment",
                      "PaymentsToAcquireProductiveAssets"],
    "ocf":           ["NetCashProvidedByUsedInOperatingActivities"],
    "div_paid":      ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
    "dep_amort":     ["DepreciationDepletionAndAmortization",
                      "DepreciationAmortizationAndAccretionNet",
                      "DepreciationAndAmortization"],
}

# 최종 parquet 컬럼 (기존 스키마 유지)
FINAL_FIELDS = [
    "cash", "debt", "assets", "ppent", "equity", "inventory", "shares",
    "retained_earnings", "current_assets", "current_liabilities",
    "revenue", "ni", "ebitda", "ebit", "gross_profit", "op_income", "eps",
    "cost_of_revenue", "fcf", "capex", "div_paid",
]


def _d(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def load_ciks(union):
    """union 종목 → CIK(int) 매핑."""
    current = pd.read_csv(ROOT / "data" / "sp500_current.csv")
    cik_map = {}
    if "CIK" in current.columns:
        for _, r in current.iterrows():
            try:
                cik_map[r["Symbol"]] = int(r["CIK"])
            except (ValueError, TypeError):
                pass
    # SEC ticker→CIK (현재 상장 종목)
    try:
        tj = requests.get("https://www.sec.gov/files/company_tickers.json",
                          headers=UA, timeout=30).json()
        for v in tj.values():
            cik_map.setdefault(v["ticker"], int(v["cik_str"]))
    except Exception as e:
        print(f"  [warn] company_tickers.json 실패: {e}")
    cik_map.update(CIK_OVERRIDES)
    resolved = {s: cik_map[s] for s in union if s in cik_map}
    missing = [s for s in union if s not in cik_map]
    return resolved, missing


def fetch_facts(cik):
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=40)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                time.sleep(1.0 + attempt)
                continue
            return None
        except Exception:
            time.sleep(0.5 + attempt)
    return None


def _pick(store, candidates):
    for c in candidates:
        if c in store:
            return store[c]
    return None


def instant_points(node):
    """instant 개념 → {end(str): (val, filed)} (분기말 스냅샷, 최초 공시 우선)."""
    out = {}
    if not node:
        return out
    units = node.get("units", {})
    chosen = None
    for u in ["USD", "shares"] + list(units.keys()):
        if u in units:
            chosen = units[u]
            break
    if not chosen:
        return out
    for p in chosen:
        e, v = p.get("end"), p.get("val")
        if e is None or v is None:
            continue
        f = p.get("filed", e)
        if e not in out or f < out[e][1]:
            out[e] = (v, f)
    return out


def quarterly_points(node):
    """duration 개념 → {end(str): (val, filed)} 분기값.

    손익항목은 10-Q 에 3개월 값이 직접 있지만, 현금흐름은 누적(YTD)으로만
    보고된다. 따라서:
      1) 3개월(80~100일) 직접 값 우선 사용 (손익 Q1~Q3)
      2) 회계연도별 YTD 차분으로 빈 분기 채움 (현금흐름 전 분기 + 손익 Q4)
         분기값 = YTD(이번 분기말) - YTD(직전 분기말), 회계연도 시작 시 0 리셋
    """
    if not node:
        return {}
    units = node.get("units", {})
    unit = None
    for u in ["USD", "USD/shares"] + list(units.keys()):
        if u in units:
            unit = u
            break
    if not unit:
        return {}

    # (start,end) 중복 제거 — 최초 공시 우선 (이전연도 비교치/재작성 정리).
    # fy 태그는 비교치 때문에 오염되므로 쓰지 않고, '기간 시작일(start)' 로 그룹화한다.
    uniq = {}
    for p in units[unit]:
        s, e, v = p.get("start"), p.get("end"), p.get("val")
        if not s or not e or v is None:
            continue
        if not str(p.get("form", "")).startswith(("10-Q", "10-K")):
            continue
        f = p.get("filed", e)
        k = (s, e)
        if k not in uniq or f < uniq[k][1]:
            uniq[k] = (v, f)

    from collections import defaultdict
    by_start = defaultdict(list)
    for (s, e), (v, f) in uniq.items():
        by_start[s].append((e, v, f, (_d(e) - _d(s)).days))

    out = {}

    def setq(e, v, f):
        if e not in out or f < out[e][1]:
            out[e] = (v, f)

    for s, grp in by_start.items():
        grp.sort(key=lambda x: _d(x[0]))
        if len(grp) >= 2:
            # 같은 시작일을 공유 = YTD 사다리 → 연속 차분으로 분기값
            prev = 0.0
            for e, v, f, days in grp:
                setq(e, v - prev, f)
                prev = v
        else:
            # 단독 포인트 = 이미 3개월(분기) 값일 때만 사용
            e, v, f, days = grp[0]
            if 80 <= days <= 100:
                setq(e, v, f)
    return out


def debt_series(gaap):
    """총부채 ≈ 장기차입금(+유동성 장기부채/단기차입금). 분리 태그를 합산해 커버리지 ↑."""
    combined = instant_points(gaap.get("DebtLongtermAndShorttermCombinedAmount"))
    lt_total = instant_points(gaap.get("LongTermDebt"))
    lt_nc = instant_points(gaap.get("LongTermDebtNoncurrent"))
    lt_c = instant_points(gaap.get("LongTermDebtCurrent"))
    debt_c = instant_points(gaap.get("DebtCurrent"))
    st = instant_points(gaap.get("ShortTermBorrowings"))
    ends = set(combined) | set(lt_total) | set(lt_nc) | set(lt_c) | set(debt_c)
    out = {}
    for e in ends:
        if e in combined:
            out[e] = combined[e]
            continue
        nc = lt_total.get(e) or lt_nc.get(e)
        cur = lt_c.get(e) or debt_c.get(e) or st.get(e)
        if nc:
            out[e] = (nc[0] + (cur[0] if cur else 0), nc[1])
        elif cur:
            out[e] = cur
    return out


def shares_series(store):
    """주식수 후보를 합쳐 {end(str): (val, filed)} (최초 공시 우선)."""
    merged = {}
    for ns, cands in SHARES_SOURCES:
        for e, (v, f) in instant_points(_pick(store[ns], cands)).items():
            if e not in merged or f < merged[e][1]:
                merged[e] = (v, f)
    return merged


def nearest_asof(series, target, lo=-15, hi=85):
    """target(분기말) 기준 [target+lo, target+hi] 안에서 가장 가까운 값."""
    t = _d(target)
    best, best_dist = None, None
    for e, (v, f) in series.items():
        dist = (_d(e) - t).days
        if lo <= dist <= hi:
            score = abs(dist)
            if best_dist is None or score < best_dist:
                best_dist, best = score, v
    return best


def build_rows(symbol, facts):
    gaap = facts.get("facts", {}).get("us-gaap", {})
    dei = facts.get("facts", {}).get("dei", {})
    store = {"us-gaap": gaap, "dei": dei}

    series = {}        # field -> {end: (val, filed)}
    for field, (ns, cands) in INSTANT.items():
        series[field] = instant_points(_pick(store[ns], cands))
    for field, cands in DURATION.items():
        series[field] = quarterly_points(_pick(gaap, cands))
    sh_series = shares_series(store)   # 주식수 (근사일 매칭)
    dt_series = debt_series(gaap)      # 총부채 (분리 태그 합산)

    # 모든 분기말 후보 = assets 또는 revenue 가 있는 end
    ends = set(series["assets"]) | set(series["revenue"])
    rows = []
    for e in sorted(ends):
        qe = pd.Timestamp(e)
        if qe < CUTOFF:
            continue
        row = {"symbol": symbol, "quarter_end": qe}
        fileds = []
        for f in FINAL_FIELDS:
            if f in ("ebitda", "fcf"):
                continue  # 파생, 아래서 계산
            if f == "shares":
                row[f] = nearest_asof(sh_series, e)
                continue
            if f == "debt":
                dv = dt_series.get(e)
                row[f] = dv[0] if dv else None
                if dv:
                    fileds.append(dv[1])
                continue
            pv = series.get(f, {}).get(e)
            row[f] = pv[0] if pv else None
            if pv:
                fileds.append(pv[1])
        # 파생: ebitda = op_income + 감가상각, fcf = ocf - capex
        oi = series["op_income"].get(e)
        da = series["dep_amort"].get(e)
        row["ebitda"] = (oi[0] + da[0]) if (oi and da) else None
        ocf = series["ocf"].get(e)
        cap = series["capex"].get(e)
        row["fcf"] = (ocf[0] - cap[0]) if (ocf and cap) else None
        # 공시일 = 그 분기 항목들 중 최초 filed
        row["announcement_date"] = pd.Timestamp(min(fileds)) if fileds else pd.NaT
        rows.append(row)
    return rows


def main():
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    print(f"[1/4] union 유니버스 구성 ({START_DATE} ~ {today})...")
    current_symbols, changes = load_data(str(ROOT / "data"))
    sample = pd.date_range(START_DATE, today, freq="MS").append(
        pd.DatetimeIndex([START_DATE, today]))
    union = set()
    for d in sample:
        union |= get_sp500_members_at(d, current_symbols, changes)
    union = sorted(union)
    print(f"      union 크기: {len(union)}")

    print(f"[2/4] CIK 매핑...")
    ciks, missing = load_ciks(union)
    print(f"      해결: {len(ciks)}  /  CIK 없음(스킵): {len(missing)} {missing[:15]}")

    print(f"[3/4] EDGAR companyfacts 다운로드 (workers={MAX_WORKERS})...")
    t0 = time.time()
    all_rows, failed = [], []

    def work(sym):
        time.sleep(0.1)  # rate-limit 여유
        facts = fetch_facts(ciks[sym])
        if facts is None:
            return sym, None
        try:
            return sym, build_rows(sym, facts)
        except Exception as e:
            return sym, f"ERR:{e}"

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(work, s): s for s in ciks}
        done = 0
        for fut in as_completed(futures):
            sym, res = fut.result()
            if isinstance(res, list):
                all_rows.extend(res)
            else:
                failed.append(sym)
            done += 1
            if done % 50 == 0:
                print(f"      {done}/{len(ciks)}  ({time.time()-t0:.0f}s)")
    print(f"      완료: 행 {len(all_rows)}, 실패 {len(failed)} {failed[:10]}  ({time.time()-t0:.0f}s)")

    print(f"[4/4] 저장: {OUTPUT_FILE}")
    df = pd.DataFrame(all_rows)
    df = df.dropna(subset=["quarter_end"])
    df["quarter_end"] = pd.to_datetime(df["quarter_end"])
    # 컬럼 순서 정리 (announcement_date 포함)
    cols = FINAL_FIELDS + ["announcement_date"]
    df = df.set_index(["symbol", "quarter_end"]).sort_index()
    df = df.reindex(columns=cols)
    df.to_parquet(OUTPUT_FILE)

    qe = df.index.get_level_values("quarter_end")
    print()
    print("=" * 56)
    print(f"shape: {df.shape}  | 종목: {df.index.get_level_values('symbol').nunique()}")
    print(f"분기 범위: {qe.min().date()} ~ {qe.max().date()}")
    for yr in [2022, 2023, 2024, 2025, 2026]:
        sub = df[qe.year == yr]
        print(f"  {yr}: 행 {len(sub):4d}  종목 {sub.index.get_level_values('symbol').nunique()}")
    print("  결측 비율(필드별):")
    for c in FINAL_FIELDS:
        print(f"    {c:22s} {df[c].isna().mean():.1%}")


if __name__ == "__main__":
    main()
