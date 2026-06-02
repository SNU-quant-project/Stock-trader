"""백테스트 union 유니버스 전체의 섹터맵 생성.

배경:
  - sp500_current.csv 의 'GICS Sector' 는 *현재* 멤버만 커버한다.
  - 백테스트는 2023-01-01 이후 한 번이라도 S&P 500 이었던 종목(union)을 모두 다루므로,
    이미 방출된 종목은 섹터가 비어 'Unknown' 이 된다.
  - Sector neutralization 이 망가지지 않도록, 방출 종목도 섹터를 채운다.

방법:
  1. union 유니버스 구성 (05_fetch_panel_data 와 동일 로직)
  2. 현재 멤버 → GICS Sector (CSV, 이미 GICS 명칭)
  3. 나머지(방출/누락) → yfinance info['sector'] → GICS 명칭으로 정규화
  4. yfinance 로도 안 되는 종목 → 수동 override (아래 OVERRIDES)
  5. data/sp500_sectors.csv (Symbol, Sector) 저장 — union 전체, GICS 11 섹터로 통일

매주 cron 으로 갱신 (멤버십이 바뀌면 새 방출 종목이 생기므로).
"""

import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from lib.sp500_universe import load_data, get_sp500_members_at

ROOT = Path(__file__).parent.parent
OUTPUT_FILE = ROOT / "data" / "sp500_sectors.csv"
START_DATE = "2023-01-01"          # 백테스트 시작일과 동일
MAX_WORKERS = 10

# yfinance 섹터 명칭 → GICS 11 섹터 명칭 (현재 CSV 와 통일)
YF_TO_GICS = {
    "Technology":             "Information Technology",
    "Financial Services":     "Financials",
    "Healthcare":             "Health Care",
    "Consumer Cyclical":      "Consumer Discretionary",
    "Consumer Defensive":     "Consumer Staples",
    "Communication Services": "Communication Services",
    "Industrials":            "Industrials",
    "Energy":                 "Energy",
    "Basic Materials":        "Materials",
    "Real Estate":            "Real Estate",
    "Utilities":              "Utilities",
}

# yfinance 로도 해결 안 되는 (상장폐지/피인수) 종목 수동 매핑 — 모두 GICS 명칭
OVERRIDES = {
    "ATVI": "Communication Services",  # Activision Blizzard (MSFT 인수)
    "FRC":  "Financials",              # First Republic Bank (파산)
    "DISH": "Communication Services",  # DISH Network (EchoStar 합병)
    "CTLT": "Health Care",             # Catalent (Novo Holdings 인수)
    "PXD":  "Energy",                  # Pioneer Natural Resources (XOM 인수)
    "ABMD": "Health Care",             # Abiomed (J&J 인수)
    "SIVB": "Financials",              # SVB Financial (파산)
    "SBNY": "Financials",              # Signature Bank (파산)
    "RE":   "Financials",              # Everest Re
    "PEAK": "Real Estate",             # Healthpeak (현 DOC)
    "FLT":  "Financials",              # FleetCor (현 Corpay/CPAY)
    "WRK":  "Materials",               # WestRock (Smurfit 합병)
    "SPLK": "Information Technology",   # Splunk (CSCO 인수)
    "AMTM": "Industrials",             # Amentum
    "DAY":  "Information Technology",   # Dayforce (HCM 소프트웨어)
    "ANSS": "Information Technology",   # Ansys (Synopsys 인수)
    "CMA":  "Financials",              # Comerica (FITB 합병)
    "DFS":  "Financials",              # Discover Financial (COF 인수)
    "HES":  "Energy",                  # Hess (CVX 인수)
    "IPG":  "Communication Services",  # Interpublic Group (OMC 합병)
    "JNPR": "Information Technology",   # Juniper Networks (HPE 인수)
    "K":    "Consumer Staples",        # Kellanova (Mars 인수)
    "MRO":  "Energy",                  # Marathon Oil (COP 인수)
    "WBA":  "Consumer Staples",        # Walgreens Boots Alliance (비상장 전환)
}


def build_union(start_date, end_date):
    current_symbols, changes = load_data(str(ROOT / "data"))
    sample = pd.date_range(start=start_date, end=end_date, freq="MS")
    sample = sample.append(pd.DatetimeIndex([start_date, end_date]))
    union = set()
    for d in sample:
        union |= get_sp500_members_at(d, current_symbols, changes)
    return sorted(union)


def fetch_yf_sector(symbol):
    """yfinance 에서 섹터 조회 → GICS 명칭. 실패 시 None."""
    import yfinance as yf
    try:
        info = yf.Ticker(symbol).info
        raw = info.get("sector")
        if raw:
            return YF_TO_GICS.get(raw, raw)  # 매핑 없으면 원문 (대개 이미 일치)
    except Exception:
        pass
    return None


def main():
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    print(f"[1/4] union 유니버스 구성 ({START_DATE} ~ {today})...")
    union = build_union(START_DATE, today)
    print(f"      union 크기: {len(union)}")

    current = pd.read_csv(ROOT / "data" / "sp500_current.csv")
    gics = dict(zip(current["Symbol"], current["GICS Sector"]))

    sector_map = {}
    need_yf = []
    for s in union:
        sec = gics.get(s)
        if isinstance(sec, str) and sec.strip() and sec.strip().lower() != "unknown":
            sector_map[s] = sec.strip()
        else:
            need_yf.append(s)
    print(f"      현재 CSV 로 해결: {len(sector_map)}  /  yfinance 조회 필요: {len(need_yf)}")

    print(f"[2/4] yfinance 섹터 조회 (workers={MAX_WORKERS})...")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_yf_sector, s): s for s in need_yf}
        for fut in as_completed(futures):
            s = futures[fut]
            sec = fut.result()
            if sec:
                sector_map[s] = sec
    print(f"      완료 ({time.time()-t0:.1f}s)")

    print(f"[3/4] 미해결 종목 override / 이전 결과 fallback 적용...")
    unresolved = [s for s in union if s not in sector_map]
    for s in unresolved:
        if s in OVERRIDES:
            sector_map[s] = OVERRIDES[s]
    # 이전에 저장해 둔 sp500_sectors.csv 를 fallback 으로 (yfinance 일시 실패로
    # 인한 퇴행 방지 — 한 번 확정된 섹터는 절대 Unknown 으로 돌아가지 않게)
    if OUTPUT_FILE.exists():
        prev = pd.read_csv(OUTPUT_FILE)
        prev_map = dict(zip(prev["Symbol"], prev["Sector"]))
        for s in union:
            if s not in sector_map:
                pv = prev_map.get(s)
                if isinstance(pv, str) and pv.strip() and pv.strip().lower() != "unknown":
                    sector_map[s] = pv.strip()
    still = [s for s in union if s not in sector_map]
    if still:
        print(f"      [!] 여전히 미해결 {len(still)}개: {still}")
        print(f"          -> OVERRIDES 에 추가 필요. 임시로 'Unknown' 저장.")
        for s in still:
            sector_map[s] = "Unknown"
    else:
        print(f"      [OK] 전 종목 섹터 확정 (Unknown 0개)")

    print(f"[4/4] 저장: {OUTPUT_FILE}")
    out = pd.DataFrame(
        sorted(sector_map.items()), columns=["Symbol", "Sector"]
    )
    out.to_csv(OUTPUT_FILE, index=False)

    print()
    print("=" * 56)
    print(f"종목 수: {len(out)}")
    print("섹터별 분포:")
    for sec, n in out["Sector"].value_counts().items():
        print(f"  {sec:24s} {n}")


if __name__ == "__main__":
    main()
