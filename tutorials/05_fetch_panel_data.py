# S&P 500 panel data 다운로드 (옵션 B: union of all members)
#
# 흐름:
#   1. 테스트 기간 동안 한 번이라도 S&P 500이었던 종목 set 구성
#   2. Alpaca에서 그 종목들의 1년치 일봉을 배치로 받음
#   3. Parquet 파일로 저장
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import time
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import Adjustment

from lib.sp500_universe import load_data, get_sp500_members_at

# === 설정 ===
# 백테스트 기간: 2023-01-01 ~ 오늘 (cron 이 매일 갱신하므로 종료일은 동적)
START_DATE = "2023-01-01"
END_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")
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


def _fetch_bars(client, symbols, start_dt, end_dt, adjustment, label):
    """주어진 adjustment 로 배치 다운로드 → 합친 DataFrame, 실패배치 리스트."""
    all_dfs, failed = [], []
    total = (len(symbols) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i : i + BATCH_SIZE]
        bn = i // BATCH_SIZE + 1
        print(f"  [{label}] 배치 {bn}/{total} ({batch[0]}~{batch[-1]})... ", end="", flush=True)
        request = StockBarsRequest(
            symbol_or_symbols=batch,
            timeframe=TimeFrame.Day,
            start=start_dt,
            end=end_dt,
            adjustment=adjustment,
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
            failed.append((bn, batch))
        time.sleep(0.3)
    if not all_dfs:
        raise RuntimeError(f"[{label}] 모든 배치 실패")
    return pd.concat(all_dfs), failed


def fetch_panel(symbols, start_date, end_date):
    """Alpaca 일봉 panel.

    중요: 분할(split) 보정 안 하면 분할일에 가짜 폭락이 생겨 수익률이 망가짐.
      - OHLCV: SPLIT 보정 → 수익률/ts 연산에 사용
      - close_raw: RAW(미보정) close → cap = shares × 실제가격 계산에 사용
        (cap 은 실제 시총이어야 하므로 분할보정 가격을 쓰면 분할 전 구간이 어긋남)
    """
    load_dotenv()
    client = StockHistoricalDataClient(
        os.getenv("ALPACA_API_KEY"),
        os.getenv("ALPACA_SECRET_KEY"),
    )
    start_dt = pd.to_datetime(start_date).tz_localize(timezone.utc)
    end_dt = pd.to_datetime(end_date).tz_localize(timezone.utc)

    panel, failed = _fetch_bars(client, symbols, start_dt, end_dt, Adjustment.SPLIT, "split보정")
    raw, _ = _fetch_bars(client, symbols, start_dt, end_dt, Adjustment.RAW, "raw")
    # raw close 를 close_raw 컬럼으로 합침 (인덱스 정렬)
    panel = panel.copy()
    panel["close_raw"] = raw["close"].reindex(panel.index)
    return panel, failed


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