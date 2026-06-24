"""KOSPI 모의 트레이딩 데이터 — FinanceDataReader.
유니버스(KOSPI 시총 상위 N 보통주) + 일별 패널(OHLCV) + KS11 지수 저장.
미국판 05_fetch_panel_data 의 국내 버전. (시세·지수는 키 불필요)
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import pandas as pd
import FinanceDataReader as fdr

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
TOP_N = 200
START = "2024-06-01"   # ~2년: ts_zscore(252) 룩백 + 1년 표시 + 버퍼


def main():
    print(f"[1/3] KOSPI 유니버스 (시총 상위 {TOP_N} 보통주)...")
    lst = fdr.StockListing("KOSPI")
    lst = lst[lst["Market"] == "KOSPI"].copy()
    lst = lst[~lst["Name"].astype(str).str.contains("스팩|제[0-9]+호", na=False)]   # SPAC 제외
    lst = lst[lst["Code"].astype(str).str.endswith("0")]                            # 보통주(우선주 제외)
    lst = lst[lst["Stocks"] > 0]
    lst = lst.sort_values("Marcap", ascending=False).head(TOP_N)
    uni = lst[["Code", "Name", "Stocks", "Marcap"]].rename(columns={"Code": "Symbol"})
    uni.to_csv(DATA / "kospi_universe.csv", index=False, encoding="utf-8-sig")
    print(f"   {len(uni)}종목. 상위3: {list(uni['Name'].head(3))}")

    print("[2/3] 일별 패널(OHLCV)...")
    frames, t0, ok = [], time.time(), 0
    for i, sym in enumerate(uni["Symbol"]):
        try:
            df = fdr.DataReader(sym, START)
            if df is None or df.empty:
                continue
            df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].copy()
            df.index.name = "timestamp"
            df["symbol"] = sym
            frames.append(df.reset_index().set_index(["timestamp", "symbol"]))
            ok += 1
        except Exception:
            continue
        if (i + 1) % 50 == 0:
            print(f"    {i+1}/{len(uni)} ({time.time()-t0:.0f}s)")
    panel = pd.concat(frames).sort_index()
    panel.to_parquet(DATA / "kospi_panel.parquet")
    ts = panel.index.get_level_values("timestamp")
    print(f"   패널 {panel.shape}, 종목 {ok}, 기간 {ts.min().date()}~{ts.max().date()}, 거래일 {ts.nunique()}")

    print("[3/3] KS11(코스피) 지수...")
    idx = fdr.DataReader("KS11", START)[["Close"]].rename(columns={"Close": "close"})
    idx.index.name = "date"
    idx.to_csv(DATA / "kospi_index.csv", encoding="utf-8-sig")
    print(f"   KS11 {len(idx)}일, 마지막 {idx.index[-1].date()} = {float(idx['close'].iloc[-1]):.1f}")
    print("완료.")


if __name__ == "__main__":
    main()
