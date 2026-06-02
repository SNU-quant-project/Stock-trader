/* ===== Secondary tabs: Performance / Orders / Positions / Bot Logs / News ===== */

function Page({ title, sub, children, right }) {
  return (
    <div style={{ flex: 1, overflowY: "auto", overflowX: "hidden", background: "var(--res-alt)" }}>
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "26px 32px 56px" }}>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 20 }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: "var(--tx-on-light)" }}>{title}</h1>
            {sub && <div style={{ marginTop: 5, fontSize: 13, color: "var(--tx-on-light-2)" }}>{sub}</div>}
          </div>
          {right}
        </div>
        {children}
      </div>
    </div>
  );
}

function Card({ children, style, pad = 20 }) {
  return <div style={{ background: "#fff", border: "1px solid var(--res-line)", borderRadius: "var(--r-lg)", padding: pad, ...style }}>{children}</div>;
}

function SectionTitle({ children, style }) {
  return <h2 style={{ fontSize: 16, fontWeight: 700, color: "var(--tx-on-light)", margin: "0 0 14px", ...style }}>{children}</h2>;
}

// ---- market index cards (dark) ----
function MarketCards() {
  const D = window.AB_DATA;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14, marginBottom: 22 }}>
      {D.indices.map((ix) => {
        const c = ix.up ? "var(--up)" : "var(--down)";
        return (
          <div key={ix.sym} style={{ background: "#161a28", borderRadius: "var(--r-lg)", padding: "16px 18px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontSize: 12.5, color: "var(--tx-on-dark-2)" }}>{ix.label}</div>
              <div className="tabnum" style={{ fontSize: 21, fontWeight: 600, color: "#fff", marginTop: 5 }}>{fmtNum(ix.price)}</div>
              <div className="tabnum" style={{ fontSize: 12, color: c, marginTop: 2 }}>{ix.up ? "+" : ""}{fmtNum(ix.chg)} ({ix.up ? "+" : ""}{ix.pct.toFixed(2)}%)</div>
            </div>
            <Sparkline values={ix.spark} color={c} w={92} h={46} />
          </div>
        );
      })}
    </div>
  );
}

// ---- account metric cards ----
function AccountCards() {
  const a = window.AB_DATA.account;
  const items = [
    { l: "Equity", v: fmtUSD(a.equity, 2), s: fmtPct(a.dailyReturn) + " vs prev close", c: a.dailyReturn >= 0 ? "var(--up)" : "var(--down)" },
    { l: "Cash", v: fmtUSD(a.cash, 2), s: "Buying power " + fmtUSD0(a.buyingPower) },
    { l: "Positions", v: a.positions, s: "long + short" },
    { l: "Open Orders", v: a.openOrders, s: a.openOrders > 0 ? "미체결 — Orders 탭" : "none" },
    { l: "US Market", v: a.marketOpen ? "OPEN" : "CLOSED", s: "→ " + a.nextEvent, c: a.marketOpen ? "var(--up)" : "var(--down)" },
  ];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 14, marginBottom: 22 }}>
      {items.map((it) => (
        <Card key={it.l} pad={16}>
          <div style={{ fontSize: 12, color: "var(--tx-on-light-2)" }}>{it.l}</div>
          <div className="tabnum" style={{ fontSize: 21, fontWeight: 600, marginTop: 5, color: it.c || "var(--tx-on-light)" }}>{it.v}</div>
          <div style={{ fontSize: 11, color: "var(--tx-on-light-3)", marginTop: 3, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{it.s}</div>
        </Card>
      ))}
    </div>
  );
}

const DONUT_COLORS = ["#22a06b", "#2f7ce0", "#7c5cff", "#e0792f", "#16a36a", "#d94a6a", "#0fb5c4", "#9b8b3f", "#5b6577", "#c0c7d2"];

function SideBlock({ rows, title, dotColor, valueKey, weightFromCost }) {
  const total = rows.reduce((s, r) => s + Math.abs(r[valueKey]), 0) || 1;
  const sorted = [...rows].sort((a, b) => Math.abs(b[valueKey]) - Math.abs(a[valueKey]));
  const donutItems = sorted.slice(0, 6).map((r) => ({ label: r.sym, value: Math.abs(r[valueKey]) }));
  const totPl = rows.reduce((s, r) => s + (r.pl || 0), 0);
  return (
    <Card>
      <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 6 }}>
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: dotColor }} />
        <span style={{ fontSize: 16, fontWeight: 700 }}>{title}</span>
        <span style={{ fontSize: 12.5, color: "var(--tx-on-light-2)", fontWeight: 500 }}>
          {rows.length}종목 · {fmtUSD0(total)}
          {rows[0] && rows[0].pl !== undefined && <> · <span style={{ color: totPl >= 0 ? "var(--up)" : "var(--down)", fontWeight: 700 }}>PL {fmtUSD0(totPl)}</span></>}
        </span>
      </div>
      <Donut items={donutItems} size={190} colors={DONUT_COLORS} />
      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 14, fontSize: 12.5 }}>
        <thead>
          <tr style={{ color: "var(--tx-on-light-3)", fontSize: 11, textAlign: "left", borderBottom: "1px solid var(--res-line)" }}>
            <th style={{ padding: "7px 4px", fontWeight: 600 }}>Symbol</th>
            <th style={{ padding: "7px 4px", fontWeight: 600 }}>Company</th>
            <th style={{ padding: "7px 4px", fontWeight: 600, textAlign: "right" }}>Value</th>
            {rows[0] && rows[0].pl !== undefined && <th style={{ padding: "7px 4px", fontWeight: 600, textAlign: "right" }}>P&amp;L</th>}
            <th style={{ padding: "7px 4px", fontWeight: 600, textAlign: "right" }}>Weight</th>
          </tr>
        </thead>
        <tbody>
          {sorted.slice(0, 8).map((r) => (
            <tr key={r.sym} style={{ borderBottom: "1px solid #f0f2f6" }}>
              <td style={{ padding: "8px 4px", fontWeight: 700 }}>
                <a href={`https://finance.yahoo.com/quote/${r.sym}/`} target="_blank" rel="noopener noreferrer"
                   style={{ color: "var(--tx-on-light)", textDecoration: "none" }}
                   onMouseEnter={(e) => { e.currentTarget.style.color = "var(--cool)"; e.currentTarget.style.textDecoration = "underline"; }}
                   onMouseLeave={(e) => { e.currentTarget.style.color = "var(--tx-on-light)"; e.currentTarget.style.textDecoration = "none"; }}>{r.sym}</a>
              </td>
              <td style={{ padding: "8px 4px", maxWidth: 130, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                <a href={`https://finance.yahoo.com/quote/${r.sym}/`} target="_blank" rel="noopener noreferrer"
                   style={{ color: "var(--cool)", textDecoration: "none" }} title={r.name}>{r.name}</a>
              </td>
              <td className="tabnum" style={{ padding: "8px 4px", textAlign: "right" }}>{fmtUSD0(Math.abs(r[valueKey]))}</td>
              {r.pl !== undefined && <td className="tabnum" style={{ padding: "8px 4px", textAlign: "right", color: r.pl >= 0 ? "var(--up)" : "var(--down)", fontWeight: 600 }}>{fmtUSD0(r.pl)} ({fmtPct(r.plpc, 1)})</td>}
              <td className="tabnum" style={{ padding: "8px 4px", textAlign: "right", color: dotColor, fontWeight: 600 }}>{fmtPctRaw(Math.abs(r[valueKey]) / total, 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

// ===== Performance =====
function PerformanceTab() {
  const D = window.AB_DATA;
  const [period, setPeriod] = React.useState("1M");
  const eqVals = D.acctHist.map((h) => h.equity);
  const eqLabels = D.acctHist.map((h) => h.date);
  return (
    <Page title="Performance" sub="Alpaca 페이퍼 계좌의 실거래 성과. 봇 로그에 시점별 종목 PnL 도 누적됩니다.">
      <AccountCards />
      <Card style={{ marginBottom: 22 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
          <SectionTitle style={{ margin: 0 }}>Equity Curve</SectionTitle>
          <div style={{ display: "flex", gap: 3, background: "var(--res-alt)", borderRadius: 16, padding: 3, border: "1px solid var(--res-line)" }}>
            {["1W", "1M", "3M", "1Y", "ALL"].map((p) => (
              <button key={p} onClick={() => setPeriod(p)} style={{ padding: "5px 13px", borderRadius: 13, fontSize: 12, fontWeight: 700, background: p === period ? "var(--accent)" : "transparent", color: p === period ? "#fff" : "var(--tx-on-light-2)" }}>{p}</button>
            ))}
          </div>
        </div>
        <LineChart values={eqVals} labels={eqLabels} height={280} color="var(--accent)"
          yFmt={(v) => {
            const span = Math.max(...eqVals) - Math.min(...eqVals);
            // 값 폭이 작으면 (~$1K 미만) 소수점까지 표시해 라벨이 다 같은 "$100K" 로 뭉개지지 않게
            return span < 2000 ? "$" + (v / 1000).toFixed(2) + "K" : "$" + (v / 1000).toFixed(0) + "K";
          }} />
        <div style={{ fontSize: 12.5, color: "var(--tx-on-light-2)", marginTop: 8 }}>
          시작 {fmtUSD(eqVals[0])} → 현재 {fmtUSD(eqVals[eqVals.length - 1])} <span style={{ color: (eqVals[eqVals.length - 1] / eqVals[0] - 1) >= 0 ? "var(--up)" : "var(--down)", fontWeight: 700 }}>({fmtPct(eqVals[eqVals.length - 1] / eqVals[0] - 1)})</span> <span style={{ color: "var(--tx-on-light-3)" }}>· 기간 전체 기준 (상단 Equity 카드는 전일 대비)</span>
        </div>
      </Card>

      <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1fr", gap: 18, marginBottom: 22 }}>
        <Card>
          <SectionTitle>일별 수익률 &amp; 잔고</SectionTitle>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
            <thead><tr style={{ color: "var(--tx-on-light-3)", fontSize: 11, textAlign: "right", borderBottom: "1px solid var(--res-line)" }}>
              <th style={{ padding: "7px 4px", textAlign: "left", fontWeight: 600 }}>Date</th><th style={{ padding: "7px 4px", fontWeight: 600 }}>Equity</th><th style={{ padding: "7px 4px", fontWeight: 600 }}>Daily P&amp;L</th><th style={{ padding: "7px 4px", fontWeight: 600 }}>Return</th><th style={{ padding: "7px 4px", fontWeight: 600 }}>Cum</th>
            </tr></thead>
            <tbody>
              {D.dailyPerf.slice(0, 10).map((r) => (
                <tr key={r.date} style={{ borderBottom: "1px solid #f0f2f6" }}>
                  <td style={{ padding: "8px 4px", color: "var(--tx-on-light-2)" }}>{r.date}</td>
                  <td className="tabnum" style={{ padding: "8px 4px", textAlign: "right" }}>{fmtUSD(r.equity)}</td>
                  <td className="tabnum" style={{ padding: "8px 4px", textAlign: "right", color: r.pl >= 0 ? "var(--up)" : "var(--down)" }}>{fmtUSD(r.pl)}</td>
                  <td className="tabnum" style={{ padding: "8px 4px", textAlign: "right", color: r.ret >= 0 ? "var(--up)" : "var(--down)" }}>{fmtPct(r.ret, 3)}</td>
                  <td className="tabnum" style={{ padding: "8px 4px", textAlign: "right", color: r.cum >= 0 ? "var(--up)" : "var(--down)" }}>{fmtPct(r.cum)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <WinnersLosers />
      </div>
    </Page>
  );
}

function WinnersLosers() {
  const D = window.AB_DATA;
  const all = [...D.longs, ...D.shorts];
  const winners = [...all].sort((a, b) => b.pl - a.pl).slice(0, 6);
  const losers = [...all].sort((a, b) => a.pl - b.pl).slice(0, 6);
  const tbl = (rows, color, label) => (
    <div>
      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8, color }}>{label}</div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <tbody>
          {rows.map((r) => (
            <tr key={r.sym} style={{ borderBottom: "1px solid #f0f2f6" }}>
              <td style={{ padding: "6px 4px", fontWeight: 700 }}>
                <a href={`https://finance.yahoo.com/quote/${r.sym}/`} target="_blank" rel="noopener noreferrer"
                   style={{ color: "var(--tx-on-light)", textDecoration: "none" }}
                   onMouseEnter={(e) => { e.currentTarget.style.color = "var(--cool)"; e.currentTarget.style.textDecoration = "underline"; }}
                   onMouseLeave={(e) => { e.currentTarget.style.color = "var(--tx-on-light)"; e.currentTarget.style.textDecoration = "none"; }}>{r.sym}</a>
              </td>
              <td style={{ padding: "6px 4px" }}><span style={{ fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: 4, background: r.qty >= 0 ? "var(--cool-soft)" : "#fdeceb", color: r.qty >= 0 ? "var(--cool)" : "var(--down)" }}>{r.qty >= 0 ? "LONG" : "SHORT"}</span></td>
              <td className="tabnum" style={{ padding: "6px 4px", textAlign: "right", color: r.pl >= 0 ? "var(--up)" : "var(--down)", fontWeight: 600 }}>{fmtUSD0(r.pl)} ({fmtPct(r.plpc, 1)})</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
  return (
    <Card>
      <SectionTitle>종목별 손익 <span style={{ fontSize: 12, fontWeight: 500, color: "var(--tx-on-light-3)" }}>현재 보유 · 미실현</span></SectionTitle>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
        {tbl(winners, "var(--up)", "🟢 Top Winners")}
        {tbl(losers, "var(--down)", "🔴 Top Losers")}
      </div>
    </Card>
  );
}

// ===== Orders =====
function OrdersTab() {
  const D = window.AB_DATA;
  const [cancelled, setCancelled] = React.useState(false);
  const buys = cancelled ? [] : D.buyOrders, sells = cancelled ? [] : D.sellOrders;
  const n = buys.length + sells.length;
  return (
    <Page title="Open Orders" sub={`현재 미체결 주문 ${n}건. 비중 = qty × 최신 close 가격 기준 (cost basis).`}
      right={n > 0 && (
        <button onClick={() => setCancelled(true)} style={{ display: "flex", alignItems: "center", gap: 8, height: 40, padding: "0 18px", borderRadius: "var(--r-sm)", background: "var(--down)", color: "#fff", fontSize: 13.5, fontWeight: 700, whiteSpace: "nowrap" }}>
          🚫 미체결 {n}건 전체 취소
        </button>
      )}>
      {n === 0 ? (
        <Card><div style={{ textAlign: "center", padding: 40, color: "var(--tx-on-light-2)" }}>{cancelled ? "✓ 모든 미체결 주문이 취소되었습니다." : "미체결 주문이 없습니다."}</div></Card>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
          <SideBlock rows={buys} title="🟢 Long (BUY)" dotColor="var(--up)" valueKey="cost" />
          <SideBlock rows={sells} title="🔴 Short (SELL)" dotColor="var(--down)" valueKey="cost" />
        </div>
      )}
    </Page>
  );
}

// ===== Positions =====
function PositionsTab() {
  const D = window.AB_DATA;
  return (
    <Page title="Positions" sub="비중 = |market_value| / 총 gross. 회사명 클릭 → Yahoo Finance.">
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
        <SideBlock rows={D.longs} title="🟢 Long" dotColor="var(--up)" valueKey="marketValue" />
        <SideBlock rows={D.shorts} title="🔴 Short" dotColor="var(--down)" valueKey="marketValue" />
      </div>
    </Page>
  );
}

// ===== Bot Logs =====
function BotLogRow({ log }) {
  const [open, setOpen] = React.useState(false);
  const tone = log.status === "ok" ? "var(--up)" : log.status === "warn" ? "var(--accent)" : "var(--down)";
  const modeC = log.mode === "LIVE" ? { bg: "#fdeceb", tx: "var(--down)" } : { bg: "var(--cool-soft)", tx: "var(--cool)" };
  const s = log.settings || {};
  const hasDetail = log.expression || log.equity != null || (log.failedSample && log.failedSample.length);
  return (
    <Card pad={0}>
      {/* 헤더 (클릭하면 펼침) */}
      <div onClick={() => hasDetail && setOpen((o) => !o)}
        style={{ display: "flex", alignItems: "center", gap: 16, padding: "14px 20px", cursor: hasDetail ? "pointer" : "default" }}>
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: tone, flexShrink: 0 }} />
        <div style={{ minWidth: 150 }}>
          <div style={{ fontWeight: 700, fontSize: 14 }}>{log.at}</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--tx-on-light-3)" }}>{log.file}</div>
        </div>
        <span style={{ fontSize: 11, fontWeight: 700, padding: "3px 9px", borderRadius: 5, background: modeC.bg, color: modeC.tx, letterSpacing: 0.5 }}>{log.mode}</span>
        <div style={{ fontSize: 13, color: "var(--tx-on-light-2)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{log.note}</div>
        <div className="tabnum" style={{ display: "flex", gap: 18, fontSize: 12.5, color: "var(--tx-on-light-2)" }}>
          <span>orders <b style={{ color: "var(--tx-on-light)" }}>{log.orders}</b></span>
          <span style={{ color: "var(--cool)" }}>L {log.longs}</span>
          <span style={{ color: "var(--down)" }}>S {log.shorts}</span>
        </div>
        {hasDetail && <Icon name={open ? "chevU" : "chevD"} size={16} style={{ color: "var(--tx-on-light-3)", flexShrink: 0 }} />}
      </div>

      {/* 세부 디테일 */}
      {open && hasDetail && (
        <div style={{ borderTop: "1px solid var(--res-line)", padding: "16px 20px", background: "var(--res-alt)" }}>
          {log.expression && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--tx-on-light-3)", letterSpacing: 0.5, marginBottom: 5 }}>EXPRESSION</div>
              <pre style={{ margin: 0, fontFamily: "var(--font-mono)", fontSize: 12.5, color: "var(--tx-on-light)", background: "#fff", border: "1px solid var(--res-line)", borderRadius: 6, padding: "10px 12px", whiteSpace: "pre-wrap" }}>{log.expression}</pre>
            </div>
          )}
          <div style={{ display: "flex", flexWrap: "wrap", gap: "10px 28px", fontSize: 12.5, color: "var(--tx-on-light-2)", marginBottom: log.failedSample && log.failedSample.length ? 14 : 0 }}>
            {s.neutralization != null && <span>Neutralization <b style={{ color: "var(--tx-on-light)" }}>{s.neutralization}</b></span>}
            {s.decay != null && <span>Decay <b style={{ color: "var(--tx-on-light)" }}>{s.decay}</b></span>}
            {s.truncation != null && <span>Truncation <b style={{ color: "var(--tx-on-light)" }}>{s.truncation}</b></span>}
            {s.delay != null && <span>Delay <b style={{ color: "var(--tx-on-light)" }}>{s.delay}</b></span>}
            {log.equity != null && <span>Equity <b style={{ color: "var(--tx-on-light)" }}>{fmtUSD0(log.equity)}</b></span>}
            {log.universeSize != null && <span>Universe <b style={{ color: "var(--tx-on-light)" }}>{log.universeSize}</b></span>}
            {log.panelLast && <span>Panel last <b style={{ color: "var(--tx-on-light)" }}>{log.panelLast}</b></span>}
            <span>제출 <b style={{ color: "var(--up)" }}>{log.nSubmitted}</b> · 실패 <b style={{ color: "var(--down)" }}>{log.nFailed}</b>{log.preCancelled ? ` · 사전취소 ${log.preCancelled}` : ""}</span>
          </div>
          {log.failedSample && log.failedSample.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--down)", letterSpacing: 0.5, marginBottom: 5 }}>FAILED ORDERS ({log.nFailed})</div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <tbody>
                  {log.failedSample.map((x, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid #f0f2f6" }}>
                      <td style={{ padding: "5px 4px", fontWeight: 700, width: 70 }}>{x.symbol}</td>
                      <td className="tabnum" style={{ padding: "5px 4px", width: 70, color: "var(--tx-on-light-2)" }}>{x.qty}</td>
                      <td style={{ padding: "5px 4px", color: "var(--down)" }}>{x.error}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

function BotLogsTab() {
  const D = window.AB_DATA;
  return (
    <Page title="Bot Logs" sub="매 봇 실행 기록. LIVE 는 Alpaca 에 실주문 제출, DRY 는 시뮬레이션만. 행 클릭 시 세부 디테일.">
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {D.botLogs.map((log) => <BotLogRow key={log.file} log={log} />)}
      </div>
    </Page>
  );
}

// ===== News =====
function NewsTab() {
  const D = window.AB_DATA;
  return (
    <Page title="Market News" sub="CNBC (Markets · Finance · Economy) · MarketWatch 시장 헤드라인. 상담칼럼·라이프스타일 제외.">
      <MarketCards />
      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 18 }}>
        <Card>
          <SectionTitle>주요 헤드라인</SectionTitle>
          <div style={{ display: "flex", flexDirection: "column" }}>
            {D.news.map((n, i) => (
              <a key={i} href={n.link || "#"} target="_blank" rel="noopener noreferrer"
                style={{ display: "flex", gap: 14, padding: "13px 0", textDecoration: "none",
                  borderBottom: i < D.news.length - 1 ? "1px solid #f0f2f6" : "none",
                  cursor: n.link ? "pointer" : "default", borderRadius: 6, transition: "background .12s" }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "var(--res-alt)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}>
                <div style={{ flex: 1, padding: "0 8px" }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "var(--tx-on-light)", lineHeight: 1.4 }}>{n.title}</div>
                  <div style={{ fontSize: 12.5, color: "var(--tx-on-light-2)", marginTop: 3 }}>{n.titleKo}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 7 }}>
                    <span style={{ fontSize: 11, color: "var(--tx-on-light-3)" }}>{n.pub} · {n.ago}</span>
                    {n.tickers.map((t) => <span key={t} style={{ fontSize: 10.5, fontWeight: 700, fontFamily: "var(--font-mono)", padding: "1px 6px", borderRadius: 4, background: "var(--accent-soft)", color: "var(--accent-lo)" }}>${t}</span>)}
                  </div>
                </div>
                <Icon name="ext" size={15} style={{ color: "var(--tx-on-light-3)", flexShrink: 0, marginTop: 3 }} />
              </a>
            ))}
          </div>
        </Card>
        <Card style={{ alignSelf: "flex-start", background: "linear-gradient(160deg,#0f1320,#161a28)", border: "none" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 14 }}>
            <AlphaMark size={20} color="var(--accent-hi)" />
            <span style={{ fontSize: 15, fontWeight: 700, color: "#fff", whiteSpace: "nowrap" }}>AI 시장 요약</span>
            <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 4, background: "rgba(34,160,107,0.2)", color: "var(--accent-hi)", letterSpacing: 0.5 }}>CLAUDE</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {D.aiSummary.map((s, i) => (
              <div key={i} style={{ display: "flex", gap: 10, fontSize: 13, color: "var(--tx-on-dark)", lineHeight: 1.5 }}>
                <span className="tabnum" style={{ color: "var(--accent-hi)", fontWeight: 700, flexShrink: 0 }}>{i + 1}</span>
                <span dangerouslySetInnerHTML={{ __html: s.replace(/\$(\w+)/g, '<b style="color:var(--accent-hi)">$$$1</b>') }} />
              </div>
            ))}
          </div>
        </Card>
      </div>
    </Page>
  );
}

Object.assign(window, { PerformanceTab, OrdersTab, PositionsTab, BotLogsTab, NewsTab, Page, Card });
