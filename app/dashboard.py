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


@st.cache_data(ttl=60)
def fetch_market_indices_yf(tickers, period="30d", interval="1d"):
    """yfinance 로 시장 인덱스 일봉. ^GSPC, ^IXIC 등 인덱스 직접 가능."""
    import yfinance as yf
    data = yf.download(
        list(tickers), period=period, interval=interval,
        auto_adjust=False, progress=False, group_by="ticker", threads=True,
    )
    result = {}
    for t in tickers:
        try:
            df = data[t] if isinstance(data.columns, pd.MultiIndex) else data
            result[t] = df.dropna(subset=["Close"]) if not df.empty else pd.DataFrame()
        except Exception:
            result[t] = pd.DataFrame()
    return result


@st.cache_data(ttl=600)
def fetch_market_news(n=12):
    """yfinance 시장 뉴스. 여러 ticker 의 뉴스를 통합 후 시간순으로."""
    import yfinance as yf
    tickers = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]
    seen, items = set(), []
    for t in tickers:
        try:
            for n_item in (yf.Ticker(t).news or []):
                c = n_item.get("content", {}) if isinstance(n_item, dict) else {}
                title = c.get("title") or ""
                if not title or title in seen:
                    continue
                seen.add(title)
                items.append({
                    "title": title,
                    "summary": c.get("summary", "") or c.get("description", ""),
                    "publisher": (c.get("provider") or {}).get("displayName", ""),
                    "link": (c.get("canonicalUrl") or {}).get("url", ""),
                    "pub_date": c.get("pubDate", ""),
                })
        except Exception:
            continue
    # 최신순 정렬
    items.sort(key=lambda x: x.get("pub_date", ""), reverse=True)
    return items[:n]


@st.cache_data(ttl=1800)
def summarize_market_with_claude(news_items):
    """Anthropic Claude API 로 시장 뉴스 핵심 이슈 5개 요약."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None, "ANTHROPIC_API_KEY 가 .env 에 없음. 키를 추가하면 AI 요약 활성화됩니다."
    try:
        from anthropic import Anthropic
    except ImportError:
        return None, "anthropic 라이브러리 설치 필요 (pip install anthropic)"

    client = Anthropic(api_key=api_key)
    import re
    news_text = "\n".join(
        f"{i+1}. [{n['publisher']}] {n['title']} — {re.sub('<[^>]+>', '', n['summary'])[:200]}"
        for i, n in enumerate(news_items)
    )
    prompt = (
        "다음은 미국 주식 시장 관련 최신 뉴스 헤드라인이야. "
        "투자자가 알아야 할 핵심 이슈 5가지를 한국어로 짧게 정리해줘. "
        "각 항목은 한 줄로, 관련 종목/섹터/사건 위주로. 형식은 정확히 아래처럼:\n"
        "1. [이슈 한 줄 — 관련 종목 ($AAPL 식으로) 포함]\n"
        "2. ...\n\n"
        f"뉴스:\n{news_text}"
    )
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
    try:
        msg = client.messages.create(
            model=model, max_tokens=700,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text, None
    except Exception as e:
        return None, f"Claude API 호출 실패: {e}"


def sparkline_svg(values, color, width=110, height=42):
    """SVG sparkline 생성 — 토스 스타일 라인."""
    if values is None or len(values) < 2:
        return ""
    vs = list(map(float, values))
    min_v, max_v = min(vs), max(vs)
    rng = max_v - min_v if max_v != min_v else 1
    pad = 3
    pts = []
    for i, v in enumerate(vs):
        x = i * width / (len(vs) - 1)
        y = height - pad - (v - min_v) / rng * (height - 2 * pad)
        pts.append(f"{x:.1f},{y:.1f}")
    return (
        f'<svg width="{width}" height="{height}" style="display:block;">'
        f'<polyline fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" '
        f'points="{" ".join(pts)}"/></svg>'
    )


@st.cache_data(ttl=30)
def fetch_market_clock():
    """미국 장 개장 여부 + 다음 개장/마감 시간."""
    tc = get_trading_client()
    return tc.get_clock()


def get_market_session():
    """Alpaca clock + ET 시간 기준으로 미장 세션 판단.
    반환: (dot_color, label)
    """
    from datetime import datetime
    try:
        import pytz
    except ImportError:
        pytz = None

    try:
        clock = fetch_market_clock()
        if clock.is_open:
            return ("#2ecc71", "미장 정규장")
    except Exception:
        pass

    if pytz is None:
        return ("#888", "미장 휴장")

    et = pytz.timezone("America/New_York")
    now_et = datetime.now(et)
    if now_et.weekday() >= 5:
        return ("#888", "미장 휴장 (주말)")

    minute = now_et.hour * 60 + now_et.minute
    if 4 * 60 <= minute < 9 * 60 + 30:
        return ("#f39c12", "미장 프리마켓")
    elif 16 * 60 <= minute < 20 * 60:
        return ("#f39c12", "미장 애프터마켓")
    else:
        return ("#888", "미장 휴장")


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
    """Alpaca portfolio history API → 일별 자산 시계열.

    1D timeframe 은 일별 종가만 주므로 장중 실시간 변화가 안 잡힘.
    현재 account.equity 를 마지막 row 로 append 해서 실시간 반영.
    """
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

    # 마지막 row 가 어제 종가일 수 있으므로 현재 account.equity 를 추가 (장중 실시간 반영)
    try:
        acct = tc.get_account()
        current_eq = float(acct.equity)
        if not df.empty and abs(df["equity"].iloc[-1] - current_eq) > 0.01:
            now = pd.Timestamp.utcnow().tz_localize(None)
            base = df["equity"].iloc[0]
            df = pd.concat([df, pd.DataFrame({
                "timestamp": [now],
                "equity": [current_eq],
                "profit_loss": [current_eq - base],
                "profit_loss_pct": [(current_eq / base - 1) if base else 0],
            })], ignore_index=True)
    except Exception:
        pass

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
st.caption("Brain 스타일 expression 으로 알파 작성 → 백테스트 → Alpaca 페이퍼 자동매매")

# === Market Overview (다크 카드, 토스 스타일) ===
INDEX_INFO = [
    ("^GSPC", "S&P 500"),
    ("^IXIC", "NASDAQ"),
    ("^DJI", "DOW"),
    ("^VIX", "VIX"),
]
try:
    mkt_data = fetch_market_indices_yf([s for s, _ in INDEX_INFO])
except Exception:
    mkt_data = {}

mc = st.columns(len(INDEX_INFO))
for col, (sym, label) in zip(mc, INDEX_INFO):
    df = mkt_data.get(sym)
    if df is None or df.empty or len(df) < 2:
        with col:
            st.markdown(
                f'<div style="background:#1a1d29; color:#fff; padding:14px 18px; '
                f'border-radius:10px; height:90px;">'
                f'<div style="font-size:13px; color:#a0a8b0;">{label}</div>'
                f'<div style="font-size:16px; color:#888; margin-top:14px;">데이터 없음</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        continue

    latest = float(df["Close"].iloc[-1])
    prev = float(df["Close"].iloc[-2])
    chg = latest - prev
    chg_pct = chg / prev * 100

    # 양수=초록 / 음수=빨강 (전세계 표준, Long/Short 다른 탭과 통일)
    is_up = chg >= 0
    color = "#2ecc71" if is_up else "#ff5566"
    sign = "+" if is_up else ""

    spark = sparkline_svg(df["Close"].tail(30).values, color, width=110, height=46)

    with col:
        st.markdown(
            f'<div style="background:#1a1d29; color:#fff; padding:14px 18px; '
            f'border-radius:10px; height:90px; display:flex; '
            f'justify-content:space-between; align-items:center;">'
            f'  <div style="min-width:0; flex:1;">'
            f'    <div style="font-size:13px; color:#a0a8b0;">{label}</div>'
            f'    <div style="font-size:21px; font-weight:600; margin-top:6px; '
            f'                white-space:nowrap;">{latest:,.2f}</div>'
            f'    <div style="font-size:12px; color:{color}; margin-top:2px; '
            f'                white-space:nowrap;">'
            f'      {sign}{chg:,.2f} ({sign}{chg_pct:.2f}%)'
            f'    </div>'
            f'  </div>'
            f'  <div style="margin-left:8px; flex-shrink:0;">{spark}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

# === AI 시장 요약 ===
with st.expander("🤖 AI 시장 요약 — 최근 미국 시장 핵심 이슈 5", expanded=True):
    news_items = fetch_market_news(10)
    if not news_items:
        st.info("뉴스 받아올 수 없습니다.")
    else:
        summary, err = summarize_market_with_claude(news_items)
        if summary:
            st.markdown(summary)
            st.caption("Claude 가 요약. 30분마다 갱신.")
        else:
            st.warning(f"⚠️ {err}")
            st.markdown("**최신 헤드라인 (요약 미가공):**")
            for i, n in enumerate(news_items[:5]):
                pub = n["publisher"] or "?"
                link = n["link"] or "#"
                st.markdown(f"{i+1}. [{n['title']}]({link}) — _{pub}_")

        with st.popover("📰 원문 뉴스 보기 (10건)"):
            for n in news_items:
                pub = n["publisher"] or "?"
                link = n["link"] or "#"
                date = n["pub_date"][:10] if n["pub_date"] else ""
                st.markdown(f"- **[{n['title']}]({link})** — _{pub}_ ({date})")

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

c1, c2, c3, c4, c5 = st.columns([1.5, 1.3, 0.8, 1.1, 1.7])
c1.metric("Equity", f"${equity:,.2f}", f"{daily_return:+.2%} (vs prev close)")
c2.metric("Cash", f"${cash:,.2f}")
c3.metric("Positions", len(state["positions"]) if not state["positions"].empty else 0)
with c4:
    st.metric("Open Orders", n_open)
    if n_open > 0:
        st.caption(f"⚠️ 미체결 {n_open}건 — Orders 탭에서 취소 가능")
c5.metric("US Market", market_label, market_sub, delta_color="off")

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
tab1, tab_ord, tab_perf, tab2, tab_bt, tab3 = st.tabs(
    ["Positions", "Orders", "Performance", "Alpha Code", "Backtest", "Bot Logs"]
)

with tab_ord:
    st.markdown(f"### 현재 Open Orders ({n_open}건)")
    if n_open == 0:
        st.info("미체결 주문이 없습니다.")
    else:
        st.caption("비중 = qty × 최신 close 가격 기준 (cost basis).")
        col_a, col_b = st.columns([2, 4])
        with col_a:
            if st.button(
                f"🚫 미체결 주문 {n_open}건 전체 취소",
                type="primary",
                use_container_width=True,
            ):
                n, errs = cancel_all_open_orders()
                st.success(f"취소 요청: {n}건, 실패: {errs}건")
                st.cache_data.clear()
                st.rerun()
        with col_b:
            st.caption("⚠️ 이 버튼을 누르면 아래 표에 있는 모든 주문이 Alpaca 에서 취소됩니다. 체결 전 주문만 취소 가능 (체결된 건은 영향 없음).")

        # 최신 close 가격 로드 (캐시 가능)
        @st.cache_data(ttl=300)
        def _latest_prices():
            try:
                panel_df = pd.read_parquet(ROOT / "data" / "sp500_panel.parquet")
                close = panel_df["close"].unstack(level="symbol")
                return close.iloc[-1].to_dict()
            except Exception:
                return {}
        prices = _latest_prices()

        cmap = load_company_map()
        rows = []
        for o in open_orders:
            sym = o.symbol
            qty = float(o.qty) if o.qty else 0.0
            side = (o.side.value if hasattr(o.side, "value") else str(o.side)).lower()
            px = prices.get(sym, 0)
            cost = qty * px
            info = cmap.get(sym, {"name": sym, "sector": "Unknown"})
            rows.append({
                "symbol": sym, "name": info["name"], "sector": info["sector"],
                "side": side, "qty": qty, "price": px, "cost": cost,
            })
        ord_df = pd.DataFrame(rows)

        longs = ord_df[ord_df["side"] == "buy"].copy()
        shorts = ord_df[ord_df["side"] == "sell"].copy()

        def _render_side(df, title, color):
            if df.empty:
                st.markdown(f"#### {title}")
                st.info(f"{title} 주문 없음.")
                return

            total = df["cost"].sum()
            df = df.copy()
            df["weight"] = df["cost"] / total if total > 0 else 0
            df = df.sort_values("cost", ascending=False)

            # Top 10 + Others
            top = df.head(10)
            rest_cost = df["cost"].iloc[10:].sum()
            labels = list(top["symbol"]) + (["Others"] if rest_cost > 0 else [])
            values = list(top["cost"]) + ([rest_cost] if rest_cost > 0 else [])

            st.markdown(f"#### {title} ({len(df)}종목, 총 ${total:,.0f})")

            fig = go.Figure(go.Pie(
                labels=labels, values=values, hole=0.45,
                marker=dict(line=dict(color="white", width=1.5)),
                textinfo="label+percent", textposition="inside",
                sort=False,
            ))
            fig.update_layout(
                height=320, margin=dict(l=0, r=0, t=10, b=0),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Top 10 table
            st.markdown("**Top 10 종목**")
            tb_rows = ""
            for _, r in top.iterrows():
                url = yahoo_url(r["symbol"])
                tb_rows += (
                    f'<tr style="border-bottom:1px solid #eee; font-size:13px;">'
                    f'<td><b>{r["symbol"]}</b></td>'
                    f'<td><a href="{url}" target="_blank" style="color:#1f77b4; text-decoration:none;">{r["name"]}</a></td>'
                    f'<td style="color:#888;">{r["sector"]}</td>'
                    f'<td style="text-align:right;">{r["qty"]:.4f}</td>'
                    f'<td style="text-align:right;">${r["cost"]:,.0f}</td>'
                    f'<td style="text-align:right; color:{color}; font-weight:600;">{r["weight"]*100:.2f}%</td>'
                    f'</tr>'
                )
            header = (
                '<tr style="border-bottom:2px solid #ddd; text-align:left; font-size:12px;">'
                '<th>Symbol</th><th>Company</th><th>Sector</th>'
                '<th style="text-align:right;">Qty</th>'
                '<th style="text-align:right;">Cost</th>'
                '<th style="text-align:right;">Weight</th></tr>'
            )
            st.markdown(
                f'<table style="width:100%; border-collapse:collapse;">'
                f'<thead>{header}</thead><tbody>{tb_rows}</tbody></table>',
                unsafe_allow_html=True,
            )

        col_l, col_s = st.columns(2)
        with col_l:
            _render_side(longs, "🟢 Long (BUY)", "#2ecc71")
        with col_s:
            _render_side(shorts, "🔴 Short (SELL)", "#e74c3c")

with tab1:
    pos_df = state["positions"]
    if pos_df.empty:
        st.info("현재 보유 포지션 없음. 봇이 첫 주문을 넣은 뒤 장이 열리면 채워집니다.")
    else:
        gross = pos_df["market_value"].abs().sum()
        pos_df = pos_df.copy()
        pos_df["weight"] = pos_df["market_value"].abs() / gross
        pos_df["cost"] = pos_df["market_value"].abs()

        st.caption(f"비중 = |market_value| / 총 gross (${gross:,.0f}). 회사명 클릭 → Yahoo Finance.")

        longs = pos_df[pos_df["side"] == "long"].copy()
        shorts = pos_df[pos_df["side"] == "short"].copy()

        def _render_position_side(df, title, color):
            if df.empty:
                st.markdown(f"#### {title}")
                st.info(f"{title} 포지션 없음.")
                return

            total = df["cost"].sum()
            df = df.sort_values("cost", ascending=False)

            top = df.head(10)
            rest = df.iloc[10:]
            rest_cost = rest["cost"].sum()
            labels = list(top["symbol"]) + (["Others"] if rest_cost > 0 else [])
            values = list(top["cost"]) + ([rest_cost] if rest_cost > 0 else [])

            total_pl = df["unrealized_pl"].sum()
            pl_color = "#2ecc71" if total_pl >= 0 else "#e74c3c"
            st.markdown(
                f'<div style="font-size:20px; font-weight:600; margin:14px 0 6px 0;">'
                f'{title} '
                f'<span style="color:#888; font-size:14px; font-weight:normal;">'
                f'({len(df)}종목 · 총 ${total:,.0f} · '
                f'<span style="color:{pl_color}; font-weight:600;">PL ${total_pl:+,.0f}</span>)'
                f'</span></div>',
                unsafe_allow_html=True,
            )

            fig = go.Figure(go.Pie(
                labels=labels, values=values, hole=0.45,
                marker=dict(line=dict(color="white", width=1.5)),
                textinfo="label+percent", textposition="inside",
                sort=False,
            ))
            fig.update_layout(
                height=320, margin=dict(l=0, r=0, t=10, b=0),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Top 10 표 (좁은 화면에서 안 겹치게 컬럼 축소: P&L $/% 병합, Sector 제거)
            st.markdown("**Top 10 종목**")
            tb = ""
            for _, r in top.iterrows():
                url = yahoo_url(r["symbol"])
                plpc = r["unrealized_plpc"] * 100
                pl_c = "#2ecc71" if r["unrealized_pl"] >= 0 else "#e74c3c"
                pl_combined = f'${r["unrealized_pl"]:+,.0f} ({plpc:+.1f}%)'
                tb += (
                    f'<tr style="border-bottom:1px solid #eee; font-size:12px;">'
                    f'<td><b>{r["symbol"]}</b></td>'
                    f'<td style="max-width:140px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">'
                    f'<a href="{url}" target="_blank" style="color:#1f77b4; text-decoration:none;" title="{r["name"]}">{r["name"]}</a></td>'
                    f'<td style="text-align:right;">{r["qty"]:.2f}</td>'
                    f'<td style="text-align:right;">${r["market_value"]:,.0f}</td>'
                    f'<td style="text-align:right; color:{pl_c}; white-space:nowrap;">{pl_combined}</td>'
                    f'<td style="text-align:right; color:{color}; font-weight:600;">{r["weight"]*100:.1f}%</td>'
                    f'</tr>'
                )
            hdr = (
                '<tr style="border-bottom:2px solid #ddd; text-align:left; font-size:11px; color:#666;">'
                '<th>Symbol</th><th>Company</th>'
                '<th style="text-align:right;">Qty</th>'
                '<th style="text-align:right;">Value</th>'
                '<th style="text-align:right;">P&L</th>'
                '<th style="text-align:right;">Weight</th></tr>'
            )
            st.markdown(
                f'<table style="width:100%; border-collapse:collapse; table-layout:auto;">'
                f'<thead>{hdr}</thead><tbody>{tb}</tbody></table>',
                unsafe_allow_html=True,
            )

        col_l, col_s = st.columns(2)
        with col_l:
            _render_position_side(longs, "🟢 Long", "#2ecc71")
        with col_s:
            _render_position_side(shorts, "🔴 Short", "#e74c3c")

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
        "`data/sp500_panel.parquet` (S&P 500 1년치) 으로 백테스팅을 실행합니다.  \n"
        "**모델**: D 시가 진입 → D+1 시가 청산, 매일 리밸런싱, slippage·수수료 없음."
    )

    # 현재 cfg 다시 로드 (Edit 탭에서 막 저장했을 수 있음)
    bt_cfg = load_alpha_config()
    bt_settings = bt_cfg.get("settings", {})

    BT_NEUT_OPTIONS = ["Sector", "Cap Bucket", "Sector + Cap Bucket", "Market", "None"]

    with st.form("backtest_form"):
        bt_expr = st.text_area(
            "Expression",
            value=bt_cfg.get("expression", "rank(-returns)"),
            height=110,
            help="여기서 바꾼 식은 백테스트만 돌리고 저장은 안 됩니다. 저장하려면 'Save & Run Backtest' 사용.",
        )
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            cur_neut = bt_settings.get("neutralization", "Sector")
            bt_neut = st.selectbox(
                "Neutralization", BT_NEUT_OPTIONS,
                index=BT_NEUT_OPTIONS.index(cur_neut) if cur_neut in BT_NEUT_OPTIONS else 0,
            )
        with col2:
            bt_decay = st.number_input("Decay (days)", min_value=0, max_value=20,
                                       value=int(bt_settings.get("decay", 0)))
        with col3:
            bt_trunc = st.number_input("Truncation", min_value=0.0, max_value=0.20, step=0.01,
                                       value=float(bt_settings.get("truncation", 0)), format="%.2f")
        with col4:
            bt_delay = st.number_input("Delay", min_value=0, max_value=5,
                                       value=int(bt_settings.get("delay", 1)),
                                       help="1 이상이어야 lookahead bias 안 생김.")

        cA, cB, _ = st.columns([1.4, 1.6, 3])
        bt_only_clicked = cA.form_submit_button("🧪 Run Backtest")
        bt_save_clicked = cB.form_submit_button("💾 Save & Run Backtest", type="primary")

    if bt_only_clicked or bt_save_clicked:
        expression = bt_expr.strip()
        settings = {
            "neutralization": bt_neut,
            "decay": int(bt_decay),
            "truncation": float(bt_trunc),
            "delay": int(bt_delay),
        }

        if bt_save_clicked:
            save_alpha_config({
                "expression": expression,
                "settings": settings,
                "description": bt_cfg.get("description", ""),
            })
            st.success("저장됨. 봇 다음 실행부터 적용됩니다.")

        from lib.backtest import backtest_alpha
        try:
            with st.spinner("백테스팅 실행 중... (~30초, group operator 사용 시 더 오래)"):
                metrics = backtest_alpha(expression, settings)
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


with tab_perf:
    st.markdown("### 포트폴리오 성과 상세")
    st.caption("Alpaca 페이퍼 계좌의 실거래 성과. 봇 로그에 시점별 종목 PnL 도 누적됩니다.")

    # === 1. 일별 수익률 + 잔고 변화 ===
    st.markdown("#### 📅 일별 수익률 & 잔고")
    p_col1, p_col2 = st.columns([1, 4])
    with p_col1:
        perf_period = st.selectbox(
            "기간", ["1W", "1M", "3M", "1Y", "all"], index=1, key="perf_period",
        )

    hist, err = fetch_portfolio_history(period=perf_period)
    if err or hist is None or hist.empty:
        st.info("아직 거래일 데이터가 부족합니다.")
    else:
        # 일별 변화 계산
        h = hist.copy()
        h["date"] = h["timestamp"].dt.date
        h["daily_pl"] = h["equity"].diff()
        h["daily_ret"] = h["equity"].pct_change()
        h["cum_ret"] = h["equity"] / h["equity"].iloc[0] - 1
        h = h.iloc[::-1]  # 최근 날짜부터

        # 표
        rows = ""
        for _, r in h.iterrows():
            pl = r["daily_pl"] if pd.notna(r["daily_pl"]) else 0
            ret = r["daily_ret"] if pd.notna(r["daily_ret"]) else 0
            cum = r["cum_ret"] if pd.notna(r["cum_ret"]) else 0
            pl_color = "#2ecc71" if pl >= 0 else "#e74c3c"
            ret_color = "#2ecc71" if ret >= 0 else "#e74c3c"
            cum_color = "#2ecc71" if cum >= 0 else "#e74c3c"
            rows += (
                f'<tr style="border-bottom:1px solid #eee; font-size:13px;">'
                f'<td>{r["date"]}</td>'
                f'<td style="text-align:right;">${r["equity"]:,.2f}</td>'
                f'<td style="text-align:right; color:{pl_color};">${pl:+,.2f}</td>'
                f'<td style="text-align:right; color:{ret_color};">{ret*100:+.3f}%</td>'
                f'<td style="text-align:right; color:{cum_color};">{cum*100:+.2f}%</td>'
                f'</tr>'
            )
        header = (
            '<tr style="border-bottom:2px solid #ddd; font-size:12px; text-align:left;">'
            '<th>Date</th>'
            '<th style="text-align:right;">Equity</th>'
            '<th style="text-align:right;">Daily P&L</th>'
            '<th style="text-align:right;">Daily Return</th>'
            '<th style="text-align:right;">Cum Return</th>'
            '</tr>'
        )
        st.markdown(
            f'<table style="width:100%; border-collapse:collapse;">'
            f'<thead>{header}</thead><tbody>{rows}</tbody></table>',
            unsafe_allow_html=True,
        )

    st.divider()

    # === 2. 종목별 Winners / Losers (현재 포지션 기준 unrealized) ===
    st.markdown("#### 🏆 종목별 손익 (현재 보유 기준 — 미실현 손익)")
    pos_df = state["positions"]
    if pos_df.empty:
        st.info("현재 보유 포지션이 없습니다. 봇이 거래를 시작하면 채워집니다.")
    else:
        winners = pos_df.sort_values("unrealized_pl", ascending=False).head(10)
        losers = pos_df.sort_values("unrealized_pl", ascending=True).head(10)

        def _render_pnl_table(df, title, color):
            st.markdown(f"**{title}**")
            rows = ""
            for _, r in df.iterrows():
                url = yahoo_url(r["symbol"])
                pl = r["unrealized_pl"]
                plpc = r["unrealized_plpc"] * 100
                # Long(파랑) / Short(빨강) 배지
                if r["side"] == "long":
                    side_badge = (
                        '<span style="background:#e7f5ff; color:#1971c2; '
                        'padding:2px 6px; border-radius:3px; font-size:11px; font-weight:600;">LONG</span>'
                    )
                else:
                    side_badge = (
                        '<span style="background:#fff5f5; color:#c92a2a; '
                        'padding:2px 6px; border-radius:3px; font-size:11px; font-weight:600;">SHORT</span>'
                    )
                rows += (
                    f'<tr style="border-bottom:1px solid #eee; font-size:12px;">'
                    f'<td><b>{r["symbol"]}</b></td>'
                    f'<td>{side_badge}</td>'
                    f'<td style="max-width:140px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">'
                    f'<a href="{url}" target="_blank" style="color:#1f77b4; text-decoration:none;" title="{r["name"]}">{r["name"]}</a></td>'
                    f'<td style="text-align:right;">{r["qty"]:+.2f}</td>'
                    f'<td style="text-align:right;">${abs(r["market_value"]):,.0f}</td>'
                    f'<td style="text-align:right; color:{color}; font-weight:600; white-space:nowrap;">${pl:+,.0f} ({plpc:+.1f}%)</td>'
                    f'</tr>'
                )
            header = (
                '<tr style="border-bottom:2px solid #ddd; font-size:11px; text-align:left; color:#666;">'
                '<th>Symbol</th><th>Side</th><th>Company</th>'
                '<th style="text-align:right;">Qty</th>'
                '<th style="text-align:right;">Value</th>'
                '<th style="text-align:right;">P&L</th></tr>'
            )
            st.markdown(
                f'<table style="width:100%; border-collapse:collapse;">'
                f'<thead>{header}</thead><tbody>{rows}</tbody></table>',
                unsafe_allow_html=True,
            )

        col_w, col_l = st.columns(2)
        with col_w:
            _render_pnl_table(winners, "🟢 Top 10 Winners", "#2ecc71")
        with col_l:
            _render_pnl_table(losers, "🔴 Top 10 Losers", "#e74c3c")

    st.divider()

    # === 3. 봇 로그 기반 시점별 종목 PnL 히스토리 ===
    st.markdown("#### 📈 종목별 누적 PnL (봇 실행 기록 기준)")
    st.caption("매 봇 실행 시 그 시점의 unrealized PnL 을 기록. 시간이 지날수록 더 풍부해집니다.")

    log_records = load_recent_logs(50)
    pnl_history = []
    for _, log in log_records:
        ts = pd.to_datetime(log.get("started_at"))
        for sym, info in (log.get("positions_after") or {}).items():
            if isinstance(info, dict):
                pnl_history.append({
                    "ts": ts,
                    "symbol": sym,
                    "unrealized_pl": info.get("unrealized_pl", 0),
                    "qty": info.get("qty", 0),
                })

    if not pnl_history:
        st.info("아직 시점별 PnL 기록이 없습니다. 봇이 한 번 이상 LIVE 로 실행되어야 합니다.")
    else:
        pnl_df = pd.DataFrame(pnl_history)
        latest_full = pnl_df.sort_values("ts").groupby("symbol").last()
        latest_full = latest_full.sort_values("unrealized_pl")

        cmap = load_company_map()

        top_winners = latest_full.tail(10).iloc[::-1]
        top_losers = latest_full.head(10)

        def _render_simple(df, title, color):
            st.markdown(f"**{title}**")
            rows = ""
            for sym, r in df.iterrows():
                info = cmap.get(sym, {"name": sym, "sector": "Unknown"})
                url = yahoo_url(sym)
                pl = r["unrealized_pl"]
                qty = r["qty"]
                if qty > 0:
                    side_badge = (
                        '<span style="background:#e7f5ff; color:#1971c2; '
                        'padding:2px 6px; border-radius:3px; font-size:11px; font-weight:600;">LONG</span>'
                    )
                else:
                    side_badge = (
                        '<span style="background:#fff5f5; color:#c92a2a; '
                        'padding:2px 6px; border-radius:3px; font-size:11px; font-weight:600;">SHORT</span>'
                    )
                rows += (
                    f'<tr style="border-bottom:1px solid #eee; font-size:12px;">'
                    f'<td><b>{sym}</b></td>'
                    f'<td>{side_badge}</td>'
                    f'<td style="max-width:140px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">'
                    f'<a href="{url}" target="_blank" style="color:#1f77b4; text-decoration:none;" title="{info["name"]}">{info["name"]}</a></td>'
                    f'<td style="text-align:right; color:{color}; font-weight:600;">${pl:+,.2f}</td>'
                    f'</tr>'
                )
            header = (
                '<tr style="border-bottom:2px solid #ddd; font-size:11px; text-align:left; color:#666;">'
                '<th>Symbol</th><th>Side</th><th>Company</th>'
                '<th style="text-align:right;">최신 PnL</th></tr>'
            )
            st.markdown(
                f'<table style="width:100%; border-collapse:collapse;">'
                f'<thead>{header}</thead><tbody>{rows}</tbody></table>',
                unsafe_allow_html=True,
            )

        c_w2, c_l2 = st.columns(2)
        with c_w2:
            _render_simple(top_winners, "🟢 누적 Winners", "#2ecc71")
        with c_l2:
            _render_simple(top_losers, "🔴 누적 Losers", "#e74c3c")


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
                        msg = m.group(1) if m else (e or "")[:120]
                        # >=, <= 같은 escape 디코드
                        try:
                            msg = msg.encode("utf-8").decode("unicode_escape")
                        except Exception:
                            pass
                        return msg

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
