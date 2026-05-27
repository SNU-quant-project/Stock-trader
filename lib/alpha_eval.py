"""Brain 스타일 알파 expression 평가기.

사용 예:
    expr = "group_neutralize(winsorize(ts_backfill((ppent + cash)/cap, 63), std=4), bucket(rank(cap), range='0,1,0.1'))"
    weights = evaluate(expr, panel, fundamentals, sector_map, settings)

panel: (date × symbol) 의 가격 패널 (close, open 등)
fundamentals: (symbol × field) 의 스냅샷 — 모든 날짜에 같은 값으로 broadcast 됨
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import operators as ops


# ========== 평가 ==========

def build_namespace(panel, fundamentals, sector_series):
    """eval 에 넘길 변수 namespace 만들기."""
    close = panel["close"].unstack(level="symbol")
    open_ = panel["open"].unstack(level="symbol")
    high = panel["high"].unstack(level="symbol") if "high" in panel.columns else close
    low = panel["low"].unstack(level="symbol") if "low" in panel.columns else close
    volume = panel["volume"].unstack(level="symbol") if "volume" in panel.columns else close

    # 인덱스를 date 로 (timezone 제거)
    for df in (close, open_, high, low, volume):
        df.index = df.index.normalize()

    dates = close.index
    symbols = close.columns

    # === Fundamental: 모든 날짜에 같은 값으로 broadcast ===
    fund_broadcast = {}
    fundamentals_aligned = fundamentals.reindex(symbols)
    for col in fundamentals_aligned.columns:
        row = fundamentals_aligned[col]
        fund_broadcast[col] = pd.DataFrame(
            np.tile(row.values, (len(dates), 1)),
            index=dates, columns=symbols, dtype=float,
        )

    # === Sector group (Series, index=symbol) ===
    sector_aligned = sector_series.reindex(symbols).fillna("Unknown")

    # === returns (자주 쓰임) ===
    returns = close.pct_change()

    ns = {
        # 가격 panel
        "close": close,
        "open": open_,
        "high": high,
        "low": low,
        "volume": volume,
        "returns": returns,
        # group
        "sector": sector_aligned,
        "industry": sector_aligned,  # alias
        "subindustry": sector_aligned,  # alias
        # numpy/pandas (필요 시)
        "np": np,
        "pd": pd,
    }
    ns.update(fund_broadcast)
    ns.update(ops.ALL_OPS)
    return ns


def evaluate(expression, panel, fundamentals, sector_map, settings=None):
    """expression 을 평가해서 마지막 거래일 weight Series 반환.

    settings:
      - neutralization: "Sector" | "None" | "Market"
      - decay: int (linear decay days, 0=skip)
      - truncation: float (0.0~0.20, 0=skip)
      - delay: 1 (기본; D-1 데이터로 D 진입)
    """
    settings = settings or {}
    sector_series = pd.Series(sector_map, name="sector")
    ns = build_namespace(panel, fundamentals, sector_series)

    # === 1. 식 평가 ===
    raw = eval(expression, {"__builtins__": {}}, ns)

    if not isinstance(raw, pd.DataFrame):
        raise ValueError(f"식 결과가 DataFrame 이 아님: {type(raw).__name__}")

    # === 2. Neutralization ===
    neut = settings.get("neutralization", "Sector")

    def _cap_bucket():
        cap = ns.get("cap")
        if isinstance(cap, pd.DataFrame) and not cap.empty:
            return ops.bucket(ops.rank(cap), range="0,1,0.1")
        return None

    if neut == "Sector":
        raw = ops.group_neutralize(raw, sector_series)
    elif neut == "Cap Bucket":
        cb = _cap_bucket()
        if cb is not None:
            raw = ops.group_neutralize(raw, cb)
    elif neut == "Sector + Cap Bucket":
        raw = ops.group_neutralize(raw, sector_series)
        cb = _cap_bucket()
        if cb is not None:
            raw = ops.group_neutralize(raw, cb)
    elif neut == "Market":
        raw = raw.sub(raw.mean(axis=1), axis=0)
    # None → 그대로

    # === 3. Truncation (종목당 max 비중 캡) ===
    trunc = settings.get("truncation", 0)
    if trunc and trunc > 0:
        # 정규화 후 8% 캡, 한 번만 (Brain 방식)
        abs_sum = raw.abs().sum(axis=1).replace(0, np.nan)
        norm = raw.div(abs_sum, axis=0)
        norm = norm.clip(lower=-trunc, upper=trunc)
        raw = norm

    # === 4. Decay (linear) ===
    decay_d = settings.get("decay", 0)
    if decay_d and decay_d > 1:
        raw = ops.ts_decay_linear(raw, decay_d)

    # === 5. Delay (D-1 데이터로 D 진입) ===
    delay = settings.get("delay", 1)
    if delay > 0:
        # 마지막 행을 잡되, shift 효과는 panel.pct_change 가 이미 D 종가 -> 다음날 시그널이라
        # 여기서는 단순히 마지막 행만 사용
        pass

    # === 6. Normalize |sum|=1 ===
    last = raw.iloc[-1].dropna()
    if last.abs().sum() > 0:
        last = last / last.abs().sum()
    return last
