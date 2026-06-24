"""KOSPI 모의 트레이딩 — 데이터 로더 + 고정 long-only 알파 평가/백테스트.

미국 파이프라인(lib/alpha_eval, lib/backtest)을 그대로 재사용 — 시장만 KOSPI.
페이지가 필요로 하는 것: 현재 알파, 현재 포지션, 지수 대비 1년 수익률 비교.
"""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd

from .alpha_eval import evaluate
from .backtest import run_backtest

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"

# 사용자가 지정한 long-only 알파 (그대로)
ALPHA = (
    "x = zscore(ts_backfill((ppent + cash)/cap, 63));\n"
    "core = signed_power(winsorize(max(x, 0), std=4), 2);\n"
    "quality = group_rank(ts_zscore(cashflow_op/assets, 252), sector);\n"
    "cap_bucket = bucket(rank(cap), range='0,1,0.2');\n"
    "alpha = max(group_neutralize(core * quality, cap_bucket), 0)"
)
SETTINGS = {"region": "KOR", "universe": "KOSPI", "neutralization": "None",
            "delay": 1, "decay": 1, "truncation": 0.08}
TRADING_DAYS_1Y = 252


def load_kospi_data():
    panel = pd.read_parquet(DATA / "kospi_panel.parquet")
    fundamentals = pd.read_parquet(DATA / "kospi_fundamentals.parquet")
    uni = pd.read_csv(DATA / "kospi_universe.csv", dtype={"Symbol": str})
    uni["Symbol"] = uni["Symbol"].str.zfill(6)
    name_map = dict(zip(uni["Symbol"], uni["Name"]))
    sec = pd.read_csv(DATA / "kospi_sectors.csv", dtype={"Symbol": str})
    sec["Symbol"] = sec["Symbol"].str.zfill(6)
    sector_map = dict(zip(sec["Symbol"], sec["Sector"].astype(str)))
    return panel, fundamentals, sector_map, name_map


def _kospi_index():
    idx = pd.read_csv(DATA / "kospi_index.csv", parse_dates=["date"]).set_index("date")["close"]
    idx.index = pd.DatetimeIndex(idx.index).normalize()
    return idx


def build_page_data():
    """KOSPI 페이지용 데이터: 현재 알파/세팅 + 현재 포지션 + 1년 지수비교."""
    panel, fundamentals, sector_map, name_map = load_kospi_data()
    weights = evaluate(ALPHA, panel, fundamentals, sector_map, SETTINGS, return_full=True)

    close = panel["close"].unstack(level="symbol")
    close.index = pd.DatetimeIndex(close.index).normalize()

    # --- 현재 포지션 (마지막 거래일 목표 비중, long-only) ---
    last_date = weights.index[-1]
    w = weights.iloc[-1].dropna()
    w = w[w > 1e-6].sort_values(ascending=False)
    last_px = close.iloc[-1]
    positions = [{
        "sym": s, "name": name_map.get(s, s), "sector": str(sector_map.get(s, "—")),
        "weight": float(w[s]), "price": float(last_px.get(s, float("nan"))),
    } for s in w.index]

    # --- 1년 백테스트 (long-only) vs KOSPI 지수 ---
    port_ret = run_backtest(weights, panel, delay=SETTINGS["delay"]).dropna()
    port_ret = port_ret[port_ret != 0]
    win = port_ret.index[-TRADING_DAYS_1Y:]
    pr = port_ret.reindex(win).fillna(0.0)
    port_cum = ((1 + pr).cumprod() - 1) * 100

    idx = _kospi_index()
    win_norm = pd.DatetimeIndex(win).normalize()
    idx_al = idx.reindex(win_norm, method="ffill")
    base = idx_al.dropna().iloc[0] if idx_al.notna().any() else np.nan
    kospi_cum = (idx_al / base - 1) * 100

    fmt = "%m/%d"
    labels = [pd.Timestamp(d).strftime(fmt) for d in win_norm]
    series = [
        {"name": "내 포트폴리오", "values": [round(float(v), 2) for v in port_cum.values], "color": "var(--accent)"},
        {"name": "KOSPI", "values": [None if pd.isna(v) else round(float(v), 2) for v in kospi_cum.values], "color": "#2f7ce0"},
    ]
    port_final = float(port_cum.iloc[-1]) if len(port_cum) else 0.0
    kospi_final = float(kospi_cum.dropna().iloc[-1]) if kospi_cum.notna().any() else 0.0

    return {
        "alpha": ALPHA,
        "settings": {"Region": "KOR", "Universe": "KOSPI(시총상위 200)", "Delay": 1,
                     "Decay": 1, "Truncation": 0.08, "Neutralization": "None"},
        "asOf": pd.Timestamp(last_date).strftime("%Y-%m-%d"),
        "positions": positions,
        "nPositions": len(positions),
        "compare": {"labels": labels, "series": series},
        "summary": {"portfolio1y": round(port_final, 2), "kospi1y": round(kospi_final, 2),
                    "excess1y": round(port_final - kospi_final, 2),
                    "days": len(labels)},
    }
