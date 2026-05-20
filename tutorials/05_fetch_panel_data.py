# S&P 500 panel data 다운로드 (옵션 B: union of all members)
#
# 흐름:
#   1. 테스트 기간 동안 한 번이라도 S&P 500이었던 종목 set 구성
#   2. Alpaca에서 그 종목들의 1년치 일봉을 배치로 받음
#   3. Parquet 파일로 저장

import os
import time
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from lib.sp500_universe import load_data, get_sp500_members_at

# === 설정 ===
START_DATE = "2025-05-20"
END_DATE = "2026-05-19"
BATCH_SIZE = 50
OUTPUT_FILE = "data/sp500_panel.parquet"


def build_universe(start_date, end_date):
    """기간 동안 한 번이라도 S&P 500이었던 종목 set 반환."""
    current_symbols, changes = load_data()

    # 매월 1일 시점의 멤버십을 모두 합집합 (월 단위 샘플링이면 충분)
    sample_dates = pd.date_range(start=start_date, end=end_date, freq="MS")
    # MS = Month Start. 매월 1일.

    # 시작/종료 시점도 추가
    sample_dates = sample_dates.append(pd.DatetimeIndex([start_date, end_date]))

    union = set()
    for date in sample_dates:
        members = get_sp500_members_at(date, current_symbols, changes)
        union |= members  # set union

    return sorted(union)


def fetch_panel(symbols, start_date, end_date):
    """Alpaca에서 종목 리스트의 일봉을 배치로 받아 panel DataFrame 반환."""
    load_dotenv()
    client = StockHistoricalDataClient(
        os.getenv("ALPACA_API_KEY"),
        os.getenv("ALPACA_SECRET_KEY"),
    )

    # 날짜 변환
    start_dt = pd.to_datetime(start_date).tz_localize(timezone.utc)
    end_dt = pd.to_datetime(end_date).tz_localize(timezone.utc)

    all_dfs = []
    failed_batches = []
    total_batches = (len(symbols) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"  배치 {batch_num}/{total_batches} "
              f"({batch[0]} ~ {batch[-1]}) 요청 중... ", end="", flush=True)

        request = StockBarsRequest(
            symbol_or_symbols=batch,
            timeframe=TimeFrame.Day,
            start=start_dt,
            end=end_dt,
        )

        try:
            bars = client.get_stock_bars(request)
            if not bars.df.empty:
                all_dfs.append(bars.df)
                print(f"OK ({len(bars.df):,}행)")
            else:
                print("빈 응답")
        except Exception as e:
            print(f"실패: {e}")
            failed_batches.append((batch_num, batch))

        time.sleep(0.3)  # Rate limit 안전 마진

    if not all_dfs:
        raise RuntimeError("모든 배치가 실패했습니다.")

    panel = pd.concat(all_dfs)
    return panel, failed_batches


# === 메인 ===
if __name__ == "__main__":
    print(f"[1/3] {START_DATE} ~ {END_DATE} 기간 유니버스 구성 중...")
    universe = build_universe(START_DATE, END_DATE)
    print(f"      유니버스 크기: {len(universe)}개 종목")
    print(f"      처음 10개: {universe[:10]}")
    print()

    print(f"[2/3] Alpaca에서 일봉 데이터 다운로드 중...")
    panel, failed = fetch_panel(universe, START_DATE, END_DATE)
    print()

    print(f"[3/3] 저장 중...")
    panel.to_parquet(OUTPUT_FILE)
    print(f"      파일: {OUTPUT_FILE}")
    print()

    # === 요약 ===
    print("=" * 60)
    print("완료")
    print("=" * 60)
    print(f"전체 행 수      : {len(panel):,}")
    print(f"고유 종목 수    : {panel.index.get_level_values('symbol').nunique()}")
    print(f"날짜 범위       : "
          f"{panel.index.get_level_values('timestamp').min().date()} ~ "
          f"{panel.index.get_level_values('timestamp').max().date()}")

    received_symbols = set(panel.index.get_level_values('symbol').unique())
    requested_symbols = set(universe)
    missing = requested_symbols - received_symbols
    print(f"누락 종목 수    : {len(missing)}")
    if missing:
        print(f"  누락 종목     : {sorted(missing)[:20]}{'...' if len(missing) > 20 else ''}")

    if failed:
        print(f"실패 배치       : {len(failed)}개")