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

# 메트릭 폰트 크기 줄이기 (100% 화면에서도 잘리지 않게)
st.markdown(
    """
    <style>
    [data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        line-height: 1.2 !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem !important;
        color: #666 !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.75rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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


@st.cache_data(ttl=30)
def fetch_market_clock():
    """미국 장 개장 여부 + 다음 개장/마감 시간."""
    tc = get_trading_client()
    return tc.get_clock()


@st.cache_data(ttl=30)
def fetch_open_orders():
    """현재 미체결 (open) 주문 목록."""
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus
    tc = get_trading_client()
    req = GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=500)
    return list(tc.get_orders(filter=req))


def cancel_all_open_orders():
    """모든 open 주문 취소. (취소 시도 수, 에러 수) 반환."""
    tc = get_trading_client()
    try:
        results = tc.cancel_orders()
        return len(results), 0
    except Exception:
        opens = fetch_open_orders()
        errs = 0
        for o in opens:
            try:
                tc.cancel_order_by_id(o.id)
            except Exception:
                errs += 1
        return len(opens), errs


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

open_orders = fetch_open_orders()
n_open = len(open_orders)

# === Market clock (US 장 개장 여부) ===
try:
    clock = fetch_market_clock()
    is_open = bool(clock.is_open)
    if is_open:
        next_event = pd.Timestamp(clock.next_close).tz_convert("Asia/Seoul")
        market_label = "🟢 OPEN"
        market_sub = f"마감까지 → {next_event:%m/%d %H:%M} KST"
    else:
        next_event = pd.Timestamp(clock.next_open).tz_convert("Asia/Seoul")
        market_label = "🔴 CLOSED"
        market_sub = f"개장까지 → {next_event:%m/%d %H:%M} KST"
except Exception:
    market_label, market_sub = "—", ""

c1, c2, c3, c4, c5 = st.columns([1.5, 1.3, 0.8, 0.9, 1.7])
c1.metric("Equity", f"${equity:,.2f}", f"{daily_return:+.2%} (vs prev close)")
c2.metric("Cash", f"${cash:,.2f}")
c3.metric("Positions", len(state["positions"]) if not state["positions"].empty else 0)
c4.metric("Open Orders", n_open)
with c5:
    st.metric("US Market", market_label, market_sub, delta_color="off")
    if n_open > 0:
        if st.button(f"🚫 Cancel {n_open} open", use_container_width=True):
            n, errs = cancel_all_open_orders()
            st.success(f"취소 요청: {n}건, 실패: {errs}건")
            st.cache_data.clear()
            st.rerun()

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
tab1, tab_ord, tab2, tab_bt, tab3 = st.tabs(["Positions", "Orders", "Alpha Code", "Backtest", "Bot Logs"])

with tab_ord:
    st.markdown(f"### 현재 Open Orders ({n_open}건)")
    if n_open == 0:
        st.info("미체결 주문이 없습니다.")
    else:
        col_a, col_b = st.columns([1, 5])
        with col_a:
            if st.button("🚫 모두 취소", type="primary"):
                n, errs = cancel_all_open_orders()
                st.success(f"취소 요청: {n}건, 실패: {errs}건")
                st.cache_data.clear()
                st.rerun()
        with col_b:
            st.caption("개별 종목 옆 ✕ 버튼으로 한 건씩 취소도 가능합니다.")

        cmap = load_company_map()
        rows = []
        for o in open_orders:
            info = cmap.get(o.symbol, {"name": o.symbol, "sector": "Unknown"})
            rows.append({
                "id": str(o.id),
                "symbol": o.symbol,
                "name": info["name"],
                "side": o.side.value if hasattr(o.side, "value") else str(o.side),
                "qty": float(o.qty) if o.qty else 0.0,
                "status": o.status.value if hasattr(o.status, "value") else str(o.status),
                "submitted_at": str(o.submitted_at)[:19] if o.submitted_at else "",
            })
        ord_df = pd.DataFrame(rows).sort_values(["side", "symbol"])

        # 표 직접 HTML 로 (개별 cancel 버튼 행렬은 streamlit 에서 어려우니 일단 표만)
        header = (
            f'<tr style="border-bottom:2px solid #ddd; text-align:left; font-size:12px;">'
            f'<th>Symbol</th><th>Company</th><th>Side</th>'
            f'<th style="text-align:right;">Qty</th>'
            f'<th>Status</th><th>Submitted</th></tr>'
        )
        body = ""
        for _, r in ord_df.iterrows():
            side_color = "#2ecc71" if r["side"] == "buy" else "#e74c3c"
            url = yahoo_url(r["symbol"])
            body += (
                f'<tr style="border-bottom:1px solid #eee; font-size:13px;">'
                f'<td><b>{r["symbol"]}</b></td>'
                f'<td><a href="{url}" target="_blank" style="color:#1f77b4; text-decoration:none;">{r["name"]}</a></td>'
                f'<td style="color:{side_color}; font-weight:600;">{r["side"].upper()}</td>'
                f'<td style="text-align:right;">{r["qty"]:.4f}</td>'
                f'<td style="color:#888;">{r["status"]}</td>'
                f'<td style="color:#888; font-size:12px;">{r["submitted_at"]}</td>'
                f'</tr>'
            )
        st.markdown(
            f'<table style="width:100%; border-collapse:collapse;">'
            f'<thead>{header}</thead><tbody>{body}</tbody></table>',
            unsafe_allow_html=True,
        )

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
    s = cfg.get("settings", {})

    # === (1) Currently Applied Alpha — read-only Brain-style card ===
    import html as _html
    expr_display = _html.escape(cfg.get("expression", ""))
    applied_html = (
        f'<div style="border:1px solid #2a9d8f; border-radius:6px; padding:14px 18px; margin-bottom:18px; background:#f0fafa;">'
        f'<div style="font-size:12px; color:#2a9d8f; font-weight:600; letter-spacing:1px; margin-bottom:8px;">✓ CURRENTLY APPLIED ALPHA</div>'
        f'<div style="background:#1e1e1e; color:#d4d4d4; padding:14px 18px; border-radius:4px; '
        f'font-family:Consolas,Menlo,monospace; font-size:13px; line-height:1.6; white-space:pre-wrap; '
        f'word-break:break-word; margin-bottom:10px;">{expr_display}</div>'
        f'<div style="font-size:12px; color:#555;">'
        f'<b>Neutralization</b>: {s.get("neutralization","-")} &nbsp;·&nbsp; '
        f'<b>Decay</b>: {s.get("decay",0)} &nbsp;·&nbsp; '
        f'<b>Truncation</b>: {s.get("truncation",0)} &nbsp;·&nbsp; '
        f'<b>Delay</b>: {s.get("delay",1)}'
        f'</div>'
    )
    if cfg.get("description"):
        applied_html += f'<div style="font-size:12px; color:#777; margin-top:6px;">{_html.escape(cfg["description"])}</div>'
    applied_html += '</div>'
    st.markdown(applied_html, unsafe_allow_html=True)
    st.caption("위는 봇이 실제로 매일 돌리는 알파. 아래 폼에서 수정 후 Save 를 누르면 다음 실행부터 반영됩니다.")
    st.divider()

    # === (2) Edit Form ===
    st.markdown("### ✏️ Edit Alpha")
    NEUT_OPTIONS = ["Sector", "Cap Bucket", "Sector + Cap Bucket", "Market", "None"]
    with st.form("alpha_form"):
        st.markdown("**Code**")
        new_expr = st.text_area(
            "Expression",
            value=cfg.get("expression", "rank(-returns)"),
            height=120,
            label_visibility="collapsed",
            help="Brain Fast Expression 문법. 예: group_neutralize(rank(-returns), sector)",
        )

        st.markdown("**Simulation Settings**")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            current_neut = s.get("neutralization", "Sector")
            new_neut = st.selectbox(
                "Neutralization",
                NEUT_OPTIONS,
                index=NEUT_OPTIONS.index(current_neut) if current_neut in NEUT_OPTIONS else 0,
                help="식 평가 후 추가로 적용할 중립화. Cap Bucket = 시총 10분위 중립, Sector + Cap Bucket = 둘 다.",
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

        st.markdown(
            '<div style="background:#fff3cd; border-left:4px solid #f0ad4e; padding:8px 12px; '
            'font-size:12px; color:#856404; margin-bottom:8px;">'
            'LIVE 실행은 Alpaca 페이퍼 계좌에 <b>실제 주문을 제출</b>합니다. '
            '아래 체크박스를 켠 뒤 빨간 버튼을 눌러야 실행됩니다.</div>',
            unsafe_allow_html=True,
        )
        confirm_live = st.checkbox(
            "확인 — Alpaca 페이퍼 계좌에 실주문을 제출하는 것에 동의합니다.",
            value=False, key="confirm_live",
        )

        c_save, c_run, c_live, _ = st.columns([1, 1.4, 1.8, 2.8])
        save_clicked = c_save.form_submit_button("💾 Save")
        run_clicked = c_run.form_submit_button("▶ Save & Dry Run")
        live_clicked = c_live.form_submit_button("🔴 Save & Run LIVE", type="primary")

    if save_clicked or run_clicked or live_clicked:
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

        cmd_args = None
        run_label = ""
        if live_clicked:
            if not confirm_live:
                st.error("⚠️ 확인 체크박스를 체크하지 않아 LIVE 실행 취소됨. (저장은 완료)")
            else:
                cmd_args = [sys.executable, str(ROOT / "bot" / "run_alpha.py")]
                run_label = "🔴 LIVE 실행 — Alpaca 에 실제 주문 제출 중... (~30초)"
        elif run_clicked:
            cmd_args = [sys.executable, str(ROOT / "bot" / "run_alpha.py"), "--dry-run"]
            run_label = "🟡 Dry-run 실행 중... (~10초)"

        if cmd_args:
            with st.spinner(run_label):
                try:
                    result = subprocess.run(
                        cmd_args, capture_output=True, text=True, timeout=180, cwd=str(ROOT),
                        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                    )
                    out = result.stdout + result.stderr
                except Exception as e:
                    out = f"실행 실패: {e}"
            if live_clicked:
                st.success("LIVE 실행 완료. 결과는 Bot Logs 탭과 Open Orders 메트릭에서 확인하세요.")
                st.cache_data.clear()
            st.code(out[-4000:], language="text")

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

with tab_bt:
    st.markdown("### 백테스팅")
    st.caption(
        "현재 저장된 알파 식과 세팅으로 `data/sp500_panel.parquet` (S&P 500 1년치) 백테스팅을 실행합니다.  \n"
        "**모델**: D 시가 진입 → D+1 시가 청산, 매일 리밸런싱, slippage·수수료 없음."
    )

    # 현재 cfg 다시 로드 (Edit 탭에서 막 저장했을 수 있음)
    bt_cfg = load_alpha_config()
    bt_settings = bt_cfg.get("settings", {})

    col_show, col_run = st.columns([4, 1])
    with col_show:
        st.code(bt_cfg.get("expression", ""), language="javascript")
        st.caption(
            f"Neutralization=**{bt_settings.get('neutralization','-')}**, "
            f"Decay=**{bt_settings.get('decay',0)}**, "
            f"Truncation=**{bt_settings.get('truncation',0)}**, "
            f"Delay=**{bt_settings.get('delay',1)}**"
        )
    with col_run:
        bt_clicked = st.button("🧪 Run Backtest", type="primary", use_container_width=True)

    if bt_clicked:
        from lib.backtest import backtest_alpha
        try:
            with st.spinner("백테스팅 실행 중... (~30초)"):
                metrics = backtest_alpha(bt_cfg["expression"], bt_settings)
        except Exception as e:
            st.error(f"백테스팅 실패: {e}")
            metrics = None

        if metrics and "error" not in metrics:
            st.divider()
            st.markdown("#### 📊 성과 지표")

            mc = st.columns(4)
            mc[0].metric("총 수익률", f"{metrics['total_return']:+.2%}")
            mc[1].metric("연환산 수익률", f"{metrics['annual_return']:+.2%}")
            mc[2].metric("Sharpe", f"{metrics['sharpe']:.3f}")
            mc[3].metric("MDD", f"{metrics['mdd']:+.2%}")

            mc2 = st.columns(4)
            mc2[0].metric("승률", f"{metrics['win_rate']:.2%}")
            mc2[1].metric("일평균 회전율", f"{metrics['avg_turnover']:.2%}")
            mc2[2].metric("평균 최대비중", f"{metrics['avg_max_weight']:.2%}")
            mc2[3].metric("거래일 수", f"{metrics['n_days']}일")

            # === Cumulative return chart ===
            st.markdown("#### 📈 Cumulative Return")
            cum = metrics["cumulative"]
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=cum.index, y=cum.values,
                mode="lines",
                line=dict(color="#2ecc71", width=2),
                name="Cumulative",
            ))
            fig.add_hline(y=1.0, line_dash="dash", line_color="gray", line_width=0.7)
            fig.update_layout(
                height=340, margin=dict(l=0, r=0, t=10, b=0),
                yaxis_title="Cumulative Return (× 시작)", xaxis_title="",
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

            # === Drawdown chart ===
            st.markdown("#### 📉 Drawdown")
            dd = metrics["drawdown"]
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=dd.index, y=dd.values,
                fill="tozeroy",
                mode="lines",
                line=dict(color="#e74c3c", width=1),
                fillcolor="rgba(231, 76, 60, 0.3)",
                name="Drawdown",
            ))
            fig2.update_layout(
                height=240, margin=dict(l=0, r=0, t=10, b=0),
                yaxis_title="Drawdown", xaxis_title="",
                yaxis_tickformat=".1%",
                showlegend=False,
            )
            st.plotly_chart(fig2, use_container_width=True)


with tab3:
    st.markdown("### 최근 봇 실행 로그")
    st.caption(
        "🟡 **DRY-RUN**: 사이트 / 터미널에서 `--dry-run` 으로 돌린 시뮬레이션. **실제 주문 들어가지 않음**.  \n"
        "🟢 **LIVE**: cron (매일 06:05 KST) 또는 봇 직접 실행으로 **실제 주문 제출됨**."
    )
    logs = load_recent_logs(10)
    if not logs:
        st.info("아직 실행 로그가 없습니다.")
    else:
        for name, log in logs:
            ts = log.get("started_at", name)
            n_orders = len(log.get("orders", {}))
            n_subm = len(log.get("submitted", []))
            n_fail = len(log.get("failed", []))
            is_dry = bool(log.get("dry_run"))
            if is_dry:
                label = f"🟡 DRY-RUN  ·  {ts}  ·  시뮬레이션 {n_orders}건  (실제 주문 X)"
            else:
                label = f"🟢 LIVE  ·  {ts}  ·  주문 {n_orders}건 제출됨 (성공 {n_subm}, 실패 {n_fail})"
            with st.expander(label):
                # 상단 줄 — 모드 강조
                mode_bg = "#fff8e1" if is_dry else "#e8f5e9"
                mode_color = "#f57c00" if is_dry else "#2e7d32"
                mode_text = "DRY-RUN (시뮬레이션만, Alpaca 에 주문 들어가지 않음)" if is_dry else "LIVE (Alpaca 에 실제 주문 제출)"
                st.markdown(
                    f'<div style="background:{mode_bg}; color:{mode_color}; padding:8px 12px; '
                    f'border-radius:4px; font-size:13px; margin-bottom:10px;"><b>Mode:</b> {mode_text}</div>',
                    unsafe_allow_html=True,
                )

                summary_cols = st.columns(5)
                summary_cols[0].metric("Equity", f"${log.get('equity', 0):,.0f}")
                summary_cols[1].metric("Universe", log.get("universe_size", 0))
                summary_cols[2].metric("Panel last", log.get("panel_last_date", "-"))
                summary_cols[3].metric("Orders", n_orders)
                summary_cols[4].metric("Submitted" if not is_dry else "Simulated", n_subm if not is_dry else n_orders)

                # 알파 식 / 세팅도 같이 보여주기
                if log.get("expression"):
                    st.caption(f"**식**: `{log['expression']}`")
                if log.get("settings"):
                    s = log["settings"]
                    st.caption(f"**세팅**: Neut={s.get('neutralization')}, Decay={s.get('decay')}, Trunc={s.get('truncation')}, Delay={s.get('delay')}")

                # === 실패 주문 상세 ===
                failed_list = log.get("failed", [])
                if failed_list:
                    st.markdown(f"#### ❌ 실패한 주문 ({len(failed_list)}건)")
                    # 에러 메시지에서 핵심만 추출
                    def short_err(e):
                        import re
                        m = re.search(r'"message":"([^"]+)"', e or "")
                        if m:
                            return m.group(1)
                        return (e or "")[:120]

                    from collections import Counter
                    err_counter = Counter(short_err(f.get("error", "")) for f in failed_list)
                    st.caption("**에러 종류별 건수**")
                    err_rows = ""
                    for err, cnt in err_counter.most_common():
                        err_rows += (
                            f'<tr><td style="padding:4px 8px; color:#c0392b;">{cnt}건</td>'
                            f'<td style="padding:4px 8px;">{err}</td></tr>'
                        )
                    st.markdown(
                        f'<table style="border-collapse:collapse; font-size:12px;">'
                        f'<tbody>{err_rows}</tbody></table>',
                        unsafe_allow_html=True,
                    )

                    with st.expander(f"상세 보기 (종목 {len(failed_list)}개)"):
                        cmap = load_company_map()
                        rows = ""
                        for f in failed_list:
                            sym = f.get("symbol", "?")
                            qty = f.get("qty", 0)
                            err = short_err(f.get("error", ""))
                            info = cmap.get(sym, {"name": sym})
                            rows += (
                                f'<tr style="border-bottom:1px solid #eee; font-size:12px;">'
                                f'<td><b>{sym}</b></td><td>{info["name"]}</td>'
                                f'<td style="text-align:right;">{qty}</td>'
                                f'<td style="color:#c0392b;">{err}</td></tr>'
                            )
                        st.markdown(
                            f'<table style="width:100%; border-collapse:collapse;">'
                            f'<thead><tr style="border-bottom:2px solid #ddd; font-size:12px; text-align:left;">'
                            f'<th>Symbol</th><th>Company</th><th style="text-align:right;">Qty</th><th>Error</th>'
                            f'</tr></thead><tbody>{rows}</tbody></table>',
                            unsafe_allow_html=True,
                        )

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
