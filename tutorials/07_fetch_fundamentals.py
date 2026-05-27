"""S&P 500 종목별 분기별 시계열 fundamental 다운로드 (yfinance).

흐름:
  1. 현재 S&P 500 종목 리스트 로드
  2. 각 종목의 quarterly_balance_sheet / quarterly_income_stmt / quarterly_cashflow 받기
     (각 5~7분기치)
  3. (symbol, quarter_end_date) MultiIndex DataFrame 으로 통합
  4. parquet 저장

매일 cron 으로 돌려서 최신 fundamental 유지.

받는 필드 (Brain 명명 매핑):
  Balance Sheet (분기 발표):
    cash       ← Cash And Cash Equivalents (없으면 Cash Cash Equivalents And Short Term Investments)
    debt       ← Total Debt
    assets     ← Total Assets
    ppent      ← Net PPE
    equity     ← Stockholders Equity
    inventory  ← Inventory
    shares     ← Ordinary Shares Number (없으면 Share Issued)
    book_value ← Stockholders Equity / shares  (계산)

  Income Statement (분기 발표):
    revenue    ← Total Revenue
    ni         ← Net Income
    ebitda     ← EBITDA
    ebit       ← EBIT
    gross_profit ← Gross Profit
    op_income  ← Operating Income
    eps        ← Diluted EPS (없으면 Basic EPS)

  Cash Flow (분기 발표):
    ocf        ← (Operating Cash Flow 없음) 직접 계산 어려움, 일단 skip
    fcf        ← Free Cash Flow
    capex      ← Capital Expenditure
    div_paid   ← Cash Dividends Paid
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

# 항목명 매핑 (alternative key 는 fallback 순서)
BS_FIELDS = {
    "cash":       ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
    "debt":       ["Total Debt"],
    "assets":     ["Total Assets"],
    "ppent":      ["Net PPE"],
    "equity":     ["Stockholders Equity", "Common Stock Equity"],
    "inventory":  ["Inventory"],
    "shares":     ["Ordinary Shares Number", "Share Issued"],
    "retained_earnings": ["Retained Earnings"],
    "current_assets": ["Current Assets"],
    "current_liabilities": ["Current Liabilities"],
}

IS_FIELDS = {
    "revenue":    ["Total Revenue", "Operating Revenue"],
    "ni":         ["Net Income", "Net Income Common Stockholders"],
    "ebitda":     ["EBITDA", "Normalized EBITDA"],
    "ebit":       ["EBIT"],
    "gross_profit": ["Gross Profit"],
    "op_income":  ["Operating Income"],
    "eps":        ["Diluted EPS", "Basic EPS"],
    "cost_of_revenue": ["Cost Of Revenue", "Reconciled Cost Of Revenue"],
}

CF_FIELDS = {
    "fcf":        ["Free Cash Flow"],
    "capex":      ["Capital Expenditure"],
    "div_paid":   ["Cash Dividends Paid"],
}


def _pick(df, candidates, q_col):
    """df 의 index 후보들 중 첫 매치 → q_col 값 반환."""
    for label in candidates:
        if label in df.index:
            v = df.loc[label, q_col]
            if pd.notna(v):
                return float(v)
    return None


def fetch_one(symbol):
    """한 종목의 모든 분기 데이터 → [{symbol, quarter_end, ...}, ...]"""
    rows = []
    try:
        t = yf.Ticker(symbol)
        bs = t.quarterly_balance_sheet
        income = t.quarterly_income_stmt
        cf = t.quarterly_cashflow

        # 분기 발표 시점 (column = quarter_end_date) — 세 표의 합집합
        all_quarters = sorted(
            set(bs.columns) | set(income.columns) | set(cf.columns),
            reverse=True,
        )

        for q in all_quarters:
            row = {"symbol": symbol, "quarter_end": pd.Timestamp(q)}
            for k, candidates in BS_FIELDS.items():
                row[k] = _pick(bs, candidates, q) if q in bs.columns else None
            for k, candidates in IS_FIELDS.items():
                row[k] = _pick(income, candidates, q) if q in income.columns else None
            for k, candidates in CF_FIELDS.items():
                row[k] = _pick(cf, candidates, q) if q in cf.columns else None
            rows.append(row)
    except Exception as e:
        rows.append({"symbol": symbol, "quarter_end": pd.NaT, "_err": str(e)})
    return rows


def main():
    print("[1/3] 유니버스 로드...")
    current = pd.read_csv("data/sp500_current.csv")
    symbols = sorted(current["Symbol"].unique())
    print(f"  종목 수: {len(symbols)}")

    print(f"[2/3] yfinance quarterly 다운로드 (workers={MAX_WORKERS})...")
    t0 = time.time()
    all_rows = []
    failed = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_one, s): s for s in symbols}
        done = 0
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                rows = fut.result()
                # 에러 row 분리
                ok_rows = [r for r in rows if "_err" not in r and pd.notna(r.get("quarter_end"))]
                if not ok_rows:
                    failed.append(sym)
                all_rows.extend(ok_rows)
            except Exception as e:
                failed.append(sym)
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(symbols)}  ({time.time()-t0:.1f}s)")
    print(f"  완료: 행 수 {len(all_rows)}, 종목 실패 {len(failed)}, 소요 {time.time()-t0:.1f}s")

    print("[3/3] 저장 중...")
    df = pd.DataFrame(all_rows)
    df = df.dropna(subset=["quarter_end"])
    df["quarter_end"] = pd.to_datetime(df["quarter_end"])
    df = df.set_index(["symbol", "quarter_end"]).sort_index()

    df.to_parquet(OUTPUT_FILE)
    print(f"  저장: {OUTPUT_FILE}")
    print(f"  shape: {df.shape}")
    print(f"  종목 수: {df.index.get_level_values('symbol').nunique()}")
    print(f"  분기 범위: {df.index.get_level_values('quarter_end').min().date()} ~ "
          f"{df.index.get_level_values('quarter_end').max().date()}")
    print(f"  종목당 평균 분기 수: {len(df) / df.index.get_level_values('symbol').nunique():.1f}")
    print()
    print(f"  결측 비율 (필드별):")
    for c in df.columns:
        miss = df[c].isna().mean()
        marker = " ⚠️" if miss > 0.3 else ""
        print(f"    {c:20s}  {miss:.1%}{marker}")


if __name__ == "__main__":
    main()
