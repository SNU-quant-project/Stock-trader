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

// ---- 지표 설명 (WorldQuant BRAIN 문구) ----
const METRIC_TIPS = {
  Sharpe: { title: "SHARPE", text: "위험 대비 수익률 지표. Sharpe = 연율화 평균 수익률 / 연율화 수익률 표준편차." },
  Turnover: { title: "TURNOVER", text: "일평균 거래 활동 정도. Turnover = 거래된 금액 / 보유 금액." },
  Fitness: { title: "FITNESS", text: "전반적 성과를 나타내는 종합 지표. 높을수록 좋음. Fitness = Sharpe × √( |Returns| / max(Turnover, 0.125) )." },
  Returns: { title: "RETURNS", text: "투자 금액 대비 연율화 평균 손익. (투자 금액 = 북사이즈의 절반)" },
  Drawdown: { title: "DRAWDOWN", text: "해당 기간 PnL 의 최대 낙폭(고점 대비 최대 하락)을 % 로 표시." },
  Margin: { title: "MARGIN", text: "거래 1달러당 벌어들인 수익(‰, 천분율). Margin ≈ Returns / Turnover." },
};

// ---- hover 설명 동그라미 ----
function InfoDot({ tip }) {
  const [pos, setPos] = React.useState(null);
  if (!tip) return <span style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--cool)", opacity: 0.6 }} />;
  const show = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const x = Math.min(Math.max(r.left + r.width / 2, 170), (window.innerWidth || 1400) - 170);
    setPos({ x, y: r.bottom + 8 });
  };
  // hover 영역을 넓히려 padding 둔 래퍼, 가운데 작은 점.
  const target = (
    <span onMouseEnter={show} onMouseMove={show} onMouseLeave={() => setPos(null)}
      style={{ display: "inline-flex", alignItems: "center", padding: "3px 4px", margin: "-3px -4px", cursor: "help", verticalAlign: "middle" }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--cool)" }} />
    </span>
  );
  // 툴팁은 body 로 portal → 조상의 transform/overflow 에 안 잘림
  const tooltip = pos && ReactDOM.createPortal(
    <div style={{
      position: "fixed", left: pos.x, top: pos.y, transform: "translateX(-50%)", zIndex: 9999,
      width: 300, maxWidth: "90vw", background: "#4a9fe0", color: "#fff", borderRadius: 8, padding: "12px 15px",
      boxShadow: "0 14px 34px rgba(0,0,0,0.28)", fontSize: 12.5, lineHeight: 1.5, pointerEvents: "none",
    }}>
      <div style={{ fontWeight: 700, letterSpacing: 0.6, marginBottom: 6 }}>{tip.title}</div>
      <div>{tip.text}</div>
    </div>,
    document.body
  );
  return <React.Fragment>{target}{tooltip}</React.Fragment>;
}

// ---- metric strip ----
function MetricItem({ label, value, color, sub, style }) {
  return (
    <div style={{ minWidth: 0, ...style }}>
      <div style={{ fontSize: 11.5, color: "var(--tx-on-light-2)", display: "flex", alignItems: "center", gap: 4, fontWeight: 500 }}>
        {label}<InfoDot tip={METRIC_TIPS[label]} />
      </div>
      <div className="tabnum" style={{ fontSize: 23, fontWeight: 600, marginTop: 3, color: color || "var(--tx-on-light)", whiteSpace: "nowrap" }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: "var(--tx-on-light-3)" }}>{sub}</div>}
    </div>
  );
}

// ---- Fitness 등급 배지 (BRAIN 스타일) ----
function FitnessGrade({ fitness }) {
  const g = fitness <= 1.0 ? { label: "Needs Improvement", c: "#e0463e", bg: "#fdecea", glyph: "✕" }
          : fitness <= 1.5 ? { label: "Good", c: "#2f7ce0", bg: "#eef2f7", glyph: "★" }
          : fitness <= 2.0 ? { label: "Excellent", c: "#16a36a", bg: "#e7f6ef", glyph: "✦" }
          : { label: "Spectacular", c: "#e0792f", bg: "#fff4e8", glyph: "❂" };
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "6px 14px 6px 8px", borderRadius: 20, background: g.bg, border: `1px solid ${g.c}55` }}>
      <span style={{ width: 20, height: 20, borderRadius: "50%", display: "grid", placeItems: "center", border: `1.6px solid ${g.c}`, color: g.c, fontSize: 11, fontWeight: 700, lineHeight: 1 }}>{g.glyph}</span>
      <span style={{ fontSize: 13, fontWeight: 700, color: g.c }}>{g.label}</span>
    </span>
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

const CHART_OPTS = ["PnL", "Cumulative Return", "Drawdown", "Daily Return"];
function ChartSelect({ value, onChange }) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h); return () => document.removeEventListener("mousedown", h);
  }, []);
  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button onClick={() => setOpen((o) => !o)} style={{
        display: "flex", alignItems: "center", justifyContent: "space-between", gap: 30, minWidth: 220,
        padding: "9px 14px", border: "1px solid var(--res-line)", borderRadius: "var(--r-sm)",
        background: "#fff", color: "var(--tx-on-light)", fontSize: 14, fontWeight: 500,
      }}>{value}<Icon name="chevD" size={16} style={{ color: "var(--tx-on-light-3)" }} /></button>
      {open && (
        <div style={{ position: "absolute", top: "calc(100% + 4px)", right: 0, left: 0, zIndex: 20, background: "#fff", border: "1px solid var(--res-line)", borderRadius: "var(--r-sm)", boxShadow: "0 12px 30px rgba(0,0,0,0.12)", overflow: "hidden" }}>
          {CHART_OPTS.map((o) => (
            <button key={o} onClick={() => { onChange(o); setOpen(false); }} style={{ display: "block", width: "100%", textAlign: "left", padding: "9px 14px", fontSize: 13.5, color: o === value ? "var(--accent-lo)" : "var(--tx-on-light)", background: o === value ? "var(--accent-soft)" : "#fff", fontWeight: o === value ? 600 : 400 }}>{o}</button>
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
  const [chartType, setChartType] = React.useState("PnL");
  if (!s) return <EmptyResults />;
  const cardStyle = tweaks.resultsStyle === "cards";
  const rangeLabel = (D.start && D.end) ? `${D.start} ~ ${D.end}` : null;

  // 선택된 차트 시계열 + 색/포맷
  const charts = D.charts || { PnL: D.pnlScaled };
  const series = charts[chartType] || charts.PnL || [];
  const chartStyle = {
    "PnL": { color: "var(--accent)", fmt: (v) => "$" + (Math.abs(v) >= 1000 ? (v / 1000).toFixed(0) + "K" : v.toFixed(0)) },
    "Cumulative Return": { color: "var(--accent)", fmt: (v) => v.toFixed(0) + "%" },
    "Drawdown": { color: "var(--down)", fmt: (v) => v.toFixed(0) + "%" },
    "Daily Return": { color: "var(--cool)", fmt: (v) => v.toFixed(1) + "%" },
  }[chartType] || { color: "var(--accent)", fmt: (v) => v.toFixed(0) };

  return (
    <div className="fadeUp" style={{ flex: 1, overflowY: "auto", overflowX: "hidden" }}>
      <div style={{ padding: "20px 26px 40px", minWidth: 0 }}>
        {/* chart */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 19, fontWeight: 700, color: "var(--tx-on-light)" }}>
            <Icon name="chart" size={20} style={{ color: "var(--accent-lo)" }} /> Chart
          </div>
          <ChartSelect value={chartType} onChange={setChartType} />
        </div>
        <LineChart key={chartType} values={series} labels={D.monthLabels} height={300}
          color={chartStyle.color} yFmt={chartStyle.fmt} />

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
        <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap", alignItems: "center" }}>
          <FitnessGrade fitness={s.fitness} />
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
