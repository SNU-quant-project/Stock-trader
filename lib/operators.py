"""WorldQuant Brain 스타일 operator 라이브러리 (Python 구현).

데이터 모델:
  - 모든 panel 변수는 (date × symbol) DataFrame
  - Group 은 매 시점 동일하면 Series (index=symbol), 시점별 다르면 DataFrame
  - cross-sectional operator 는 각 row (= 한 시점) 단위로 동작
"""

import numpy as np
import pandas as pd


# ========== Arithmetic ==========

def add(x, y, filter=False):
    if filter:
        x = x.fillna(0) if hasattr(x, "fillna") else np.nan_to_num(x)
        y = y.fillna(0) if hasattr(y, "fillna") else np.nan_to_num(y)
    return x + y


def subtract(x, y, filter=False):
    if filter:
        x = x.fillna(0) if hasattr(x, "fillna") else np.nan_to_num(x)
        y = y.fillna(0) if hasattr(y, "fillna") else np.nan_to_num(y)
    return x - y


def multiply(*args, filter=False):
    out = args[0]
    if filter and hasattr(out, "fillna"):
        out = out.fillna(0)
    for a in args[1:]:
        if filter and hasattr(a, "fillna"):
            a = a.fillna(0)
        out = out * a
    return out


def divide(x, y):
    return x / y


def log(x):
    return np.log(x)


def sqrt(x):
    return np.sqrt(x.abs()) if hasattr(x, "abs") else np.sqrt(np.abs(x))


def abs_(x):
    return x.abs() if hasattr(x, "abs") else np.abs(x)


def sign(x):
    return np.sign(x)


def signed_power(x, y):
    return np.sign(x) * (np.abs(x) ** y)


def reverse(x):
    return -x


def power(x, y):
    return x ** y


def inverse(x):
    return 1 / x


def _stack(*args):
    return pd.concat([a.stack() if isinstance(a, pd.DataFrame) else pd.Series([a]) for a in args])


def max_(*args):
    # DataFrame 들이면 element-wise max
    if all(isinstance(a, pd.DataFrame) for a in args):
        return pd.concat([a.stack() for a in args], axis=1).max(axis=1).unstack()
    return np.maximum.reduce(args)


def min_(*args):
    if all(isinstance(a, pd.DataFrame) for a in args):
        return pd.concat([a.stack() for a in args], axis=1).min(axis=1).unstack()
    return np.minimum.reduce(args)


def to_nan(x, value=0, reverse=False):
    if reverse:
        return x.fillna(value) if hasattr(x, "fillna") else np.where(np.isnan(x), value, x)
    return x.where(x != value) if hasattr(x, "where") else np.where(x == value, np.nan, x)


# ========== Logical ==========

def is_nan(x):
    return x.isna() if hasattr(x, "isna") else np.isnan(x)


def if_else(cond, a, b):
    """cond 가 truthy 면 a, 아니면 b."""
    if isinstance(cond, pd.DataFrame):
        result = pd.DataFrame(np.where(cond, a, b), index=cond.index, columns=cond.columns)
        return result
    if isinstance(cond, pd.Series):
        return pd.Series(np.where(cond, a, b), index=cond.index)
    return a if cond else b


# ========== Cross Sectional ==========

def rank(x, rate=2):
    """Cross-sectional rank → 0~1."""
    if isinstance(x, pd.DataFrame):
        return x.rank(axis=1, pct=True)
    return x.rank(pct=True)


def winsorize(x, std=4):
    """std 배 이상 outlier 자르기."""
    if isinstance(x, pd.DataFrame):
        m = x.mean(axis=1)
        s = x.std(axis=1)
        lower = m - std * s
        upper = m + std * s
        return x.sub(0, axis=0).clip(lower=lower, upper=upper, axis=0)
    m, s = x.mean(), x.std()
    return x.clip(lower=m - std * s, upper=m + std * s)


def zscore(x):
    if isinstance(x, pd.DataFrame):
        return x.sub(x.mean(axis=1), axis=0).div(x.std(axis=1), axis=0)
    return (x - x.mean()) / x.std()


def normalize(x, useStd=False, limit=0.0):
    if isinstance(x, pd.DataFrame):
        result = x.sub(x.mean(axis=1), axis=0)
        if useStd:
            result = result.div(result.std(axis=1), axis=0)
    else:
        result = x - x.mean()
        if useStd:
            result = result / result.std()
    if limit > 0:
        result = result.clip(-limit, limit)
    return result


def scale(x, scale=1, longscale=1, shortscale=1):
    """|sum|=scale 로 정규화. long/short 분리 스케일 가능."""
    if isinstance(x, pd.DataFrame):
        pos = x.clip(lower=0)
        neg = x.clip(upper=0)
        pos_sum = pos.sum(axis=1)
        neg_sum = neg.abs().sum(axis=1)
        out = x.copy()
        if longscale != 1:
            out = out.where(out <= 0, pos.div(pos_sum, axis=0) * longscale)
        if shortscale != 1:
            out = out.where(out >= 0, -neg.abs().div(neg_sum, axis=0) * shortscale)
        if longscale == 1 and shortscale == 1:
            abs_sum = x.abs().sum(axis=1)
            out = x.div(abs_sum, axis=0) * scale
        return out
    return x / x.abs().sum() * scale


def quantile(x, driver="gaussian", sigma=1.0):
    from scipy.stats import norm, cauchy
    r = rank(x).clip(1e-3, 1 - 1e-3)
    if driver == "gaussian":
        return r.map(norm.ppf) if isinstance(r, pd.Series) else r.apply(norm.ppf) * sigma
    if driver == "uniform":
        return r - 0.5
    if driver == "cauchy":
        return r.map(cauchy.ppf) if isinstance(r, pd.Series) else r.apply(cauchy.ppf) * sigma
    return r


def scale_down(x, constant=0):
    if isinstance(x, pd.DataFrame):
        mn = x.min(axis=1)
        mx = x.max(axis=1)
        return (x.sub(mn, axis=0)).div((mx - mn).replace(0, np.nan), axis=0).sub(constant)
    return (x - x.min()) / (x.max() - x.min()) - constant


# ========== Time Series ==========

def ts_mean(x, d):
    return x.rolling(d, min_periods=1).mean()


def ts_sum(x, d):
    return x.rolling(d, min_periods=1).sum()


def ts_std_dev(x, d):
    return x.rolling(d, min_periods=2).std()


def ts_zscore(x, d):
    return (x - ts_mean(x, d)) / ts_std_dev(x, d)


def ts_rank(x, d, constant=0):
    def f(s):
        if pd.isna(s.iloc[-1]):
            return np.nan
        return s.rank(pct=True).iloc[-1] + constant
    return x.rolling(d, min_periods=2).apply(f, raw=False)


def ts_delta(x, d):
    return x - x.shift(d)


def ts_delay(x, d):
    return x.shift(d)


def ts_backfill(x, lookback=5, k=1):
    """NaN 을 최근 lookback 일 이내 valid 값으로 채움."""
    if isinstance(x, (pd.Series, pd.DataFrame)):
        return x.ffill(limit=lookback)
    return x


def ts_min(x, d):
    return x.rolling(d, min_periods=1).min()


def ts_max(x, d):
    return x.rolling(d, min_periods=1).max()


def ts_av_diff(x, d):
    return x - ts_mean(x, d)


def ts_product(x, d):
    return x.rolling(d, min_periods=1).apply(np.prod, raw=True)


def ts_corr(x, y, d):
    if isinstance(x, pd.DataFrame):
        return x.rolling(d).corr(y)
    return x.rolling(d).corr(y)


def ts_covariance(y, x, d):
    return y.rolling(d).cov(x)


def ts_decay_linear(x, d, dense=False):
    weights = np.arange(d, 0, -1, dtype=float)
    weights = weights / weights.sum()
    def f(s):
        v = s.values
        n = len(v)
        if n == 0:
            return np.nan
        w = weights[-n:][::-1]
        valid = ~np.isnan(v)
        if not valid.any():
            return np.nan
        w_sum = w[valid].sum()
        return (v[valid] * w[valid]).sum() / w_sum
    return x.rolling(d, min_periods=1).apply(f, raw=False)


def ts_scale(x, d, constant=0):
    mn = ts_min(x, d)
    mx = ts_max(x, d)
    return (x - mn) / (mx - mn).replace(0, np.nan) + constant


def ts_arg_max(x, d):
    return x.rolling(d).apply(lambda s: d - 1 - s.values.argmax(), raw=False)


def ts_arg_min(x, d):
    return x.rolling(d).apply(lambda s: d - 1 - s.values.argmin(), raw=False)


def ts_count_nans(x, d):
    return x.isna().rolling(d, min_periods=1).sum()


def hump(x, hump_val=0.01):
    """변동이 hump 미만이면 hold."""
    if isinstance(x, pd.DataFrame):
        out = x.copy()
        for i in range(1, len(out)):
            change = (out.iloc[i] - out.iloc[i - 1]).abs()
            mask = change < hump_val
            out.iloc[i] = out.iloc[i - 1].where(mask, out.iloc[i])
        return out
    return x


# ========== Group ==========

def _align_group(x, group):
    """group 이 Series 면 x 의 행마다 broadcast. DataFrame 이면 그대로."""
    if isinstance(group, pd.Series):
        # x columns 와 정렬
        return group.reindex(x.columns)
    return group


def group_neutralize(x, group):
    """같은 group 안에서 평균 빼기."""
    if isinstance(x, pd.DataFrame):
        g = _align_group(x, group)
        if isinstance(g, pd.Series):
            # 시점 무관 그룹
            result = x.copy()
            for grp_val in g.dropna().unique():
                cols = g[g == grp_val].index
                cols = [c for c in cols if c in x.columns]
                if cols:
                    result[cols] = x[cols].sub(x[cols].mean(axis=1), axis=0)
            return result
        else:
            # 시점별 그룹 (DataFrame g)
            return _apply_rowwise_group(x, g, lambda s, gs: s - s.groupby(gs).transform("mean"))
    return pd.Series(x).sub(pd.Series(x).groupby(group).transform("mean"))


def group_rank(x, group):
    if isinstance(x, pd.DataFrame):
        g = _align_group(x, group)
        if isinstance(g, pd.Series):
            return _apply_rowwise_group_static(x, g, lambda s, gs: s.groupby(gs).rank(pct=True))
        return _apply_rowwise_group(x, g, lambda s, gs: s.groupby(gs).rank(pct=True))
    return pd.Series(x).groupby(group).rank(pct=True)


def group_zscore(x, group):
    if isinstance(x, pd.DataFrame):
        g = _align_group(x, group)
        if isinstance(g, pd.Series):
            return _apply_rowwise_group_static(
                x, g,
                lambda s, gs: (s - s.groupby(gs).transform("mean")) / s.groupby(gs).transform("std"),
            )
        return _apply_rowwise_group(
            x, g,
            lambda s, gs: (s - s.groupby(gs).transform("mean")) / s.groupby(gs).transform("std"),
        )
    s = pd.Series(x)
    return (s - s.groupby(group).transform("mean")) / s.groupby(group).transform("std")


def group_mean(x, group, weight=None):
    if isinstance(x, pd.DataFrame):
        g = _align_group(x, group)
        if isinstance(g, pd.Series):
            return _apply_rowwise_group_static(x, g, lambda s, gs: s.groupby(gs).transform("mean"))
        return _apply_rowwise_group(x, g, lambda s, gs: s.groupby(gs).transform("mean"))
    return pd.Series(x).groupby(group).transform("mean")


def group_min(x, group):
    if isinstance(x, pd.DataFrame):
        g = _align_group(x, group)
        if isinstance(g, pd.Series):
            return _apply_rowwise_group_static(x, g, lambda s, gs: s.groupby(gs).transform("min"))
        return _apply_rowwise_group(x, g, lambda s, gs: s.groupby(gs).transform("min"))
    return pd.Series(x).groupby(group).transform("min")


def group_max(x, group):
    if isinstance(x, pd.DataFrame):
        g = _align_group(x, group)
        if isinstance(g, pd.Series):
            return _apply_rowwise_group_static(x, g, lambda s, gs: s.groupby(gs).transform("max"))
        return _apply_rowwise_group(x, g, lambda s, gs: s.groupby(gs).transform("max"))
    return pd.Series(x).groupby(group).transform("max")


def group_scale(x, group):
    """(x - groupmin) / (groupmax - groupmin) — 그룹 내 0~1 정규화."""
    return (x - group_min(x, group)) / (group_max(x, group) - group_min(x, group)).replace(0, np.nan)


def _apply_rowwise_group_static(x, g, fn):
    """g 가 시점 무관 Series 인 경우 — 각 row 에 fn 적용."""
    result = pd.DataFrame(index=x.index, columns=x.columns, dtype=float)
    for date in x.index:
        s = x.loc[date]
        result.loc[date] = fn(s, g).values
    return result


def _apply_rowwise_group(x, g, fn):
    """g 가 시점별 DataFrame 인 경우."""
    result = pd.DataFrame(index=x.index, columns=x.columns, dtype=float)
    for date in x.index:
        s = x.loc[date]
        gs = g.loc[date] if date in g.index else g.iloc[-1]
        result.loc[date] = fn(s, gs).values
    return result


# ========== Transformational ==========

def bucket(x, range=None, buckets=None):
    """float 값을 bucket index 로 변환.
    range='0,1,0.1' → [0, 0.1, 0.2, ..., 1.0] edges
    buckets='2,5,6,7,10' → 직접 edges 지정
    """
    if range is not None:
        if isinstance(range, str):
            parts = [float(p.strip()) for p in range.split(",")]
            start, end, step = parts
            edges = list(np.arange(start, end + step / 2, step))
        else:
            edges = list(range)
    elif buckets is not None:
        if isinstance(buckets, str):
            edges = [float(p.strip()) for p in buckets.split(",")]
        else:
            edges = list(buckets)
    else:
        edges = list(np.linspace(0, 1, 11))

    if isinstance(x, pd.DataFrame):
        return x.apply(lambda col: pd.cut(col, bins=edges, labels=False, include_lowest=True))
    if isinstance(x, pd.Series):
        return pd.cut(x, bins=edges, labels=False, include_lowest=True)
    return np.digitize(x, edges) - 1


def trade_when(x, alpha, close):
    """trade 조건 x 가 true 일 때 alpha 유지, close 가 true 면 nan (포지션 종료)."""
    out = alpha.copy()
    if hasattr(close, "values"):
        out = out.where(~close.astype(bool), np.nan)
    if hasattr(x, "values"):
        out = out.where(x.astype(bool), out.shift(1))
    return out


def densify(x):
    """그룹 인덱스 압축 — 우리 케이스에선 그대로."""
    return x


# ========== 공개 namespace ==========

ALL_OPS = {
    # arithmetic
    "add": add, "subtract": subtract, "multiply": multiply, "divide": divide,
    "log": log, "sqrt": sqrt, "abs": abs_, "sign": sign,
    "signed_power": signed_power, "reverse": reverse, "power": power,
    "inverse": inverse, "max": max_, "min": min_, "to_nan": to_nan,
    # logical
    "is_nan": is_nan, "if_else": if_else,
    # cross sectional
    "rank": rank, "winsorize": winsorize, "zscore": zscore,
    "normalize": normalize, "scale": scale, "quantile": quantile,
    "scale_down": scale_down,
    # time series
    "ts_mean": ts_mean, "ts_sum": ts_sum, "ts_std_dev": ts_std_dev,
    "ts_zscore": ts_zscore, "ts_rank": ts_rank, "ts_delta": ts_delta,
    "ts_delay": ts_delay, "ts_backfill": ts_backfill, "ts_min": ts_min,
    "ts_max": ts_max, "ts_av_diff": ts_av_diff, "ts_product": ts_product,
    "ts_corr": ts_corr, "ts_covariance": ts_covariance,
    "ts_decay_linear": ts_decay_linear, "ts_scale": ts_scale,
    "ts_arg_max": ts_arg_max, "ts_arg_min": ts_arg_min,
    "ts_count_nans": ts_count_nans, "hump": hump,
    # group
    "group_neutralize": group_neutralize, "group_rank": group_rank,
    "group_zscore": group_zscore, "group_mean": group_mean,
    "group_min": group_min, "group_max": group_max, "group_scale": group_scale,
    # transformational
    "bucket": bucket, "trade_when": trade_when, "densify": densify,
}
