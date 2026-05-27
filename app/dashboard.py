"""Streamlit 대시보드: 봇 상태, 계좌, 포지션, 알파 코드 시각화.

실행:
  streamlit run app/dashboard.py
  streamlit run app/dashboard.py --server.port 8081 --server.address 0.0.0.0  # EC2 외부 노출
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from alpaca.trading.client import TradingClient

CONFIG_FILE = ROOT / "bot" / "alpha_config.json"


def load_alpha_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {
        "expression": "rank(-returns)",
        "settings": {"neutralization": "Sector", "decay": 0, "truncation": 0, "delay": 1},
        "description": "",
    }


def save_alpha_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


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
def fetch_portfolio_history(period="1M", timeframe="1D"):
    """Alpaca portfolio history API → 일별 자산 시계열."""
    tc = get_trading_client()
    try:
        hist = tc.get_portfolio_history(
            history_filter={"period": period, "timeframe": timeframe}
        )
    except Exception:
        try:
            from alpaca.trading.requests import GetPortfolioHistoryRequest
            req = GetPortfolioHistoryRequest(period=period, timeframe=timeframe)
            hist = tc.get_portfolio_history(history_filter=req)
        except Exception as e:
            return None, str(e)

    df = pd.DataFrame({
        "timestamp": pd.to_datetime(hist.timestamp, unit="s"),
        "equity": hist.equity,
        "profit_loss": hist.profit_loss,
        "profit_loss_pct": hist.profit_loss_pct,
    })
    # 계좌 개설 이전 (equity == 0 또는 NaN) 잘라내기
    df = df[df["equity"].notna() & (df["equity"] > 0)].reset_index(drop=True)
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

# === 사이드바 ===
cfg = load_alpha_config()
with st.sidebar:
    st.header("Current Alpha")
    st.caption("`bot/alpha_config.json`")
    st.code(cfg["expression"], language="javascript")
    s = cfg.get("settings", {})
    st.markdown(
        f"- Neutralization: **{s.get('neutralization', '-')}**\n"
        f"- Decay: **{s.get('decay', 0)}**\n"
        f"- Truncation: **{s.get('truncation', 0)}**\n"
        f"- Delay: **{s.get('delay', 1)}**"
    )
    st.divider()
    if st.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()
    st.caption("알파 식·세팅 수정은 **Alpha Code** 탭에서.")

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
header_col, period_col = st.columns([3, 2])
with header_col:
    st.subheader("Equity Curve")
with period_col:
    period_options = {"1W": "1W", "1M": "1M", "3M": "3M", "1Y": "1Y", "ALL": "all"}
    selected_period = st.radio(
        "기간",
        list(period_options.keys()),
        index=1,  # 1M 기본
        horizontal=True,
        label_visibility="collapsed",
    )

hist_df, err = fetch_portfolio_history(period=period_options[selected_period])
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
    st.markdown("Brain 스타일 expression 으로 알파를 작성하면 봇이 다음 실행 때 그대로 적용합니다.")

    s = cfg.get("settings", {})
    with st.form("alpha_form"):
        st.markdown("### Code")
        new_expr = st.text_area(
            "Expression",
            value=cfg.get("expression", "rank(-returns)"),
            height=120,
            label_visibility="collapsed",
            help="Brain Fast Expression 문법. 예: group_neutralize(rank(-returns), sector)",
        )

        st.markdown("### Simulation Settings")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            new_neut = st.selectbox(
                "Neutralization",
                ["Sector", "Market", "None"],
                index=["Sector", "Market", "None"].index(s.get("neutralization", "Sector")),
                help="식 평가 후 추가로 적용할 중립화. 식 안에 group_neutralize 가 이미 있으면 None 권장.",
            )
        with col2:
            new_decay = st.number_input(
                "Decay (days)", min_value=0, max_value=20,
                value=int(s.get("decay", 0)),
                help="0 = 적용 안 함. 1 이상이면 linear decay.",
            )
        with col3:
            new_trunc = st.number_input(
                "Truncation", min_value=0.0, max_value=0.20, step=0.01,
                value=float(s.get("truncation", 0)),
                format="%.2f",
                help="종목당 최대 비중 (0 = 적용 안 함).",
            )
        with col4:
            new_delay = st.number_input(
                "Delay", min_value=0, max_value=5,
                value=int(s.get("delay", 1)),
                help="D-1 데이터로 D 진입 (보통 1).",
            )

        st.markdown("### Description")
        new_desc = st.text_area(
            "Description",
            value=cfg.get("description", ""),
            height=80,
            label_visibility="collapsed",
            placeholder="알파의 의미를 짧게 적어두세요.",
        )

        c_save, c_run, _ = st.columns([1, 1, 4])
        save_clicked = c_save.form_submit_button("💾 Save")
        run_clicked = c_run.form_submit_button("▶ Save & Dry Run")

    if save_clicked or run_clicked:
        new_cfg = {
            "expression": new_expr.strip(),
            "settings": {
                "neutralization": new_neut,
                "decay": int(new_decay),
                "truncation": float(new_trunc),
                "delay": int(new_delay),
            },
            "description": new_desc.strip(),
        }
        save_alpha_config(new_cfg)
        st.success(f"저장됨 ({CONFIG_FILE.name}). 다음 봇 실행부터 적용됩니다.")

        if run_clicked:
            with st.spinner("봇 dry-run 실행 중... (~10초)"):
                try:
                    result = subprocess.run(
                        [sys.executable, str(ROOT / "bot" / "run_alpha.py"), "--dry-run"],
                        capture_output=True, text=True, timeout=120, cwd=str(ROOT),
                    )
                    out = result.stdout + result.stderr
                except Exception as e:
                    out = f"실행 실패: {e}"
            st.code(out[-3000:], language="text")

    # === Operators 참고 ===
    with st.expander("📚 사용 가능한 변수와 operator"):
        st.markdown("""
**가격 panel** (date × symbol DataFrame): `close`, `open`, `high`, `low`, `volume`, `returns`

**Fundamental** (S&P 500 스냅샷, 모든 날짜에 broadcast):
`cap` (시총), `cash`, `debt`, `assets`, `ppent` (Net PPE), `equity`, `revenue`, `ni` (순이익),
`ebitda`, `fcf`, `ocf`, `shares`, `eps`, `pe`, `pb`, `ps`, `roe`, `roa`,
`gross_margin`, `op_margin`, `profit_margin`, `revenue_growth`, `earnings_growth`,
`div_yield`, `beta`, `book_value`, `ev`, `inventory`, `retained_earnings`

**Group**: `sector` (= `industry` = `subindustry`, GICS Sector Series)

**Cross-sectional**: `rank`, `winsorize`, `zscore`, `normalize`, `scale`, `quantile`, `scale_down`

**Time-series**: `ts_mean`, `ts_sum`, `ts_std_dev`, `ts_zscore`, `ts_rank`, `ts_delta`, `ts_delay`,
`ts_backfill`, `ts_min`, `ts_max`, `ts_av_diff`, `ts_decay_linear`, `ts_corr`, `ts_covariance`

**Group**: `group_neutralize`, `group_rank`, `group_zscore`, `group_mean`, `group_scale`, `group_min`, `group_max`

**Transformational**: `bucket(x, range='0,1,0.1')`, `trade_when`

**Arithmetic**: `add`, `subtract`, `multiply`, `divide`, `log`, `sqrt`, `abs`, `sign`, `signed_power`,
`power`, `inverse`, `max`, `min`, 그리고 `+`, `-`, `*`, `/`, `**` 같은 Python 연산자
""")

    # === 예시 식 ===
    with st.expander("💡 예시 알파 식"):
        st.markdown("""
```javascript
// 1) 단기 평균회귀 (현재 기본)
rank(-returns)

// 2) 시총 대비 자산 가치 (Brain 예시)
group_neutralize(winsorize(ts_backfill((ppent + cash)/cap, 63), std=4), bucket(rank(cap), range='0,1,0.1'))

// 3) Quality: ROE 높은 종목 long
rank(roe)

// 4) Value: P/E 낮은 종목 long
rank(-pe)

// 5) FCF Yield
rank(fcf / cap)

// 6) Momentum 반대 (1주일 반등)
-ts_zscore(returns, 5)
```
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
                    cmap = load_company_map()
                    sorted_w = sorted(weights.items(), key=lambda x: -x[1])
                    st.caption("회사명을 클릭하면 Yahoo Finance 페이지로 이동합니다.")
                    st.markdown("**Top 10 Long**")
                    render_weight_table(sorted_w[:10], cmap)
                    st.markdown("**Top 10 Short**")
                    render_weight_table(sorted_w[-10:][::-1], cmap)

st.caption(f"Last refreshed: {datetime.now():%Y-%m-%d %H:%M:%S}")
