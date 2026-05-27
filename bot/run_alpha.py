"""매일 한 번 실행: 알파 계산 → Alpaca 페이퍼 계좌에 주문.

단순 버전 (스터디 발표용 v0):
  - Alpha: rank(-returns)
  - Neutralization: GICS Sector
  - Decay / Truncation: 없음
  - D-1 종가 데이터로 알파 계산 → 시장가 주문 (다음 장 개장 시 D 시가에 체결)

실행 가정: 매일 미국 장 마감 직후 (한국 시간 새벽 5~6시)
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from lib.sp500_universe import load_data, get_sp500_members_at
from lib.alpha_eval import evaluate


LOG_DIR = ROOT / "bot" / "logs"
CONFIG_FILE = ROOT / "bot" / "alpha_config.json"


# === 1. Setup ===

def setup_clients():
    load_dotenv(ROOT / ".env")
    key = os.environ["ALPACA_API_KEY"]
    secret = os.environ["ALPACA_SECRET_KEY"]
    trading = TradingClient(key, secret, paper=True)
    data = StockHistoricalDataClient(key, secret)
    return trading, data


# === 2. 최근 일봉 받기 ===

def fetch_recent_panel(data_client, symbols, lookback_days=15, batch_size=50):
    """최근 lookback_days 거래일치 일봉 데이터. returns 한 번 쓸 거라 D-1, D-2 만 필요하지만 여유롭게."""
    end = datetime.now(timezone.utc) - timedelta(minutes=20)  # SIP 지연 회피
    start = end - timedelta(days=lookback_days + 14)

    dfs = []
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        req = StockBarsRequest(
            symbol_or_symbols=batch,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
        )
        bars = data_client.get_stock_bars(req)
        if not bars.df.empty:
            dfs.append(bars.df)

    return pd.concat(dfs) if dfs else pd.DataFrame()


# === 3. 알파 계산 (마지막 날만) ===

def load_config():
    """alpha_config.json 에서 expression + settings 읽기."""
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def compute_today_weights(panel, sector_map, expression, settings):
    """alpha expression 평가해서 마지막 거래일 포지션 비중 반환."""
    try:
        fundamentals = pd.read_parquet(ROOT / "data" / "sp500_fundamentals.parquet")
    except FileNotFoundError:
        fundamentals = pd.DataFrame()
    return evaluate(expression, panel, fundamentals, sector_map, settings)


# === 4. 목표 포지션 ↔ 주문 ===

MIN_QTY = 1e-4  # 이보다 작은 절댓값은 주문 안 함


def get_target_shares(weights, equity, latest_prices, fractional=True):
    """목표 주식 수.

    Alpaca 제약: fractional 은 long 만 가능, short 는 정수만 허용.
    - long  (w > 0): fractional=True 면 소수점 4자리
    - short (w < 0): 항상 정수 (truncate toward 0)
    """
    shares = {}
    for sym, w in weights.items():
        price = latest_prices.get(sym)
        if not price or price <= 0:
            continue
        target_dollar = equity * w
        if target_dollar > 0 and fractional:
            n = round(target_dollar / price, 4)
        else:
            n = int(target_dollar / price)
        if abs(n) >= MIN_QTY:
            shares[sym] = n
    return shares


def get_current_positions(trading):
    return {p.symbol: float(p.qty) for p in trading.get_all_positions()}


def reconcile(target, current):
    """target - current = 거래해야 할 주식 수. 너무 작은 차이는 무시."""
    all_syms = set(target) | set(current)
    out = {}
    for s in all_syms:
        diff = target.get(s, 0) - current.get(s, 0)
        if abs(diff) >= MIN_QTY:
            out[s] = round(diff, 4)
    return out


def submit_orders(trading, orders, dry_run=False):
    submitted, failed = [], []
    for sym, qty in orders.items():
        side = OrderSide.BUY if qty > 0 else OrderSide.SELL
        if dry_run:
            print(f"  [DRY] {side.value:5s} {sym:6s} x {abs(qty)}")
            continue
        try:
            req = MarketOrderRequest(
                symbol=sym,
                qty=abs(qty),
                side=side,
                time_in_force=TimeInForce.DAY,
            )
            order = trading.submit_order(req)
            submitted.append({"symbol": sym, "qty": qty, "id": str(order.id)})
            print(f"  {side.value:5s} {sym:6s} x {abs(qty)}  id={order.id}")
        except Exception as e:
            failed.append({"symbol": sym, "qty": qty, "error": str(e)})
            print(f"  ERR  {side.value:5s} {sym:6s} x {abs(qty)} → {e}")
    return submitted, failed


# === 5. 로그 ===

def write_log(payload):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"run_{ts}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"  로그 저장: {log_file}")


# === 6. 메인 ===

def main(dry_run=False):
    started_at = datetime.now()
    print(f"=== Alpha Bot {started_at:%Y-%m-%d %H:%M:%S} ===")
    print(f"Dry run: {dry_run}\n")

    print("[1/6] Alpaca 연결...")
    trading, data = setup_clients()
    acct = trading.get_account()
    equity = float(acct.equity)
    print(f"  Equity: ${equity:,.2f}  Cash: ${float(acct.cash):,.2f}\n")

    print("[2/6] S&P 500 유니버스...")
    current_symbols, changes = load_data(str(ROOT / "data"))
    today = datetime.now().strftime("%Y-%m-%d")
    members = sorted(get_sp500_members_at(today, current_symbols, changes))
    print(f"  유니버스 크기: {len(members)}\n")

    print("[3/6] 최근 일봉 다운로드...")
    panel = fetch_recent_panel(data, members)
    if panel.empty:
        print("  ERR: 데이터 없음")
        return
    n_dates = panel.index.get_level_values("timestamp").nunique()
    last_date = panel.index.get_level_values("timestamp").max().date()
    print(f"  rows: {len(panel):,}  날짜 수: {n_dates}  마지막 날: {last_date}\n")

    print("[4/6] 알파 계산...")
    current_csv = pd.read_csv(ROOT / "data" / "sp500_current.csv")
    sector_map = dict(zip(current_csv["Symbol"], current_csv["GICS Sector"]))
    for s in members:
        sector_map.setdefault(s, "Unknown")

    cfg = load_config()
    expression = cfg["expression"]
    settings = cfg.get("settings", {})
    print(f"  expression: {expression}")
    print(f"  settings:   {settings}")

    weights = compute_today_weights(panel, sector_map, expression, settings)
    longs = weights[weights > 0]
    shorts = weights[weights < 0]
    print(f"  종목 수: {len(weights)}  long: {len(longs)}  short: {len(shorts)}")
    print(f"  long 합: {longs.sum():+.4f}  short 합: {shorts.sum():+.4f}  |sum|: {weights.abs().sum():.4f}\n")

    print("[5/6] 목표 포지션 계산...")
    close = panel["close"].unstack(level="symbol")
    latest_prices = close.iloc[-1].to_dict()

    target = get_target_shares(weights, equity, latest_prices)
    current = get_current_positions(trading)
    orders = reconcile(target, current)
    print(f"  목표 종목: {len(target)}  현재 보유: {len(current)}  주문 건수: {len(orders)}\n")

    # LIVE 시 wash trade 방지를 위해 기존 open orders 먼저 취소
    cancelled_n = 0
    if not dry_run:
        try:
            cancel_results = trading.cancel_orders()
            cancelled_n = len(cancel_results) if cancel_results else 0
            if cancelled_n:
                print(f"[wash-trade 방지] 기존 open orders {cancelled_n}건 취소 요청")
                import time
                time.sleep(2)  # 거래소 처리 대기
        except Exception as e:
            print(f"[경고] open orders 취소 실패: {e}")
        print()

    print("[6/6] 주문 제출...")
    submitted, failed = submit_orders(trading, orders, dry_run=dry_run)
    print()

    print(f"=== 완료: 제출 {len(submitted)}, 실패 {len(failed)} (사전 취소 {cancelled_n}) ===")

    write_log({
        "started_at": started_at.isoformat(),
        "dry_run": dry_run,
        "equity": equity,
        "universe_size": len(members),
        "panel_last_date": str(last_date),
        "expression": expression,
        "settings": settings,
        "weights": {k: float(v) for k, v in weights.items()},
        "target_shares": target,
        "current_positions": current,
        "orders": orders,
        "pre_cancelled": cancelled_n,
        "submitted": submitted,
        "failed": failed,
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="주문 출력만, 실제 제출 안 함")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
