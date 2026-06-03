"""백테스팅 엔진.

흐름:
  expression + settings  →  evaluate_full (전체 날짜 weights DataFrame)
                          →  run_backtest (D 시가 → D+1 시가 수익)
                          →  compute_metrics (Sharpe, MDD, ...)

기존 tutorials/06_backtest_meanrev.py 의 backtest / compute_metrics 로직 재사용.
"""

from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd

from .alpha_eval import evaluate

ROOT = Path(__file__).parent.parent


def load_backtest_data():
    """price panel + fundamentals + sector_map 로드.

    sector_map: 현재 멤버는 GICS Sector, 방출/누락 종목은 sp500_sectors.csv
    (08_fetch_sectors.py 산출물, yfinance 로 보강 + GICS 명칭 정규화) 로 채운다.
    → 백테스트 union 유니버스에 'Unknown' 섹터가 남지 않게 한다.
    """
    panel = pd.read_parquet(ROOT / "data" / "sp500_panel.parquet")
    try:
        fundamentals = pd.read_parquet(ROOT / "data" / "sp500_fundamentals.parquet")
    except FileNotFoundError:
        fundamentals = pd.DataFrame()
    current = pd.read_csv(ROOT / "data" / "sp500_current.csv")
    sector_map = dict(zip(current["Symbol"], current["GICS Sector"]))
    sec_path = ROOT / "data" / "sp500_sectors.csv"
    if sec_path.exists():
        sec = pd.read_csv(sec_path)
        # 완전 섹터맵을 우선 적용 (현재 멤버 + 방출 종목 모두 포함)
        sector_map.update(dict(zip(sec["Symbol"], sec["Sector"])))
    # Sub-Industry 맵: 현재 멤버는 CSV 의 GICS Sub-Industry, union 은 보강 파일(10_)
    subindustry_map = dict(zip(current["Symbol"], current["GICS Sub-Industry"]))
    sub_path = ROOT / "data" / "sp500_subindustries.csv"
    if sub_path.exists():
        sub = pd.read_csv(sub_path)
        subindustry_map.update(dict(zip(sub["Symbol"], sub["SubIndustry"])))
    return panel, fundamentals, sector_map, subindustry_map


def run_backtest(weights, panel, delay=1):
    """
    weights: (date × symbol) 의 알파 비중 DataFrame (t 일자는 t close 까지 본 정보)
    panel:   원본 panel (close, open 컬럼 존재)
    delay:   lookahead bias 방지용. weights 를 delay 만큼 shift 후 다음날 진입.

    반환: portfolio_returns Series (일별 수익률)
    """
    close = panel["close"].unstack(level="symbol")
    open_ = panel["open"].unstack(level="symbol")
    for df in (close, open_):
        idx = df.index.normalize()
        if hasattr(idx, "tz") and idx.tz is not None:
            idx = idx.tz_localize(None)
        df.index = idx

    # delay 적용: t close 정보로 계산된 알파 → t+delay 시가 진입
    if delay > 0:
        weights = weights.shift(delay)

    # 컬럼/행 정렬
    weights = weights.reindex(index=open_.index, columns=open_.columns).fillna(0)

    # 종목별 일수익률: t 시가 → t+1 시가
    next_open = open_.shift(-1)
    daily_returns = (next_open / open_ - 1).fillna(0)

    portfolio_returns = (weights * daily_returns).sum(axis=1)
    return portfolio_returns


def compute_metrics(returns, weights):
    rets = returns.dropna()
    rets = rets[rets != 0]  # 마지막 날 next_open NaN 으로 0 인 경우 제거

    if len(rets) < 2:
        return {"error": "데이터 부족"}

    cumulative = (1 + rets).cumprod()
    total_return = cumulative.iloc[-1] - 1

    n_days = len(rets)
    annual_return = (1 + total_return) ** (252 / n_days) - 1 if n_days else 0
    sharpe = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else 0

    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    mdd = drawdown.min()

    win_rate = (rets > 0).mean()

    trade = weights.diff().abs().sum(axis=1).dropna()
    avg_turnover = trade.mean() if len(trade) else 0

    daily_max_w = weights.abs().max(axis=1).dropna()
    avg_max_weight = daily_max_w.mean() if len(daily_max_w) else 0
    peak_max_weight = daily_max_w.max() if len(daily_max_w) else 0

    return {
        "n_days": n_days,
        "total_return": float(total_return),
        "annual_return": float(annual_return),
        "sharpe": float(sharpe),
        "mdd": float(mdd),
        "win_rate": float(win_rate),
        "avg_turnover": float(avg_turnover),
        "avg_max_weight": float(avg_max_weight),
        "peak_max_weight": float(peak_max_weight),
        "cumulative": cumulative,
        "drawdown": drawdown,
        "returns": rets,
    }


def _build_panel_membership_mask(panel):
    """패널의 거래일 × 종목 기준 PIT 멤버십 마스크 (편입 전/방출 후 = False)."""
    from .sp500_universe import load_data, build_membership_mask

    close = panel["close"].unstack(level="symbol")
    idx = close.index.normalize()
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    dates, symbols = idx, close.columns
    current_symbols, changes = load_data(str(ROOT / "data"))
    return build_membership_mask(dates, symbols, current_symbols, changes)


def backtest_alpha(expression, settings):
    """식과 세팅을 받아 metrics dict 반환. 사이트에서 호출하는 진입점.

    PIT 유니버스: 그날 S&P 500 멤버가 아니던 구간은 비중 0 으로 처리.
    (편입 전 = 미보유, 방출 후 = 청산)
    """
    panel, fundamentals, sector_map, subindustry_map = load_backtest_data()
    mask = _build_panel_membership_mask(panel)
    weights = evaluate(expression, panel, fundamentals, sector_map, settings,
                       return_full=True, universe_mask=mask, subindustry_map=subindustry_map)
    delay = int(settings.get("delay", 1))
    returns = run_backtest(weights, panel, delay=delay)
    metrics = compute_metrics(returns, weights)
    metrics["weights"] = weights
    return metrics
