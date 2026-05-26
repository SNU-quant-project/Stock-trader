"""
live_trade.py — HMM 알파 Alpaca 페이퍼 트레이딩 라이브 실행

────────────────────────────────────────────────────────────────────
하는 일 (한 사이클)
────────────────────────────────────────────────────────────────────
1. Alpaca 페이퍼 계좌 연결 (.env 의 API 키 사용)
2. 7개 종목 각각:
   - 저장된 30분봉 parquet(과거) + Alpaca 최신 분봉(갭) → 전체 30분봉
   - HMM 전략으로 현재 시점 시그널(비중 -1.0 ~ +1.0) 계산
3. 비중 → 목표 포지션(주식 수). 자본은 7종목 등가중 분배.
4. 현재 Alpaca 포지션과 비교 → 차이만큼 시장가 주문
5. 사이클 결과(시그널·주문·자산)를 logs/live_log.csv 에 기록

────────────────────────────────────────────────────────────────────
실행 모드
────────────────────────────────────────────────────────────────────
  python live_trade.py --once              # 1회 실행 후 종료 (기본, dry-run)
  python live_trade.py --loop              # 30분마다 반복 (dry-run)
  python live_trade.py --loop --execute    # 30분마다 반복 + 실제 주문 제출

  --dry-run (기본 ON): 주문을 제출하지 않고 "낼 주문"만 출력해 검증.
  --execute          : dry-run 해제 → 실제 페이퍼 계좌에 주문 제출.

────────────────────────────────────────────────────────────────────
안전장치 / 설계 메모
────────────────────────────────────────────────────────────────────
- 페이퍼 계좌(paper=True)에만 연결한다. 실제 돈 아님.
- 기본이 dry-run 이라, 먼저 출력만 보고 검증한 뒤 --execute 로 전환.
- HMM 은 매 실행 시작 시 전체 과거 데이터로 새로 학습한다(캐시 미사용).
- 시그널은 "마지막으로 완성된 30분봉" 기준 — 미완성 봉은 제외.
- 리밸런싱 임계값(config.REBALANCE_THRESHOLD) 미만 변화는 거래 스킵.
- 포지션 부호가 바뀌면(롱↔숏) 청산 주문 + 신규 주문 2건으로 분리.
- 최신 분봉은 Alpaca IEX 피드(실시간·무료)로 받는다.
"""

import argparse
import csv
import os
import sys
import time

import pandas as pd
from dotenv import load_dotenv

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from strategy.HMM_strategy import config
from strategy.HMM_strategy.strategy import HMMStrategy
from strategy.HMM_strategy.features.stock_loader import (
    load_resampled_bars, resample_bars_df,
)

# ════════════════════════════════════════════════════════════════
#  설정
# ════════════════════════════════════════════════════════════════
SYMBOLS   = ["AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA"]
MARKET_TZ = "America/New_York"
DATA_DIR  = "data/30min"
SETTLE_BUFFER_SEC = 75      # 30분봉 마감 후 데이터 정착 대기 (IEX)
BAR_MINUTES = 30

# 거래·시그널 로그 (매 사이클 결과를 CSV로 누적)
LOG_PATH   = "logs/live_log.csv"
LOG_FIELDS = ["timestamp", "symbol", "signal", "price", "pos_before",
              "target", "action", "order_delta", "equity", "mode", "note"]


# ════════════════════════════════════════════════════════════════
#  연결 / 준비
# ════════════════════════════════════════════════════════════════

def connect():
    """Alpaca 페이퍼 트레이딩 + 데이터 클라이언트 생성."""
    load_dotenv()
    key = os.getenv("ALPACA_API_KEY")
    sec = os.getenv("ALPACA_SECRET_KEY")
    if not key or not sec:
        sys.exit("[오류] .env 에 ALPACA_API_KEY / ALPACA_SECRET_KEY 가 없습니다.")
    trading = TradingClient(key, sec, paper=True)
    data = StockHistoricalDataClient(key, sec)
    return trading, data


def _parquet_path(symbol: str) -> str:
    """data/30min/ 에서 종목 parquet 경로 찾기."""
    from pathlib import Path
    files = sorted(Path(DATA_DIR).glob(f"{symbol}_*_30min.parquet"))
    if not files:
        raise FileNotFoundError(f"{DATA_DIR}/{symbol}_*_30min.parquet 없음")
    return str(files[0])


def build_strategies(lookback_years: int = 5):
    """7종목 각각 HMM 전략을 최근 lookback_years년 데이터로 학습.

    Args:
        lookback_years: HMM 학습에 쓸 최근 연수. 0 이하이면 가용한 전체 과거.

    Returns:
        strategies: {symbol: 학습된 HMMStrategy}
        histories:  {symbol: 학습/워밍업에 쓸 30분봉 DataFrame}
    """
    cutoff = None
    if lookback_years and lookback_years > 0:
        cutoff = pd.Timestamp.now() - pd.DateOffset(years=lookback_years)

    strategies, histories = {}, {}
    for sym in SYMBOLS:
        hist = load_resampled_bars(_parquet_path(sym))
        if cutoff is not None:
            hist = hist[hist["datetime"] >= cutoff].reset_index(drop=True)
        span = (f"{hist['datetime'].iloc[0].date()} ~ "
                f"{hist['datetime'].iloc[-1].date()}")
        print(f"  [{sym}] {len(hist):,}봉 ({span}) — HMM 학습 ...", flush=True)
        # hmm_model_path=None → 캐시 없이 항상 최신 데이터로 새로 학습
        strat = HMMStrategy.from_config(hmm_model_path=None, verbose=False)
        strat.fit(hist)
        strategies[sym] = strat
        histories[sym] = hist
    print(f"  → {len(strategies)}개 종목 전략 준비 완료\n")
    return strategies, histories


# ════════════════════════════════════════════════════════════════
#  데이터: 과거 parquet + 최신 분봉 → 전체 30분봉
# ════════════════════════════════════════════════════════════════

def get_full_df(symbol, data_client, history_df):
    """과거 30분봉 + Alpaca 최신 분봉(갭) → 마지막 완성봉까지의 전체 df."""
    last_hist = pd.Timestamp(history_df["datetime"].iloc[-1])      # naive ET
    start_utc = (pd.Timestamp(last_hist, tz=MARKET_TZ).tz_convert("UTC")
                 + pd.Timedelta(minutes=BAR_MINUTES))
    now_utc = pd.Timestamp.now(tz="UTC")

    if start_utc >= now_utc:
        return history_df            # 갱신할 새 데이터 없음

    # Alpaca 최신 분봉 요청 (IEX 실시간 피드)
    try:
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=start_utc.to_pydatetime(),
            end=now_utc.to_pydatetime(),
            feed="iex",
        )
        bars = data_client.get_stock_bars(req)
    except Exception as exc:
        print(f"    [{symbol}] 최신 분봉 요청 실패: {exc} → 과거 데이터만 사용")
        return history_df

    if bars.df is None or len(bars.df) == 0:
        return history_df

    try:
        recent = resample_bars_df(bars.df, symbol=symbol, timeframe="30min",
                                  rth_only=True)
    except ValueError:
        # 받은 분봉이 전부 장외(프리/애프터장)이거나 비어 있음
        # (휴장일·주말 직후·장 시작 전 실행 등) → 새 완성봉 없음 → 과거만 사용
        return history_df

    # 미완성(진행 중) 마지막 봉 제외 — 마감 30분이 지난 봉만 사용
    now_et = pd.Timestamp.now(tz=MARKET_TZ).tz_localize(None)
    recent = recent[
        recent["datetime"] + pd.Timedelta(minutes=BAR_MINUTES) <= now_et
    ]
    if len(recent) == 0:
        return history_df

    full = pd.concat([history_df, recent], ignore_index=True)
    full = (full.drop_duplicates(subset="datetime", keep="last")
                .sort_values("datetime").reset_index(drop=True))
    return full


# ════════════════════════════════════════════════════════════════
#  주문 계획
# ════════════════════════════════════════════════════════════════

def plan_orders(current_shares: int, target_shares: int):
    """현재→목표 포지션 전환 주문 목록. 부호 반전 시 청산+신규 2건.

    Returns:
        [(qty, ...), ...] — qty 는 부호 있는 정수 (양수=매수, 음수=매도)
    """
    if current_shares == target_shares:
        return []
    crosses_zero = (current_shares != 0 and target_shares != 0
                    and (current_shares > 0) != (target_shares > 0))
    if crosses_zero:
        # 1) 현재 포지션 청산  2) 목표 포지션 신규 진입
        return [-current_shares, target_shares]
    return [target_shares - current_shares]


def submit_order(trading_client, symbol, signed_qty, dry_run):
    """부호 있는 수량으로 시장가 주문 (dry_run 이면 출력만)."""
    qty = abs(int(signed_qty))
    if qty == 0:
        return
    side = OrderSide.BUY if signed_qty > 0 else OrderSide.SELL
    if dry_run:
        print(f"      [DRY-RUN] {symbol:6s} {side.value:4s} {qty}주")
        return
    req = MarketOrderRequest(symbol=symbol, qty=qty, side=side,
                             time_in_force=TimeInForce.DAY)
    order = trading_client.submit_order(req)
    print(f"      [주문제출] {symbol:6s} {side.value:4s} {qty}주 → {order.status}")


# ════════════════════════════════════════════════════════════════
#  한 사이클
# ════════════════════════════════════════════════════════════════

def _append_log(rows):
    """사이클 결과 행들을 logs/live_log.csv 에 추가한다 (헤더 자동 생성)."""
    from pathlib import Path
    path = Path(LOG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new_file:
            writer.writeheader()
        for r in rows:
            writer.writerow(r)


def run_cycle(trading_client, data_client, strategies, histories, dry_run):
    """전 종목 1회 의사결정 + 주문. 결과를 logs/live_log.csv 에 기록."""
    stamp = pd.Timestamp.now(tz=MARKET_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 78)
    print(f"  사이클 실행 — {stamp} ET  {'[DRY-RUN]' if dry_run else '[실제 주문]'}")
    print("=" * 78)

    account = trading_client.get_account()
    equity = float(account.equity)
    budget = equity / len(SYMBOLS)        # 종목별 등가중 예산
    print(f"  계좌 자산: ${equity:,.2f}   |   종목별 예산: ${budget:,.2f}")

    positions = {p.symbol: float(p.qty)
                 for p in trading_client.get_all_positions()}

    rebal = config.REBALANCE_THRESHOLD
    mode = "DRY-RUN" if dry_run else "EXECUTE"
    print(f"  {'종목':6s} {'시그널':>8s} {'현재가':>10s} {'보유':>8s} "
          f"{'목표':>8s} {'동작':>8s}")
    print("  " + "-" * 60)

    log_rows = []
    for sym in SYMBOLS:
        row = {"timestamp": stamp, "symbol": sym, "signal": "", "price": "",
               "pos_before": "", "target": "", "action": "", "order_delta": 0,
               "equity": round(equity, 2), "mode": mode, "note": ""}
        try:
            full = get_full_df(sym, data_client, histories[sym])
            signals = strategies[sym].generate_signals(full)
            weight = float(signals[-1])                       # -1.0 ~ +1.0
            price = float(full["close"].iloc[-1])
            cur = int(round(positions.get(sym, 0.0)))
            target = int(round(budget * weight / price)) if price > 0 else 0
            row.update(signal=round(weight, 4), price=round(price, 2),
                       pos_before=cur, target=target)

            # 리밸런싱 임계값: 현재 비중 대비 변화가 작으면 스킵
            cur_weight = (cur * price / budget) if budget > 0 else 0.0
            if abs(weight - cur_weight) < rebal:
                row["action"] = "스킵"
                print(f"  {sym:6s} {weight:>+8.2f} {price:>10.2f} "
                      f"{cur:>8d} {target:>8d} {'스킵':>8s}")
                log_rows.append(row)
                continue

            orders = plan_orders(cur, target)
            row["action"] = "거래" if orders else "유지"
            row["order_delta"] = (target - cur) if orders else 0
            print(f"  {sym:6s} {weight:>+8.2f} {price:>10.2f} "
                  f"{cur:>8d} {target:>8d} {row['action']:>8s}")
            for signed_qty in orders:
                submit_order(trading_client, sym, signed_qty, dry_run)

        except Exception as exc:
            row["action"] = "실패"
            row["note"] = str(exc)[:200]
            print(f"  {sym:6s} 처리 실패: {exc}")

        log_rows.append(row)

    _append_log(log_rows)
    print(f"\n  → logs/live_log.csv 에 {len(log_rows)}건 기록")
    print("=" * 78 + "\n")


# ════════════════════════════════════════════════════════════════
#  반복 실행 (--loop)
# ════════════════════════════════════════════════════════════════

def _sleep_until(target_utc, label):
    """target_utc 까지 60초 단위로 대기 (Ctrl+C 로 중단 가능)."""
    while True:
        remain = (target_utc - pd.Timestamp.now(tz="UTC")).total_seconds()
        if remain <= 0:
            return
        print(f"  ...{label} — {remain/60:.1f}분 대기", flush=True)
        time.sleep(min(remain, 60))


def _next_boundary_utc():
    """다음 30분 경계(:00 / :30) + 정착 버퍼의 UTC 시각."""
    now_et = pd.Timestamp.now(tz=MARKET_TZ)
    if now_et.minute < 30:
        nb = now_et.replace(minute=30, second=0, microsecond=0)
    else:
        nb = (now_et + pd.Timedelta(hours=1)).replace(
            minute=0, second=0, microsecond=0)
    nb = nb + pd.Timedelta(seconds=SETTLE_BUFFER_SEC)
    return nb.tz_convert("UTC")


def run_loop(trading_client, data_client, strategies, histories, dry_run):
    """장중 30분마다 사이클 실행. 장 마감 시 다음 개장까지 대기."""
    print("[루프 모드] Ctrl+C 로 종료.\n")
    while True:
        try:
            clock = trading_client.get_clock()
            if not clock.is_open:
                nxt = pd.Timestamp(clock.next_open)
                print(f"  장 마감 상태 — 다음 개장: {nxt}")
                _sleep_until(nxt + pd.Timedelta(seconds=SETTLE_BUFFER_SEC),
                             "개장 대기")
                continue

            run_cycle(trading_client, data_client, strategies, histories,
                      dry_run)

            # 다음 30분 경계까지 대기 (오늘 장 마감 넘어가면 다음 개장까지)
            nb = _next_boundary_utc()
            next_close = pd.Timestamp(clock.next_close)
            if nb >= next_close:
                clock = trading_client.get_clock()
                _sleep_until(pd.Timestamp(clock.next_open)
                             + pd.Timedelta(seconds=SETTLE_BUFFER_SEC),
                             "장 마감 — 개장 대기")
            else:
                _sleep_until(nb, "다음 봉")
        except KeyboardInterrupt:
            print("\n[종료] 사용자 중단.")
            return
        except Exception as exc:
            print(f"  [루프 오류] {exc} — 60초 후 재시도")
            time.sleep(60)


# ════════════════════════════════════════════════════════════════
#  메인
# ════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(description="HMM 알파 Alpaca 페이퍼 라이브 트레이딩")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true",
                      help="1회 실행 후 종료 (기본)")
    mode.add_argument("--loop", action="store_true",
                      help="장중 30분마다 반복 실행")
    p.add_argument("--execute", action="store_true",
                   help="실제 주문 제출 (미지정 시 dry-run — 출력만)")
    p.add_argument("--lookback-years", type=int, default=5,
                   help="HMM 학습에 쓸 최근 연수 (기본 5, 0이면 전체 과거)")
    return p.parse_args()


def main():
    args = parse_args()
    dry_run = not args.execute

    print("\n" + "=" * 78)
    print("  HMM 알파 — Alpaca 페이퍼 라이브 트레이딩")
    print(f"  모드: {'LOOP' if args.loop else 'ONCE'}   "
          f"주문: {'DRY-RUN (제출 안 함)' if dry_run else '★ 실제 제출 ★'}")
    print("=" * 78 + "\n")

    trading_client, data_client = connect()
    account = trading_client.get_account()
    print(f"  계좌 상태: {account.status}   자산: ${float(account.equity):,.2f}\n")

    lb = args.lookback_years
    print(f"[준비] 종목별 HMM 전략 학습 "
          f"(학습 기간: {'전체 과거' if lb <= 0 else f'최근 {lb}년'})")
    strategies, histories = build_strategies(lb)

    if args.loop:
        run_loop(trading_client, data_client, strategies, histories, dry_run)
    else:
        run_cycle(trading_client, data_client, strategies, histories, dry_run)
        if dry_run:
            print("dry-run 완료. 실제 주문을 내려면 --execute 를 붙이세요.")


if __name__ == "__main__":
    main()
