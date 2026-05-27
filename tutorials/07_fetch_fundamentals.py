"""S&P 500 종목별 fundamental panel 다운로드 (yfinance).

흐름:
  1. 현재 S&P 500 종목 리스트 로드
  2. 각 종목에 대해 multi-thread 로 .info + quarterly_balance_sheet 받기
  3. 핵심 필드만 추출해서 종목 × 필드 DataFrame 으로 변환
  4. parquet 저장

받는 필드 (Brain 명명과 매핑):
  - cap          ← marketCap
  - cash         ← totalCash (또는 balance_sheet 의 "Cash And Cash Equivalents")
  - debt         ← totalDebt
  - assets       ← balance_sheet 의 "Total Assets"
  - ppent        ← balance_sheet 의 "Net PPE"
  - equity       ← balance_sheet 의 "Stockholders Equity"
  - revenue      ← totalRevenue (TTM)
  - ni           ← netIncomeToCommon (TTM)
  - ebitda
  - fcf          ← freeCashflow
  - ocf          ← operatingCashflow
  - shares       ← sharesOutstanding
  - eps          ← trailingEps
  - pe           ← trailingPE
  - pb           ← priceToBook
  - ps           ← priceToSalesTrailing12Months
  - roe          ← returnOnEquity
  - roa          ← returnOnAssets
"""

import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))


OUTPUT_FILE = "data/sp500_fundamentals.parquet"
MAX_WORKERS = 12

INFO_FIELDS = {
    "cap": "marketCap",
    "cash_info": "totalCash",
    "debt": "totalDebt",
    "revenue": "totalRevenue",
    "ni": "netIncomeToCommon",
    "ebitda": "ebitda",
    "fcf": "freeCashflow",
    "ocf": "operatingCashflow",
    "shares": "sharesOutstanding",
    "eps": "trailingEps",
    "pe": "trailingPE",
    "pb": "priceToBook",
    "ps": "priceToSalesTrailing12Months",
    "roe": "returnOnEquity",
    "roa": "returnOnAssets",
    "gross_margin": "grossMargins",
    "op_margin": "operatingMargins",
    "profit_margin": "profitMargins",
    "revenue_growth": "revenueGrowth",
    "earnings_growth": "earningsGrowth",
    "div_yield": "dividendYield",
    "beta": "beta",
    "book_value": "bookValue",
    "ev": "enterpriseValue",
}

BS_FIELDS = {
    "assets": "Total Assets",
    "ppent": "Net PPE",
    "cash_bs": "Cash And Cash Equivalents",
    "equity": "Stockholders Equity",
    "inventory": "Inventory",
    "retained_earnings": "Retained Earnings",
}


def fetch_one(symbol):
    """한 종목의 fundamental 필드 추출. 실패해도 dict 반환."""
    out = {"symbol": symbol}
    try:
        t = yf.Ticker(symbol)
        info = t.info
        for k, src in INFO_FIELDS.items():
            v = info.get(src)
            out[k] = float(v) if v is not None and isinstance(v, (int, float)) else None
    except Exception as e:
        out["_info_err"] = str(e)

    try:
        bs = yf.Ticker(symbol).quarterly_balance_sheet
        if not bs.empty:
            latest_col = bs.columns[0]  # 가장 최근 분기
            for k, label in BS_FIELDS.items():
                if label in bs.index:
                    v = bs.loc[label, latest_col]
                    out[k] = float(v) if pd.notna(v) else None
                else:
                    out[k] = None
    except Exception as e:
        out["_bs_err"] = str(e)

    return out


def main():
    print("[1/3] 유니버스 로드...")
    current = pd.read_csv("data/sp500_current.csv")
    symbols = sorted(current["Symbol"].unique())
    print(f"  종목 수: {len(symbols)}")

    print(f"[2/3] yfinance fundamental 다운로드 (workers={MAX_WORKERS})...")
    t0 = time.time()
    results = []
    failed = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_one, s): s for s in symbols}
        done = 0
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                row = fut.result()
                results.append(row)
            except Exception as e:
                failed.append((sym, str(e)))
            done += 1
            if done % 50 == 0:
                elapsed = time.time() - t0
                print(f"  {done}/{len(symbols)}  ({elapsed:.1f}s)")
    print(f"  완료: {len(results)}개, 실패: {len(failed)}개, 소요 {time.time()-t0:.1f}s")

    print("[3/3] 저장 중...")
    df = pd.DataFrame(results).set_index("symbol").sort_index()

    # cash 통합: balance_sheet 우선, 없으면 info
    df["cash"] = df["cash_bs"].fillna(df.get("cash_info"))
    df = df.drop(columns=[c for c in ["cash_bs", "cash_info"] if c in df.columns])

    # 에러 컬럼 제거
    df = df.drop(columns=[c for c in df.columns if c.startswith("_")])

    df.to_parquet(OUTPUT_FILE)
    print(f"  저장: {OUTPUT_FILE}  shape={df.shape}")
    print(f"  컬럼: {list(df.columns)}")
    print(f"  결측 비율 (필드별):")
    for c in df.columns:
        miss = df[c].isna().mean()
        print(f"    {c:20s}  {miss:.1%}")


if __name__ == "__main__":
    main()
