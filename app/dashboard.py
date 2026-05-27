"""Streamlit 대시보드: 봇 상태, 계좌, 포지션, 알파 코드 시각화.

실행:
  streamlit run app/dashboard.py
  streamlit run app/dashboard.py --server.port 8081 --server.address 0.0.0.0  # EC2 외부 노출
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from alpaca.trading.client import TradingClient


# === Setup ===

st.set_page_config(page_title="SNU Quant — Alpha Bot", layout="wide")

load_dotenv(ROOT / ".env")


@st.cache_resource
def get_trading_client():
    return TradingClient(
        os.environ["ALPACA_API_KEY"],
        os.environ["ALPACA_SECRET_KEY"],
        paper=True,
    )


@st.cache_data(ttl=60)
def fetch_account_state():
    tc = get_trading_client()
    acct = tc.get_account()
    positions = tc.get_all_positions()

    pos_rows = []
    for p in positions:
        pos_rows.append({
            "symbol": p.symbol,
            "qty": float(p.qty),
            "avg_entry": float(p.avg_entry_price),
            "current_price": float(p.current_price) if p.current_price else None,
            "market_value": float(p.market_value),
            "unrealized_pl": float(p.unrealized_pl),
            "unrealized_plpc": float(p.unrealized_plpc),
            "side": "long" if float(p.qty) > 0 else "short",
        })
    pos_df = pd.DataFrame(pos_rows) if pos_rows else pd.DataFrame()

    return {
        "equity": float(acct.equity),
        "cash": float(acct.cash),
        "buying_power": float(acct.buying_power),
        "last_equity": float(acct.last_equity),
        "status": str(acct.status),
        "positions": pos_df,
    }


@st.cache_data(ttl=60)
def fetch_portfolio_history():
    """Alpaca portfolio history API → 일별 자산 시계열."""
    tc = get_trading_client()
    try:
        hist = tc.get_portfolio_history(
            history_filter={"period": "1M", "timeframe": "1D"}
        )
    except Exception:
        try:
            from alpaca.trading.requests import GetPortfolioHistoryRequest
            req = GetPortfolioHistoryRequest(period="1M", timeframe="1D")
            hist = tc.get_portfolio_history(history_filter=req)
        except Exception as e:
            return None, str(e)

    df = pd.DataFrame({
        "timestamp": pd.to_datetime(hist.timestamp, unit="s"),
        "equity": hist.equity,
        "profit_loss": hist.profit_loss,
        "profit_loss_pct": hist.profit_loss_pct,
    })
    return df, None


def load_recent_logs(n=10):
    log_dir = ROOT / "bot" / "logs"
    if not log_dir.exists():
        return []
    files = sorted(log_dir.glob("run_*.json"), reverse=True)[:n]
    logs = []
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                logs.append((f.name, json.load(fh)))
        except Exception:
            continue
    return logs


# === UI ===

st.title("SNU Quant — Alpha Bot Dashboard")
st.caption("S&P 500 단기 평균회귀 알파 — Alpaca 페이퍼 트레이딩")

# === 사이드바: 알파 세팅 (UI 만) ===
with st.sidebar:
    st.header("Alpha Settings")
    st.caption("UI 만 동작. 실제 적용은 다음 버전에서.")

    st.subheader("Decay")
    decay_enabled = st.checkbox("Enable Decay", value=False)
    decay_days = st.slider("Decay days", 1, 10, 4, disabled=not decay_enabled)
    st.caption("D-1:D-2:... 가중평균 일수")

    st.subheader("Truncation")
    trunc_enabled = st.checkbox("Enable Truncation", value=False)
    trunc_limit = st.slider("Limit (%)", 1, 20, 8, disabled=not trunc_enabled) / 100
    st.caption("종목당 최대 비중 캡")

    st.divider()
    if st.button("Refresh"):
        st.cache_data.clear()
        st.rerun()

# === 계좌 상태 ===
try:
    state = fetch_account_state()
except Exception as e:
    st.error(f"Alpaca 연결 실패: {e}")
    st.stop()

equity = state["equity"]
cash = state["cash"]
last_equity = state["last_equity"]
daily_return = (equity - last_equity) / last_equity if last_equity else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Equity", f"${equity:,.2f}", f"{daily_return:+.2%} (vs prev close)")
c2.metric("Cash", f"${cash:,.2f}")
c3.metric("Positions", len(state["positions"]) if not state["positions"].empty else 0)
c4.metric("Status", state["status"])

# === 자산 차트 ===
st.subheader("Equity Curve")
hist_df, err = fetch_portfolio_history()
if err or hist_df is None or hist_df.empty:
    st.info("아직 자산 히스토리가 없거나 API 호출 실패. 봇이 한 번 이상 돌고 거래일이 지나야 곡선이 그려집니다.")
    if err:
        st.caption(f"({err})")
else:
    base = hist_df["equity"].iloc[0]
    hist_df["cum_return"] = hist_df["equity"] / base - 1

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist_df["timestamp"],
        y=hist_df["equity"],
        mode="lines+markers",
        name="Equity ($)",
        line=dict(color="#2ecc71", width=2),
    ))
    fig.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=10, b=0),
        yaxis_title="Equity ($)",
        xaxis_title="",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    total_return = hist_df["equity"].iloc[-1] / base - 1
    st.caption(f"시작 ${base:,.2f} → 현재 ${equity:,.2f}  ({total_return:+.2%})")

# === 탭: 포지션 / 알파 코드 / 로그 ===
tab1, tab2, tab3 = st.tabs(["Positions", "Alpha Code", "Bot Logs"])

with tab1:
    pos_df = state["positions"]
    if pos_df.empty:
        st.info("현재 보유 포지션 없음. 봇이 첫 주문을 넣은 뒤 장이 열리면 채워집니다.")
    else:
        gross = pos_df["market_value"].abs().sum()
        pos_df["weight"] = pos_df["market_value"] / gross

        col_long, col_short = st.columns(2)
        with col_long:
            st.markdown("### Long")
            longs = pos_df[pos_df["side"] == "long"].sort_values("weight", ascending=False)
            st.dataframe(
                longs[["symbol", "qty", "avg_entry", "current_price",
                       "market_value", "unrealized_plpc", "weight"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "qty": st.column_config.NumberColumn(format="%.0f"),
                    "avg_entry": st.column_config.NumberColumn(format="$%.2f"),
                    "current_price": st.column_config.NumberColumn(format="$%.2f"),
                    "market_value": st.column_config.NumberColumn(format="$%.0f"),
                    "unrealized_plpc": st.column_config.NumberColumn(format="%.2f%%"),
                    "weight": st.column_config.NumberColumn(format="%.2f%%"),
                },
            )
        with col_short:
            st.markdown("### Short")
            shorts = pos_df[pos_df["side"] == "short"].sort_values("weight")
            st.dataframe(
                shorts[["symbol", "qty", "avg_entry", "current_price",
                        "market_value", "unrealized_plpc", "weight"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "qty": st.column_config.NumberColumn(format="%.0f"),
                    "avg_entry": st.column_config.NumberColumn(format="$%.2f"),
                    "current_price": st.column_config.NumberColumn(format="$%.2f"),
                    "market_value": st.column_config.NumberColumn(format="$%.0f"),
                    "unrealized_plpc": st.column_config.NumberColumn(format="%.2f%%"),
                    "weight": st.column_config.NumberColumn(format="%.2f%%"),
                },
            )

with tab2:
    st.markdown("### 현재 돌리는 알파 (`bot/run_alpha.py` 의 `compute_today_weights`)")
    code_file = ROOT / "bot" / "run_alpha.py"
    if code_file.exists():
        full_code = code_file.read_text(encoding="utf-8")
        # compute_today_weights 함수만 잘라내기
        start = full_code.find("def compute_today_weights")
        end = full_code.find("\n\n# ===", start) if start >= 0 else -1
        snippet = full_code[start:end] if start >= 0 and end > start else full_code
        st.code(snippet, language="python")
    else:
        st.warning("bot/run_alpha.py 파일을 찾을 수 없음")

    st.markdown("**Spec**")
    st.markdown("""
    - **Alpha**: `rank(-returns)` — 어제 많이 떨어진 종목을 long, 많이 오른 종목을 short
    - **Neutralization**: GICS Sector (11개 그룹) 내 demean
    - **Decay**: 없음 (단순 버전)
    - **Truncation**: 없음 (단순 버전)
    - **Normalization**: `|sum(weights)| = 1` (gross = equity)
    - **체결**: D-1 종가 데이터로 계산 → D 시가 시장가 진입
    """)

with tab3:
    st.markdown("### 최근 봇 실행 로그")
    logs = load_recent_logs(10)
    if not logs:
        st.info("아직 실행 로그가 없습니다.")
    else:
        for name, log in logs:
            ts = log.get("started_at", name)
            n_orders = len(log.get("orders", {}))
            n_subm = len(log.get("submitted", []))
            n_fail = len(log.get("failed", []))
            dry = "DRY" if log.get("dry_run") else "LIVE"
            with st.expander(f"{ts}  [{dry}]  주문 {n_orders}건 (제출 {n_subm}, 실패 {n_fail})"):
                summary_cols = st.columns(4)
                summary_cols[0].metric("Equity", f"${log.get('equity', 0):,.0f}")
                summary_cols[1].metric("Universe", log.get("universe_size", 0))
                summary_cols[2].metric("Panel last", log.get("panel_last_date", "-"))
                summary_cols[3].metric("Orders", n_orders)

                weights = log.get("weights", {})
                if weights:
                    w_df = pd.DataFrame(
                        [{"symbol": k, "weight": v} for k, v in weights.items()]
                    ).sort_values("weight", ascending=False)
                    st.markdown("**Top 10 Long**")
                    st.dataframe(w_df.head(10), use_container_width=True, hide_index=True)
                    st.markdown("**Top 10 Short**")
                    st.dataframe(w_df.tail(10).iloc[::-1], use_container_width=True, hide_index=True)

st.caption(f"Last refreshed: {datetime.now():%Y-%m-%d %H:%M:%S}")
