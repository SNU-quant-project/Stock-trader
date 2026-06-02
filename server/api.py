"""FastAPI 백엔드 — BRAIN 스타일 React 프론트(web/) 서빙 + 라이브 데이터 API.

엔드포인트:
  GET  /                  → web/index.html (React 정적 사이트)
  GET  /api/data          → 대시보드 전체 데이터 (account/indices/news/positions/orders/botlogs)
  GET  /api/config        → 현재 알파 식·세팅 (bot/alpha_config.json)
  POST /api/config        → 알파 식·세팅 저장
  POST /api/backtest      → {expression, settings} 백테스트 실행 → 지표 + PnL 곡선
  POST /api/run           → {mode: "dry"|"live"} 봇 실행

실행:
  uvicorn server.api:app --host 0.0.0.0 --port 8082
"""

import os
import re
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from lib.backtest import backtest_alpha
from lib.sp500_universe import load_data as load_universe_data

WEB_DIR = ROOT / "web"
CONFIG_FILE = ROOT / "bot" / "alpha_config.json"
LOG_DIR = ROOT / "bot" / "logs"

app = FastAPI(title="SNU Quant Alpha Bot API")

# ---- 간단한 TTL 캐시 ----
_cache = {}
def cached(key, ttl, fn):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    val = fn()
    _cache[key] = (now, val)
    return val


# ============ Alpaca ============

def _trading_client():
    from alpaca.trading.client import TradingClient
    return TradingClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"], paper=True)


def _company_map():
    def build():
        df = pd.read_csv(ROOT / "data" / "sp500_current.csv")
        return {r["Symbol"]: {"name": r["Security"], "sector": r["GICS Sector"]}
                for _, r in df.iterrows()}
    return cached("cmap", 3600, build)


def get_account_block():
    """account + positions(longs/shorts) + open orders + market clock."""
    tc = _trading_client()
    acct = tc.get_account()
    cmap = _company_map()

    # 시장 시계
    market_open, next_event = False, ""
    try:
        clk = tc.get_clock()
        market_open = bool(clk.is_open)
        nxt = clk.next_close if market_open else clk.next_open
        next_event = pd.Timestamp(nxt).tz_convert("Asia/Seoul").strftime("%m/%d %H:%M KST")
    except Exception:
        pass

    # 포지션 P&L:
    #   장 중   → 실시간 current_price (Alpaca 가 주는 live market value/PL 그대로)
    #   장 마감 → 종가 lastday_price 로 재계산 (장외 stale/오류 quote, 예: BNY $10 회피)
    longs, shorts = [], []
    try:
        for p in tc.get_all_positions():
            qty = float(p.qty)
            entry = float(p.avg_entry_price)
            if market_open:
                px = float(p.current_price or 0)
                mv = float(p.market_value)
                pl = float(p.unrealized_pl)
                plpc = float(p.unrealized_plpc)
            else:
                px = float(p.lastday_price) if p.lastday_price else float(p.current_price or 0)
                mv = px * qty
                pl = (px - entry) * qty
                cost = abs(entry * qty)
                plpc = pl / cost if cost else 0
            info = cmap.get(p.symbol, {"name": p.symbol, "sector": "Unknown"})
            row = {
                "sym": p.symbol, "name": info["name"], "sector": info["sector"],
                "qty": qty, "price": px, "marketValue": mv,
                "pl": pl, "plpc": plpc,
            }
            (longs if qty >= 0 else shorts).append(row)
    except Exception:
        pass

    # 미체결 주문
    buy_orders, sell_orders = [], []
    try:
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        opens = tc.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=500))
        prices = _latest_prices()
        for o in opens:
            sym = o.symbol
            qty = float(o.qty) if o.qty else 0.0
            side = (o.side.value if hasattr(o.side, "value") else str(o.side)).lower()
            px = prices.get(sym, 0)
            info = cmap.get(sym, {"name": sym, "sector": "Unknown"})
            row = {"sym": sym, "name": info["name"], "sector": info["sector"],
                   "side": side, "qty": qty, "price": px, "cost": qty * px}
            (buy_orders if side == "buy" else sell_orders).append(row)
    except Exception:
        pass

    live_equity = float(acct.equity)
    last_equity = float(acct.last_equity) if acct.last_equity else live_equity
    # 장 닫혔을 때: 실시간 equity 는 stale/오류 quote(예: BNY 가 $10 로 찍힘)를 물 수 있어
    # 종가(last_equity) 기준으로 표시. 장 중에만 실시간 equity 사용.
    equity = live_equity if market_open else last_equity
    n_pos = len(longs) + len(shorts)
    return {
        "account": {
            "equity": equity, "cash": float(acct.cash),
            "buyingPower": float(acct.buying_power), "lastEquity": last_equity,
            "liveEquity": live_equity,
            "positions": n_pos, "openOrders": len(buy_orders) + len(sell_orders),
            "marketOpen": market_open, "nextEvent": next_event or "—",
            "dailyReturn": (equity - last_equity) / last_equity if last_equity else 0,
        },
        "longs": longs, "shorts": shorts,
        "buyOrders": buy_orders, "sellOrders": sell_orders,
    }


def _latest_prices():
    def build():
        try:
            panel = pd.read_parquet(ROOT / "data" / "sp500_panel.parquet")
            return panel["close"].unstack(level="symbol").iloc[-1].to_dict()
        except Exception:
            return {}
    return cached("prices", 600, build)


def _todays_close_from_intraday(tc):
    """당일 정규장 마감(~16:00 ET = ~20:00 UTC) equity 를 intraday 에서 추출.
    Alpaca 1D 시리즈는 당일 종가를 하루 늦게 넣어주므로 보완용.
    반환: (date, equity) 또는 None. (date 는 naive-UTC 기준, 1D 라벨과 일관)
    """
    try:
        from alpaca.trading.requests import GetPortfolioHistoryRequest
        h = tc.get_portfolio_history(history_filter=GetPortfolioHistoryRequest(period="1D", timeframe="1H"))
        idf = pd.DataFrame({"ts": pd.to_datetime(h.timestamp, unit="s"), "equity": h.equity})
        idf = idf[idf["equity"].notna() & (idf["equity"] > 0)]
        if idf.empty:
            return None
        idf["d"] = idf["ts"].dt.date
        today = idf["d"].max()
        day = idf[idf["d"] == today]
        # 정규장 종료(~20:00 UTC) 이내 값만 → 마감 시점. 없으면 마지막 값.
        reg = day[day["ts"].dt.hour <= 20]
        close_eq = float((reg if not reg.empty else day)["equity"].iloc[-1])
        return today, close_eq
    except Exception:
        return None


def get_portfolio_history(market_open=False, live_equity=None):
    """acctHist + dailyPerf (일별, naive-UTC 날짜).
    과거일은 종가. 당일은 1D 가 누락하므로 intraday 로 보완:
      장 중   → 실시간 live_equity (현재 시장가 기준)
      장 마감 → intraday 정규장 마감 종가
    """
    try:
        from alpaca.trading.requests import GetPortfolioHistoryRequest
        tc = _trading_client()
        h = tc.get_portfolio_history(history_filter=GetPortfolioHistoryRequest(period="1M", timeframe="1D"))
        df = pd.DataFrame({"ts": pd.to_datetime(h.timestamp, unit="s"), "equity": h.equity})
        df = df[df["equity"].notna() & (df["equity"] > 0)].reset_index(drop=True)
        if df.empty:
            return [], []
        df["d"] = df["ts"].dt.date
        dates = list(df["d"])
        equities = [float(x) for x in df["equity"]]

        # 1D 시리즈에 당일이 없으면 intraday 로 당일 포인트 보완
        today_close = _todays_close_from_intraday(tc)
        if today_close:
            d, eq = today_close
            if market_open and live_equity:
                eq = float(live_equity)  # 장 중엔 현재 시장가 기준 실시간 equity
            if d not in dates:
                dates.append(d)
                equities.append(eq)
            elif market_open and live_equity:
                equities[-1] = float(live_equity)

        fmt = "%m/%d" if os.name == "nt" else "%-m/%-d"
        labels = [d.strftime(fmt) for d in dates]
        acct_hist = [{"date": labels[i], "equity": equities[i]} for i in range(len(dates))]
        daily = []
        for i in range(len(equities) - 1, 0, -1):
            eq, prev = equities[i], equities[i - 1]
            daily.append({"date": labels[i], "equity": eq,
                          "pl": eq - prev, "ret": eq / prev - 1 if prev else 0,
                          "cum": eq / equities[0] - 1 if equities[0] else 0})
        return acct_hist, daily
    except Exception:
        return [], []


# ============ 시장 지수 (yfinance) ============

def get_indices():
    def build():
        import yfinance as yf
        tickers = {"^GSPC": "S&P 500", "^IXIC": "NASDAQ", "^DJI": "DOW", "^VIX": "VIX"}
        out = []
        try:
            data = yf.download(list(tickers), period="30d", interval="1d",
                               auto_adjust=False, progress=False, group_by="ticker", threads=True)
        except Exception:
            return out
        for sym, label in tickers.items():
            try:
                df = data[sym] if isinstance(data.columns, pd.MultiIndex) else data
                closes = df["Close"].dropna()
                if len(closes) < 2:
                    continue
                latest, prev = float(closes.iloc[-1]), float(closes.iloc[-2])
                chg = latest - prev
                out.append({
                    "sym": sym, "label": label, "price": latest,
                    "chg": chg, "pct": chg / prev * 100 if prev else 0,
                    "up": chg >= 0, "spark": [float(x) for x in closes.tail(28)],
                })
            except Exception:
                continue
        return out
    return cached("indices", 60, build)


# ============ 뉴스 (RSS) ============

# 시장 관련 키워드 (점수 가산) — 많이 맞을수록 시장 뉴스
MARKET_KW = re.compile(
    r"\b(stock|stocks|share|shares|equit|nasdaq|s&p|dow|index|futures|"
    r"fed|fomc|powell|rate|rates|inflation|cpi|pce|yield|treasur|bond|"
    r"earning|earnings|revenue|guidance|ipo|merger|acquisition|dividend|buyback|"
    r"oil|crude|opec|gold|dollar|gdp|jobs|payroll|jobless|unemployment|"
    r"rally|selloff|sell-off|bull|bear|tariff|chip|semiconductor|ai)\b",
    re.I,
)
# 개인재무 상담칼럼·라이프스타일 잡음 (제외)
JUNK_KW = re.compile(
    r"\b(my (husband|wife|son|daughter|mother|father|friend|buddy|sister|brother|boss|fianc)|"
    r"adviser|advisor|estate|inheritance|will|prenup|alimony|divorce|tip the|tipping|"
    r"retire early|nest egg|golf|dating|my 401|should i|am i|was i|how do i|how can we|how can i)\b",
    re.I,
)


def _sp_symbols():
    def build():
        try:
            df = pd.read_csv(ROOT / "data" / "sp500_current.csv")
            return set(df["Symbol"].astype(str))
        except Exception:
            return set()
    return cached("sp_syms", 3600, build)


def get_news():
    def build():
        import feedparser
        from email.utils import parsedate_to_datetime
        # 시장 전용 피드만 (MW topstories=Moneyist 상담칼럼, Investing=지정학 위주 → 제외)
        feeds = [
            ("CNBC Markets", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069", 1.6),
            ("CNBC Finance", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", 1.3),
            ("CNBC Economy", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258", 1.2),
            ("MarketWatch", "http://feeds.marketwatch.com/marketwatch/marketpulse/", 1.0),
        ]
        score, data = {}, {}
        for pub, url, w in feeds:
            try:
                for e in feedparser.parse(url).entries:
                    title = (e.get("title") or "").strip()
                    if not title:
                        continue
                    # 잡음(상담칼럼) 제외
                    if JUNK_KW.search(title) or (title.endswith("?") and re.search(r"\b(I|my|me|we)\b", title)):
                        continue
                    base = score.get(title, 0)
                    score[title] = base + w + len(MARKET_KW.findall(title)) * 0.6  # 시장 키워드 가산
                    if title not in data:
                        data[title] = {"title": title, "pub": pub,
                                       "link": e.get("link", ""), "pub_date": e.get("published", "")}
            except Exception:
                continue
        now = datetime.utcnow()
        for title, d in data.items():
            try:
                dt = parsedate_to_datetime(d["pub_date"])
                if dt.tzinfo:
                    dt = dt.replace(tzinfo=None)
                hrs = (now - dt).total_seconds() / 3600
                if 0 <= hrs < 48:
                    score[title] += max(0, 3 - hrs / 16)
                    d["ago"] = f"{int(hrs)}시간 전" if hrs >= 1 else f"{int(hrs*60)}분 전"
                else:
                    d["ago"] = ""
            except Exception:
                d["ago"] = ""
        items = sorted(data.values(), key=lambda x: -score.get(x["title"], 0))[:6]

        # 한국어 번역
        try:
            from deep_translator import GoogleTranslator
            tr = GoogleTranslator(source="en", target="ko")
            kos = tr.translate_batch([it["title"] for it in items])
            for it, ko in zip(items, kos):
                it["titleKo"] = ko or ""
        except Exception:
            for it in items:
                it["titleKo"] = ""

        # 티커: 제목에 실제 S&P 500 심볼이 단어로 등장할 때만 (가짜 CFP/AI/CEO 방지)
        syms = _sp_symbols()
        for it in items:
            found = [w for w in re.findall(r"\b[A-Z]{1,5}\b", it["title"]) if w in syms]
            it["tickers"] = list(dict.fromkeys(found))[:3]
        return items
    return cached("news", 300, build)


# ============ 봇 로그 ============

def get_bot_logs():
    if not LOG_DIR.exists():
        return []
    files = sorted(LOG_DIR.glob("run_*.json"), reverse=True)[:8]
    out = []
    for f in files:
        try:
            log = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        submitted = log.get("submitted", [])
        failed = log.get("failed", [])
        n_long = sum(1 for s in submitted if s.get("qty", 0) > 0)
        n_short = sum(1 for s in submitted if s.get("qty", 0) < 0)
        is_dry = bool(log.get("dry_run"))
        status = "ok" if not failed else "warn"
        note = log.get("expression", "")[:60] or ("Dry run" if is_dry else "")
        if failed:
            note = f"{len(failed)} orders failed · " + note
        started = log.get("started_at", "")
        out.append({
            "file": f.name, "at": started[:16].replace("T", " "),
            "mode": "DRY" if is_dry else "LIVE", "status": status,
            "orders": len(log.get("orders", {})), "longs": n_long, "shorts": n_short,
            "note": note, "durMs": 0,
        })
    return out


# ============ config ============

def read_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {"expression": "rank(-returns)",
            "settings": {"neutralization": "Sector", "decay": 0, "truncation": 0, "delay": 1},
            "description": ""}


# ============ 정적 데이터 (variables / examples) ============

VARIABLES = [
    {"name": "returns", "type": "Matrix, Price Volume", "desc": "Daily returns"},
    {"name": "close", "type": "Matrix, Price Volume", "desc": "Daily close price"},
    {"name": "open", "type": "Matrix, Price Volume", "desc": "Daily open price"},
    {"name": "high", "type": "Matrix, Price Volume", "desc": "Daily high price"},
    {"name": "low", "type": "Matrix, Price Volume", "desc": "Daily low price"},
    {"name": "volume", "type": "Matrix, Price Volume", "desc": "Daily volume"},
    {"name": "cap", "type": "Matrix, Fundamental", "desc": "Market capitalization"},
    {"name": "revenue", "type": "Matrix, Fundamental", "desc": "Total revenue (TTM)"},
    {"name": "ni", "type": "Matrix, Fundamental", "desc": "Net income"},
    {"name": "fcf", "type": "Matrix, Fundamental", "desc": "Free cash flow"},
    {"name": "roe", "type": "Matrix, Fundamental", "desc": "Return on equity"},
    {"name": "pe", "type": "Matrix, Fundamental", "desc": "Price / Earnings"},
    {"name": "pb", "type": "Matrix, Fundamental", "desc": "Price / Book"},
    {"name": "sector", "type": "Group, GICS", "desc": "GICS Sector"},
    {"name": "ppent", "type": "Matrix, Fundamental", "desc": "Net property, plant & equipment"},
]
EXAMPLES = [
    {"label": "Short-term mean reversion", "expr": "rank(-returns)"},
    {"label": "Quality — high ROE", "expr": "rank(roe)"},
    {"label": "Value — low P/E", "expr": "rank(-pe)"},
    {"label": "FCF yield", "expr": "rank(fcf / cap)"},
    {"label": "Cap-bucket asset value",
     "expr": "group_neutralize(\n  winsorize(ts_backfill((ppent + cash) / cap, 63), std=4),\n  bucket(rank(cap), range='0,1,0.1')\n)"},
]


# ============ 라우트 ============

@app.get("/api/data")
def api_data():
    out = {"variables": VARIABLES, "examples": EXAMPLES, "config": read_config()}
    try:
        out.update(get_account_block())
    except Exception as e:
        out["_account_err"] = str(e)
    out["indices"] = get_indices()
    out["news"] = get_news()
    out["aiSummary"] = []  # ANTHROPIC_API_KEY 없으면 빈 배열 (프론트가 헤드라인으로 폴백)
    out["botLogs"] = get_bot_logs()
    acct = out.get("account") or {}
    mkt_open = bool(acct.get("marketOpen"))
    live_eq = acct.get("liveEquity")

    # 당일 포인트: 장 중 → 실시간 equity, 장 마감 → intraday 종가
    acct_hist, daily = get_portfolio_history(market_open=mkt_open, live_equity=live_eq)
    out["acctHist"] = acct_hist
    out["dailyPerf"] = daily

    # 상단 Equity 카드 = acctHist 마지막 포인트와 일치시킴 (장중=실시간, 마감=종가)
    # dailyReturn = 당일 포인트 vs 직전 거래일 종가
    if acct and len(acct_hist) >= 2:
        last_c = acct_hist[-1]["equity"]
        prev_c = acct_hist[-2]["equity"]
        if prev_c:
            acct["dailyReturn"] = (last_c - prev_c) / prev_c
            acct["equity"] = last_c
    return JSONResponse(out)


@app.get("/api/config")
def api_get_config():
    return read_config()


@app.post("/api/config")
async def api_set_config(req: Request):
    body = await req.json()
    cfg = read_config()
    cfg["expression"] = body.get("expression", cfg["expression"])
    cfg["settings"] = body.get("settings", cfg["settings"])
    if "description" in body:
        cfg["description"] = body["description"]
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "config": cfg}


@app.post("/api/backtest")
async def api_backtest(req: Request):
    body = await req.json()
    expression = (body.get("expression") or "").strip()
    settings = body.get("settings") or {}
    if not expression:
        return JSONResponse({"error": "expression 비어있음"}, status_code=400)
    try:
        m = backtest_alpha(expression, settings)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    if "error" in m:
        return JSONResponse({"error": m["error"]}, status_code=400)

    cum = m["cumulative"]  # pandas Series (1 + ret).cumprod()
    pnl_scaled = [float(v) * 1000 for v in cum.values]  # 시작 1000 기준
    labels = [pd.Timestamp(d).strftime("%b '%y") for d in cum.index]
    # 라벨 너무 많으면 솎기 (월 단위 근사)
    if len(labels) > 60:
        step = len(labels) // 60 + 1
        labels = [lb if i % step == 0 else "" for i, lb in enumerate(labels)]

    rets = m["returns"]
    year_rows = _year_rows_from_returns(rets, m)

    is_summary = {
        "sharpe": m["sharpe"], "turnover": m["avg_turnover"], "fitness": _fitness(m),
        "returns": m["total_return"], "drawdown": abs(m["mdd"]), "margin": m["total_return"] / max(m["avg_turnover"], 1e-6) / 100,
        "win": m["win_rate"], "avgMaxWeight": m["avg_max_weight"], "nDays": m["n_days"],
        "annual": m["annual_return"],
    }
    return {"isSummary": is_summary, "pnlScaled": pnl_scaled, "monthLabels": labels, "yearRows": year_rows}


def _fitness(m):
    import math
    tv = max(m["avg_turnover"], 0.01)
    return round(abs(m["sharpe"]) * math.sqrt(abs(m["annual_return"]) / tv), 2) if tv else 0


def _year_rows_from_returns(rets, m):
    """returns Series 를 연도별로 집계."""
    import numpy as np
    rows = []
    s = rets.copy()
    s.index = pd.to_datetime(s.index)
    for year, grp in s.groupby(s.index.year):
        if len(grp) < 2:
            continue
        cum = (1 + grp).prod() - 1
        sharpe = grp.mean() / grp.std() * np.sqrt(252) if grp.std() > 0 else 0
        run = (1 + grp).cumprod()
        dd = ((run - run.cummax()) / run.cummax()).min()
        rows.append({
            "year": int(year), "sharpe": round(float(sharpe), 2),
            "turnover": float(m["avg_turnover"]), "fitness": _fitness(m),
            "returns": float(cum), "drawdown": abs(float(dd)),
            "margin": float(cum) / max(m["avg_turnover"], 1e-6) / 100,
            "long": int(m.get("n_long", 0)) or 250, "short": int(m.get("n_short", 0)) or 250,
        })
    return rows or [{
        "year": datetime.now().year, "sharpe": round(m["sharpe"], 2),
        "turnover": m["avg_turnover"], "fitness": _fitness(m),
        "returns": m["total_return"], "drawdown": abs(m["mdd"]),
        "margin": m["total_return"] / max(m["avg_turnover"], 1e-6) / 100, "long": 250, "short": 250,
    }]


@app.post("/api/run")
async def api_run(req: Request):
    body = await req.json()
    mode = body.get("mode", "dry")
    args = [sys.executable, str(ROOT / "bot" / "run_alpha.py")]
    if mode == "dry":
        args.append("--dry-run")
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=180, cwd=str(ROOT),
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        return {"ok": r.returncode == 0, "output": (r.stdout + r.stderr)[-4000:]}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---- 정적 파일 (web/) ----
@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")

app.mount("/app", StaticFiles(directory=WEB_DIR / "app"), name="app")
