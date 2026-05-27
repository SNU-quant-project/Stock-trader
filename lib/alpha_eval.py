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

FALLBACK_LAG_DAYS = 45  # announcement_date 없을 때 보수적 fallback


def _build_pit_fundamentals(fundamentals, dates, symbols, fallback_lag=FALLBACK_LAG_DAYS):
    """분기별 (symbol, quarter_end) → 거래일별 PIT (date × symbol) per field.

    각 거래일 t 에 대해 발표일 ≤ t 를 만족하는 가장 최근 분기 데이터만 사용.
    발표일: fundamentals 에 'announcement_date' 컬럼 있으면 그걸 사용 (정확),
            없으면 quarter_end + fallback_lag 일 (보수적).
    """
    if fundamentals is None or fundamentals.empty:
        return {}

    qdf = fundamentals.reset_index()
    # available = 실제 발표일 (있으면) 또는 quarter_end + lag
    fallback = qdf["quarter_end"] + pd.Timedelta(days=fallback_lag)
    if "announcement_date" in qdf.columns:
        ann = pd.to_datetime(qdf["announcement_date"], errors="coerce")
        # tz 정리
        if hasattr(ann.dtype, "tz") and ann.dt.tz is not None:
            ann = ann.dt.tz_localize(None)
        qdf["available"] = ann.fillna(fallback)
    else:
        qdf["available"] = fallback
    qdf = qdf.sort_values("available").reset_index(drop=True)

    # 거래일 × 종목 매트릭스 — merge_asof 는 left_on (date) 기준 정렬 필요
    date_sym = pd.MultiIndex.from_product(
        [dates, symbols], names=["date", "symbol"]
    ).to_frame(index=False).sort_values("date").reset_index(drop=True)

    merged = pd.merge_asof(
        date_sym, qdf,
        left_on="date", right_on="available",
        by="symbol",
        direction="backward",
    )

    # announcement_date 는 메타데이터, fund 필드에서 제외
    fields = [c for c in fundamentals.columns if c != "announcement_date"]
    result = {}
    for field in fields:
        wide = merged.pivot(index="date", columns="symbol", values=field)
        wide = wide.reindex(index=dates, columns=symbols)
        result[field] = wide.astype(float)
    return result


def build_namespace(panel, fundamentals, sector_series):
    """eval 에 넘길 변수 namespace 만들기."""
    close = panel["close"].unstack(level="symbol")
    open_ = panel["open"].unstack(level="symbol")
    high = panel["high"].unstack(level="symbol") if "high" in panel.columns else close
    low = panel["low"].unstack(level="symbol") if "low" in panel.columns else close
    volume = panel["volume"].unstack(level="symbol") if "volume" in panel.columns else close

    # 인덱스를 date 로 (timezone 제거)
    for df in (close, open_, high, low, volume):
        idx = df.index.normalize()
        if hasattr(idx, "tz") and idx.tz is not None:
            idx = idx.tz_localize(None)
        df.index = idx

    dates = close.index
    symbols = close.columns

    # === Fundamental: 분기별 시계열 → PIT (각 거래일에 그 시점 발표된 가장 최근 분기) ===
    fund_broadcast = _build_pit_fundamentals(fundamentals, dates, symbols)

    # === 가격에 따라 매일 변하는 derived fundamentals ===
    if "shares" in fund_broadcast:
        shares_df = fund_broadcast["shares"]
        fund_broadcast["cap"] = shares_df * close
        if "eps" in fund_broadcast:
            fund_broadcast["pe"] = close / fund_broadcast["eps"].replace(0, np.nan)
        if "equity" in fund_broadcast:
            # book_value per share = equity / shares → pb = close / (equity/shares)
            bps = fund_broadcast["equity"] / shares_df.replace(0, np.nan)
            fund_broadcast["book_value"] = bps
            fund_broadcast["pb"] = close / bps.replace(0, np.nan)
        if "revenue" in fund_broadcast:
            fund_broadcast["ps"] = (shares_df * close) / fund_broadcast["revenue"].replace(0, np.nan)
        if "ni" in fund_broadcast:
            # ROE = NI / equity
            if "equity" in fund_broadcast:
                fund_broadcast["roe"] = fund_broadcast["ni"] / fund_broadcast["equity"].replace(0, np.nan)
        if "assets" in fund_broadcast:
            if "ni" in fund_broadcast:
                fund_broadcast["roa"] = fund_broadcast["ni"] / fund_broadcast["assets"].replace(0, np.nan)

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


def evaluate(expression, panel, fundamentals, sector_map, settings=None, return_full=False):
    """expression 을 평가해서 weight 반환.

    settings:
      - neutralization: "Sector" | "Cap Bucket" | "Sector + Cap Bucket" | "Market" | "None"
      - decay: int (linear decay days, 0=skip)
      - truncation: float (0.0~0.20, 0=skip)
      - delay: 1 (기본; D-1 데이터로 D 진입)

    return_full=False (기본): 마지막 거래일 Series 반환
    return_full=True: 전체 날짜 DataFrame 반환 (백테스팅용)
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

    # === 5. Delay ===
    # raw[t] 는 t 일자 close 까지 본 알파.
    # 라이브 봇: 마지막 행이 어제(D-1)자 알파 → 오늘(D) 시가 진입. shift 불필요.
    # 백테스트: backtest 함수에서 weights.shift(delay) 처리해 lookahead 회피.

    # === 6. Normalize |sum|=1 (각 날짜) ===
    abs_sum = raw.abs().sum(axis=1).replace(0, np.nan)
    full = raw.div(abs_sum, axis=0)

    if return_full:
        return full.dropna(how="all")

    last = full.iloc[-1].dropna()
    return last
