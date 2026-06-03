"""백테스트 union 유니버스 전체의 GICS Sub-Industry 맵 생성.

Subindustry 중립화용 — 섹터(08)보다 세분류(약 160개 GICS Sub-Industry).
배경: Subindustry 중립화는 섹터보다 더 좁은 그룹 안에서 알파를 중립화한다.
  - 현재 멤버 → sp500_current.csv 의 'GICS Sub-Industry' (위키피디아, 정확)
  - 방출/누락 → yfinance info['industry'] (야후 세분 industry, 근사 그룹 라벨)
  - 미해결 → 이전 결과 → sp500_sectors.csv 의 Sector (폴백; 그룹 라벨이라도 부여)
출력: data/sp500_subindustries.csv (Symbol, SubIndustry)

매주 cron 으로 갱신 (멤버십 변동 시 새 방출 종목 대응). 08 과 동일 패턴.
"""

import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from lib.sp500_universe import load_data, get_sp500_members_at

ROOT = Path(__file__).parent.parent
OUTPUT_FILE = ROOT / "data" / "sp500_subindustries.csv"
SECTORS_FILE = ROOT / "data" / "sp500_sectors.csv"
START_DATE = "2023-01-01"
MAX_WORKERS = 10


def build_union(start_date, end_date):
    current_symbols, changes = load_data(str(ROOT / "data"))
    sample = pd.date_range(start=start_date, end=end_date, freq="MS")
    sample = sample.append(pd.DatetimeIndex([start_date, end_date]))
    union = set()
    for d in sample:
        union |= get_sp500_members_at(d, current_symbols, changes)
    return sorted(union)


def fetch_yf_industry(symbol):
    """yfinance 에서 세분 industry 조회. 실패 시 None."""
    import yfinance as yf
    try:
        raw = yf.Ticker(symbol).info.get("industry")
        if raw and str(raw).strip():
            return str(raw).strip()
    except Exception:
        pass
    return None


def main():
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    print(f"[1/4] union 유니버스 구성 ({START_DATE} ~ {today})...")
    union = build_union(START_DATE, today)
    print(f"      union 크기: {len(union)}")

    current = pd.read_csv(ROOT / "data" / "sp500_current.csv")
    gics_sub = dict(zip(current["Symbol"], current["GICS Sub-Industry"]))

    sub_map, need_yf = {}, []
    for s in union:
        v = gics_sub.get(s)
        if isinstance(v, str) and v.strip() and v.strip().lower() != "unknown":
            sub_map[s] = v.strip()
        else:
            need_yf.append(s)
    print(f"      현재 CSV(GICS Sub-Industry)로 해결: {len(sub_map)}  /  yfinance 필요: {len(need_yf)}")

    print(f"[2/4] yfinance industry 조회 (workers={MAX_WORKERS})...")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_yf_industry, s): s for s in need_yf}
        for fut in as_completed(futures):
            v = fut.result()
            if v:
                sub_map[futures[fut]] = v
    print(f"      완료 ({time.time()-t0:.1f}s)")

    print("[3/4] 이전 결과 / 섹터 폴백...")
    if OUTPUT_FILE.exists():
        prev = pd.read_csv(OUTPUT_FILE)
        prev_map = dict(zip(prev["Symbol"], prev["SubIndustry"]))
        for s in union:
            if s not in sub_map:
                pv = prev_map.get(s)
                if isinstance(pv, str) and pv.strip() and pv.strip().lower() != "unknown":
                    sub_map[s] = pv.strip()
    sector_map = {}
    if SECTORS_FILE.exists():
        sec = pd.read_csv(SECTORS_FILE)
        sector_map = dict(zip(sec["Symbol"], sec["Sector"]))
    still = [s for s in union if s not in sub_map]
    for s in still:
        sub_map[s] = sector_map.get(s, "Unknown")
    print(f"      섹터 폴백: {len(still)}개")

    print(f"[4/4] 저장: {OUTPUT_FILE}")
    out = pd.DataFrame(sorted(sub_map.items()), columns=["Symbol", "SubIndustry"])
    out.to_csv(OUTPUT_FILE, index=False)
    print("=" * 56)
    print(f"종목 수: {len(out)}  /  고유 Sub-Industry: {out['SubIndustry'].nunique()}")
    print("상위 분포:")
    for si, n in out["SubIndustry"].value_counts().head(12).items():
        print(f"  {si:34s} {n}")


if __name__ == "__main__":
    main()
