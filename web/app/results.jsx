/* ===== Results pane (light) ===== */

const RAIL = ["chart", "bars", "scatterDots", "clipboard", "toggle", "edit", "gear"];

function ResultRail() {
  const [active, setActive] = React.useState(0);
  return (
    <div style={{ width: 46, flexShrink: 0, background: "var(--res-rail)", borderRight: "1px solid var(--res-line)", display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 10, gap: 4 }}>
      {RAIL.map((ic, i) => {
        const on = i === active;
        return (
          <button key={i} onClick={() => setActive(i)} title={ic} style={{
            width: 34, height: 34, borderRadius: 7, display: "grid", placeItems: "center",
            color: on ? "var(--accent-lo)" : "var(--tx-on-light-3)",
            background: on ? "var(--accent-soft)" : "transparent",
          }}
            onMouseEnter={(e) => { if (!on) e.currentTarget.style.background = "#e7eaf0"; }}
            onMouseLeave={(e) => { if (!on) e.currentTarget.style.background = "transparent"; }}>
            <Icon name={ic} size={18} sw={1.7} />
          </button>
        );
      })}
    </div>
  );
}

function EmptyResults() {
  return (
    <div style={{ flex: 1, display: "grid", placeItems: "center", color: "var(--tx-on-light-3)" }}>
      <div style={{ textAlign: "center" }}>
        <Icon name="chart" size={40} sw={1.3} style={{ opacity: 0.4 }} />
        <div style={{ marginTop: 14, fontSize: 15 }}>Simulate an alpha to view the results here.</div>
        <div style={{ marginTop: 6, fontSize: 12.5, color: "var(--tx-on-light-3)", whiteSpace: "nowrap" }}>좌측 코드 입력 후 <b style={{ color: "var(--accent-lo)" }}>Simulate</b> 를 누르세요.</div>
      </div>
    </div>
  );
}

function RunningResults({ progress }) {
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 80, gap: 26 }}>
      <div style={{ width: 420, maxWidth: "80%" }}>
        <div style={{ height: 18, borderRadius: 9, background: "#eceef3", overflow: "hidden", display: "flex", alignItems: "center" }}>
          <div style={{ height: "100%", width: progress + "%", background: "linear-gradient(90deg,var(--accent-lo),var(--accent-hi))", borderRadius: 9, transition: "width .2s" }} />
        </div>
        <div style={{ textAlign: "center", marginTop: 10, fontFamily: "var(--font-num)", fontWeight: 600, color: "var(--tx-on-light-2)" }}>{Math.round(progress)}%</div>
      </div>
      <div style={{ textAlign: "center", color: "var(--tx-on-light-2)", fontSize: 14, lineHeight: 1.6 }}>
        백테스트 실행 중입니다. 보통 수십 초가 소요됩니다.<br />
        <span style={{ fontSize: 12.5, color: "var(--tx-on-light-3)" }}>group operator 사용 시 더 오래 걸릴 수 있습니다.</span>
      </div>
      <div style={{ border: "1px solid var(--res-line)", borderRadius: "var(--r-lg)", padding: "18px 26px", maxWidth: 460, textAlign: "center", background: "var(--res-alt)" }}>
        <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: 1, color: "var(--tx-on-light-2)" }}>TIP</div>
        <div style={{ marginTop: 8, fontSize: 13.5, color: "var(--tx-on-light-2)", lineHeight: 1.55 }}>
          Sharpe 1.0 이상 & Turnover 70% 미만인 알파가 페이퍼 계좌에서 더 안정적으로 동작합니다.
        </div>
      </div>
    </div>
  );
}

// ---- metric strip ----
function MetricItem({ label, value, color, sub, style }) {
  return (
    <div style={{ minWidth: 0, ...style }}>
      <div style={{ fontSize: 11.5, color: "var(--tx-on-light-2)", display: "flex", alignItems: "center", gap: 4, fontWeight: 500 }}>
        {label}<span style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--cool)", opacity: 0.6 }} />
      </div>
      <div className="tabnum" style={{ fontSize: 23, fontWeight: 600, marginTop: 3, color: color || "var(--tx-on-light)", whiteSpace: "nowrap" }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: "var(--tx-on-light-3)" }}>{sub}</div>}
    </div>
  );
}

function Pill({ icon, children, tone }) {
  const tones = {
    warn: { bg: "#fff4e8", bd: "#f3d3a8", tx: "#b9760f", dot: "#e0792f" },
    cool: { bg: "var(--cool-soft)", bd: "#bcd6f7", tx: "#1d62c0", dot: "var(--cool)" },
  };
  const c = tones[tone] || tones.cool;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "7px 13px", borderRadius: 18, background: c.bg, border: `1px solid ${c.bd}`, color: c.tx, fontSize: 12.5, fontWeight: 600 }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: c.dot }} />{children}
    </span>
  );
}

function ChartSelect() {
  const [v, setV] = React.useState("PnL");
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h); return () => document.removeEventListener("mousedown", h);
  }, []);
  const opts = ["PnL", "Cumulative Return", "Drawdown", "Daily Return"];
  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button onClick={() => setOpen((o) => !o)} style={{
        display: "flex", alignItems: "center", justifyContent: "space-between", gap: 30, minWidth: 220,
        padding: "9px 14px", border: "1px solid var(--res-line)", borderRadius: "var(--r-sm)",
        background: "#fff", color: "var(--tx-on-light)", fontSize: 14, fontWeight: 500,
      }}>{v}<Icon name="chevD" size={16} style={{ color: "var(--tx-on-light-3)" }} /></button>
      {open && (
        <div style={{ position: "absolute", top: "calc(100% + 4px)", right: 0, left: 0, zIndex: 20, background: "#fff", border: "1px solid var(--res-line)", borderRadius: "var(--r-sm)", boxShadow: "0 12px 30px rgba(0,0,0,0.12)", overflow: "hidden" }}>
          {opts.map((o) => (
            <button key={o} onClick={() => { setV(o); setOpen(false); }} style={{ display: "block", width: "100%", textAlign: "left", padding: "9px 14px", fontSize: 13.5, color: o === v ? "var(--accent-lo)" : "var(--tx-on-light)", background: o === v ? "var(--accent-soft)" : "#fff", fontWeight: o === v ? 600 : 400 }}>{o}</button>
          ))}
        </div>
      )}
    </div>
  );
}

function YearTable({ rows }) {
  const cols = ["Year", "Sharpe", "Turnover", "Fitness", "Returns", "Drawdown", "Margin", "Long", "Short"];
  return (
    <div style={{ border: "1px solid var(--res-line)", borderRadius: "var(--r-md)", overflowX: "auto" }}>
      <table style={{ width: "100%", minWidth: 620, borderCollapse: "collapse", fontFamily: "var(--font-num)", fontSize: 13 }}>
        <thead>
          <tr style={{ background: "#2b3344", color: "#fff" }}>
            {cols.map((c, i) => (
              <th key={c} style={{ textAlign: i === 0 ? "left" : "right", padding: "11px 16px", fontWeight: 600, fontSize: 12, fontFamily: "var(--font-ui)", letterSpacing: 0.3 }}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(rows || []).map((r, i) => (
            <tr key={r.year} style={{ background: i % 2 ? "var(--res-alt)" : "#fff" }}>
              <td style={{ padding: "11px 16px", fontWeight: 700, color: "var(--tx-on-light)" }}>{r.year}</td>
              <td style={cellR(r.sharpe >= 1 ? "var(--up)" : "var(--tx-on-light)")}>{r.sharpe.toFixed(2)}</td>
              <td style={cellR()}>{fmtPctRaw(r.turnover)}</td>
              <td style={cellR()}>{r.fitness.toFixed(2)}</td>
              <td style={cellR(r.returns >= 0 ? "var(--up)" : "var(--down)")}>{fmtPctRaw(r.returns)}</td>
              <td style={cellR("var(--down)")}>{fmtPctRaw(r.drawdown)}</td>
              <td style={cellR()}>{fmtPermil(r.margin)}</td>
              <td style={cellR()}>{r.long}</td>
              <td style={cellR()}>{r.short}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function cellR(color) { return { padding: "11px 16px", textAlign: "right", color: color || "var(--tx-on-light-2)" }; }

function DoneResults({ result, tweaks }) {
  const D = result || window.AB_DATA;
  const s = D.isSummary;
  if (!s) return <EmptyResults />;
  const cardStyle = tweaks.resultsStyle === "cards";
  const rangeLabel = (D.start && D.end) ? `${D.start} ~ ${D.end}` : null;
  return (
    <div className="fadeUp" style={{ flex: 1, overflowY: "auto", overflowX: "hidden" }}>
      <div style={{ padding: "20px 26px 40px", minWidth: 0 }}>
        {/* chart */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 19, fontWeight: 700, color: "var(--tx-on-light)" }}>
            <Icon name="chart" size={20} style={{ color: "var(--accent-lo)" }} /> Chart
          </div>
          <ChartSelect />
        </div>
        <LineChart values={D.pnlScaled} labels={D.monthLabels} height={300} color="var(--accent)"
          yFmt={(v) => (v >= 1000 ? (v / 1000).toFixed(0) + "K" : v.toFixed(0))} />

        {/* IS summary header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", margin: "30px 0 16px", flexWrap: "wrap", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 19, fontWeight: 700 }}>
            <Icon name="bars" size={19} style={{ color: "var(--accent-lo)" }} /> IS Summary
          </div>
          {rangeLabel && (
            <div style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 12.5, color: "var(--tx-on-light-2)", fontWeight: 600 }}>
              <Icon name="doc" size={14} style={{ color: "var(--tx-on-light-3)" }} />
              백테스트 기간 <span className="tabnum" style={{ color: "var(--tx-on-light)" }}>{rangeLabel}</span>
            </div>
          )}
        </div>
        <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
          <Pill tone="warn">{s.sharpe >= 1.3 ? "Production Ready" : "Needs Improvement"}</Pill>
          <Pill tone="cool">Single Data Set Alpha</Pill>
        </div>

        {/* aggregate metrics */}
        <div style={{
          display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap",
          padding: cardStyle ? "18px 20px" : "0 0 4px",
          border: cardStyle ? "1px solid var(--res-line)" : "none",
          borderRadius: cardStyle ? "var(--r-md)" : 0,
          background: cardStyle ? "var(--res-alt)" : "transparent",
          marginBottom: 22,
        }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--tx-on-light)", minWidth: 110 }}>Aggregate Data</div>
          <MetricItem label="Sharpe" value={s.sharpe.toFixed(2)} color="var(--up)" />
          <MetricItem label="Turnover" value={fmtPctRaw(s.turnover, 0)} />
          <MetricItem label="Fitness" value={s.fitness.toFixed(2)} />
          <MetricItem label="Returns" value={fmtPctRaw(s.returns)} color={s.returns >= 0 ? "var(--up)" : "var(--down)"} />
          <MetricItem label="Drawdown" value={fmtPctRaw(s.drawdown)} color="var(--down)" />
          <MetricItem label="Margin" value={fmtPermil(s.margin)} />
        </div>

        <YearTable rows={D.yearRows} />

        {/* secondary metrics */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14, marginTop: 20 }}>
          {[["Total Return", fmtPct(s.total != null ? s.total : 0), (s.total >= 0 ? "var(--up)" : "var(--down)")], ["Win Rate", fmtPctRaw(s.win), null], ["Avg Max Weight", fmtPctRaw(s.avgMaxWeight), null], ["Trading Days", s.nDays + "일", null]].map(([l, v, c]) => (
            <div key={l} style={{ border: "1px solid var(--res-line)", borderRadius: "var(--r-md)", padding: "13px 16px" }}>
              <div style={{ fontSize: 11.5, color: "var(--tx-on-light-2)" }}>{l}</div>
              <div className="tabnum" style={{ fontSize: 20, fontWeight: 600, marginTop: 4, color: c || "var(--tx-on-light)" }}>{v}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ResultsBottomBar({ simState, onDry, onLive }) {
  const ready = simState === "done";
  const link = (icon, label, on, fn) => (
    <button onClick={fn} disabled={!on} style={{ display: "flex", alignItems: "center", gap: 8, color: on ? "var(--tx-on-light-2)" : "var(--tx-on-light-3)", fontSize: 12.5, fontWeight: 600, whiteSpace: "nowrap", opacity: on ? 1 : 0.5, cursor: on ? "pointer" : "default" }}>
      <Icon name={icon} size={17} />{label}
    </button>
  );
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 26, padding: "0 22px", height: 60, borderTop: "1px solid var(--res-line)", background: "var(--res-alt)", flexShrink: 0 }}>
      {link("list", "Save Config", ready)}
      {link("ext", "Open in new tab", ready)}
      <div style={{ flex: 1 }} />
      <button onClick={onDry} disabled={!ready} style={{
        display: "flex", alignItems: "center", gap: 8, height: 40, padding: "0 22px", borderRadius: "var(--r-sm)",
        fontSize: 13.5, fontWeight: 600, border: "1px solid var(--res-line)", whiteSpace: "nowrap",
        background: ready ? "#fff" : "transparent", color: ready ? "var(--tx-on-light)" : "var(--tx-on-light-3)",
        opacity: ready ? 1 : 0.55, cursor: ready ? "pointer" : "default",
      }}><Icon name="flask" size={16} /> Save & Dry Run</button>
      <button onClick={onLive} disabled={!ready} style={{
        display: "flex", alignItems: "center", gap: 8, height: 40, padding: "0 26px", borderRadius: "var(--r-sm)",
        fontSize: 13.5, fontWeight: 700, letterSpacing: 0.3, whiteSpace: "nowrap",
        background: ready ? "var(--down)" : "#e9ecf1", color: ready ? "#fff" : "var(--tx-on-light-3)",
        cursor: ready ? "pointer" : "default",
      }}>
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: ready ? "#fff" : "var(--tx-on-light-3)" }} /> Save &amp; Run LIVE
      </button>
    </div>
  );
}

function ResultsPane({ simState, progress, result, onDry, onLive, tweaks }) {
  return (
    <div style={{ display: "flex", height: "100%", background: "var(--res-bg)", minWidth: 0 }}>
      <div style={{ display: "flex", flexDirection: "column", flex: 1, minWidth: 0 }}>
        {simState === "idle" && <EmptyResults />}
        {simState === "running" && <RunningResults progress={progress} />}
        {simState === "done" && <DoneResults result={result} tweaks={tweaks} />}
        <ResultsBottomBar simState={simState} onDry={onDry} onLive={onLive} />
      </div>
    </div>
  );
}

Object.assign(window, { ResultsPane });
