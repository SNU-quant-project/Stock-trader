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


@st.cache_data(ttl=3600)
def load_company_map():
    """Symbol → {name, sector} 매핑."""
    df = pd.read_csv(ROOT / "data" / "sp500_current.csv")
    return {
        row["Symbol"]: {"name": row["Security"], "sector": row["GICS Sector"]}
        for _, row in df.iterrows()
    }


def yahoo_url(symbol):
    return f"https://finance.yahoo.com/quote/{symbol}/"


TABLE_STYLE = "width:100%; border-collapse:collapse; font-size:13px;"
LINK_STYLE = "text-decoration:none; color:#1f77b4;"
HEADER_ROW = '<tr style="border-bottom:2px solid #ddd; text-align:left;">'
RA = 'style="text-align:right;"'


def render_position_table(df, side):
    """positions 테이블을 HTML 로 직접 렌더 — 회사명 클릭 시 Yahoo Finance 로 이동."""
    if df.empty:
        st.info(f"No {side} positions.")
        return

    rows = []
    for _, r in df.iterrows():
        url = yahoo_url(r["symbol"])
        plpc = r["unrealized_plpc"] * 100
        color = "#2ecc71" if plpc >= 0 else "#e74c3c"
        rows.append(
            f'<tr>'
            f'<td><b>{r["symbol"]}</b></td>'
            f'<td><a href="{url}" target="_blank" style="{LINK_STYLE}">{r["name"]}</a></td>'
            f'<td style="color:#888;">{r["sector"]}</td>'
            f'<td {RA}>{r["qty"]:.4f}</td>'
            f'<td {RA}>${r["current_price"]:.2f}</td>'
            f'<td {RA}>${r["market_value"]:,.0f}</td>'
            f'<td style="text-align:right; color:{color};">{plpc:+.2f}%</td>'
            f'<td {RA}>{r["weight"]*100:.2f}%</td>'
            f'</tr>'
        )

    header = (f'{HEADER_ROW}<th>Symbol</th><th>Company</th><th>Sector</th>'
              f'<th {RA}>Qty</th><th {RA}>Price</th><th {RA}>Value</th>'
              f'<th {RA}>P/L%</th><th {RA}>Weight</th></tr>')
    html = f'<table style="{TABLE_STYLE}"><thead>{header}</thead><tbody>{"".join(rows)}</tbody></table>'
    st.markdown(html, unsafe_allow_html=True)


def render_weight_table(items, company_map):
    """[(symbol, weight)] 리스트를 회사명 링크 포함 테이블로."""
    rows = []
    for sym, w in items:
        info = company_map.get(sym, {"name": sym, "sector": "Unknown"})
        url = yahoo_url(sym)
        rows.append(
            f'<tr>'
            f'<td><b>{sym}</b></td>'
            f'<td><a href="{url}" target="_blank" style="{LINK_STYLE}">{info["name"]}</a></td>'
            f'<td style="color:#888;">{info["sector"]}</td>'
            f'<td {RA}>{w*100:+.3f}%</td>'
            f'</tr>'
        )
    header = (f'{HEADER_ROW}<th>Symbol</th><th>Company</th><th>Sector</th>'
              f'<th {RA}>Weight</th></tr>')
    html = f'<table style="{TABLE_STYLE}"><thead>{header}</thead><tbody>{"".join(rows)}</tbody></table>'
    st.markdown(html, unsafe_allow_html=True)


@st.cache_data(ttl=60)
def fetch_account_state():
    tc = get_trading_client()
    acct = tc.get_account()
    positions = tc.get_all_positions()
    cmap = load_company_map()

    pos_rows = []
    for p in positions:
        info = cmap.get(p.symbol, {"name": p.symbol, "sector": "Unknown"})
        pos_rows.append({
            "symbol": p.symbol,
            "name": info["name"],
            "sector": info["sector"],
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

        st.caption("회사명을 클릭하면 Yahoo Finance 페이지로 이동합니다.")
        st.markdown(f"### Long ({(pos_df['side']=='long').sum()})")
        longs = pos_df[pos_df["side"] == "long"].sort_values("weight", ascending=False)
        render_position_table(longs, "long")

        st.markdown(f"### Short ({(pos_df['side']=='short').sum()})")
        shorts = pos_df[pos_df["side"] == "short"].sort_values("weight")
        render_position_table(shorts, "short")

with tab2:
    # === Expression (Brain 스타일 dark code block) ===
    st.markdown("### Code")
    expression_html = (
        '<div style="background:#1e1e1e; color:#d4d4d4; padding:16px 20px; '
        'border-radius:6px; font-family:Consolas,Menlo,monospace; font-size:14px; '
        'line-height:1.6;">'
        '<span style="color:#858585;">1</span>&nbsp;&nbsp;&nbsp;'
        '<span style="color:#9cdcfe;">alpha</span> '
        '<span style="color:#d4d4d4;">=</span> '
        '<span style="color:#dcdcaa;">rank</span>'
        '<span style="color:#d4d4d4;">(-</span>'
        '<span style="color:#9cdcfe;">returns</span>'
        '<span style="color:#d4d4d4;">);</span>'
        '</div>'
    )
    st.markdown(expression_html, unsafe_allow_html=True)

    # === Simulation Settings (Brain 스타일 테이블) ===
    st.markdown("### Simulation Settings")
    settings = [
        ("Instrument Type", "Equity"),
        ("Region", "USA"),
        ("Universe", "S&P 500"),
        ("Language", "Fast Expression"),
        ("Decay", "0"),
        ("Delay", "1"),
        ("Truncation", "0"),
        ("Neutralization", "Sector (GICS)"),
        ("Pasteurization", "Off"),
        ("Lookback", "1"),
        ("Max Trade", "OFF"),
        ("Max Position", "OFF"),
    ]
    header_cells = "".join(
        f'<th style="padding:8px 12px; background:#f5f5f5; border-bottom:1px solid #ddd; '
        f'font-size:12px; color:#666; text-align:left; white-space:nowrap;">{k}</th>'
        for k, _ in settings
    )
    body_cells = "".join(
        f'<td style="padding:8px 12px; border-bottom:1px solid #eee; font-size:13px; '
        f'white-space:nowrap;">{v}</td>'
        for _, v in settings
    )
    settings_html = (
        f'<div style="overflow-x:auto;">'
        f'<table style="border-collapse:collapse; font-size:13px;">'
        f'<thead><tr>{header_cells}</tr></thead>'
        f'<tbody><tr>{body_cells}</tr></tbody>'
        f'</table></div>'
    )
    st.markdown(settings_html, unsafe_allow_html=True)

    # === Description ===
    st.markdown("### Description")
    st.markdown("""
어제 가장 많이 떨어진 종목을 long, 가장 많이 오른 종목을 short — **단기 평균회귀 (short-term mean reversion)** 시그널.

- `returns` = (오늘 종가 / 어제 종가) − 1
- `-returns` = 부호 반전: 떨어진 종목이 양수, 오른 종목이 음수
- `rank(x)` = 그날 유니버스 503개 종목 중 cross-sectional 순위 (0~1로 표준화)
- **Sector Neutralization**: 같은 GICS Sector 내에서 평균 0으로 맞춤 → 특정 섹터 베팅 X, 순수 종목 선택 시그널
- **Delay 1**: 어제 종가로 계산해서 오늘 시가에 진입 — lookahead bias 방지
""")

    # === 실제 Python 구현 (참고용) ===
    with st.expander("실제 Python 구현 보기"):
        code_file = ROOT / "bot" / "run_alpha.py"
        if code_file.exists():
            full_code = code_file.read_text(encoding="utf-8")
            start = full_code.find("def compute_today_weights")
            end = full_code.find("\n\n# ===", start) if start >= 0 else -1
            snippet = full_code[start:end] if start >= 0 and end > start else full_code
            st.code(snippet, language="python")

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
                    cmap = load_company_map()
                    sorted_w = sorted(weights.items(), key=lambda x: -x[1])
                    st.caption("회사명을 클릭하면 Yahoo Finance 페이지로 이동합니다.")
                    st.markdown("**Top 10 Long**")
                    render_weight_table(sorted_w[:10], cmap)
                    st.markdown("**Top 10 Short**")
                    render_weight_table(sorted_w[-10:][::-1], cmap)

st.caption(f"Last refreshed: {datetime.now():%Y-%m-%d %H:%M:%S}")
