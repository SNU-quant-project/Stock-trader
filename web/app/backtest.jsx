/* ===== Backtest workspace shell (left pane: subbar + editor + settings + actions) ===== */

const NEUT_OPTIONS = ["None", "Market", "Sector", "Cap Bucket", "Sector + Cap Bucket", "Subindustry"];

function SettingsPanel({ settings, setSettings, onClose, onApply }) {
  const s = settings;
  const set = (k, v) => setSettings((p) => ({ ...p, [k]: v }));
  return (
    <div style={{
      position: "absolute", top: 0, left: 0, right: 0, zIndex: 25,
      background: "var(--panel-bg)", borderBottom: "1px solid var(--panel-border)",
      boxShadow: "0 20px 50px rgba(0,0,0,0.5)", padding: "22px 24px 24px",
      animation: "fadeUp .2s ease both",
    }}>
      {/* 이 프로젝트에서 실제로 백테스트에 반영되는 세팅만 노출.
          유니버스/리전/봉주기는 고정(USA · S&P 500 · 일봉)이라 상단 라벨로만 표시. */}
      <div style={{ fontSize: 11.5, color: "var(--tx-on-dark-3)", marginBottom: 14 }}>
        고정: <b style={{ color: "var(--tx-on-dark-2)" }}>USA · S&amp;P 500 · 일봉(D1)</b> — 아래 4개 세팅이 백테스트에 반영됩니다.
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr 1fr 1fr", gap: "18px 20px" }}>
        <Field label="Neutralization"><DarkSelect value={s.neutralization} options={NEUT_OPTIONS} onChange={(v) => set("neutralization", v)} /></Field>
        <Field label="Delay"><DarkSelect value={String(s.delay)} options={["0", "1"]} onChange={(v) => set("delay", +v)} /></Field>
        <Field label="Decay"><NumInput value={s.decay} step={1} onChange={(v) => set("decay", v)} /></Field>
        <Field label="Truncation"><NumInput value={s.truncation} step={0.01} dec={2} onChange={(v) => set("truncation", v)} /></Field>
      </div>

      <div style={{ display: "flex", alignItems: "center", marginTop: 22 }}>
        <button onClick={onClose} style={{
          fontSize: 12, fontWeight: 600, color: "var(--cool)", background: "rgba(47,124,224,0.1)",
          border: "1px solid rgba(47,124,224,0.3)", padding: "8px 14px", borderRadius: "var(--r-sm)",
        }}>Save as Default</button>
        <div style={{ flex: 1 }} />
        <button onClick={onApply} style={{
          fontSize: 14, fontWeight: 700, color: "#fff", background: "var(--accent)",
          padding: "11px 56px", borderRadius: "var(--r-sm)", letterSpacing: 0.3,
        }}
          onMouseEnter={(e) => e.currentTarget.style.background = "var(--accent-hi)"}
          onMouseLeave={(e) => e.currentTarget.style.background = "var(--accent)"}>Apply</button>
      </div>
    </div>
  );
}

function NumInput({ value, onChange, step = 1, dec = 0, suffix }) {
  return (
    <div style={{ flex: 1, position: "relative", borderBottom: "1px solid var(--panel-border)" }}>
      <input type="number" value={value} step={step}
        onChange={(e) => onChange(e.target.value === "" ? 0 : (dec ? parseFloat(e.target.value) : parseInt(e.target.value)))}
        style={{
          width: "100%", background: "transparent", border: "none", outline: "none",
          color: "var(--tx-on-dark)", fontFamily: "var(--font-num)", fontSize: 15, padding: "6px 2px 7px",
        }} />
      {suffix && <span style={{ position: "absolute", right: 2, bottom: 9, fontSize: 9.5, letterSpacing: 1, color: "var(--tx-on-dark-3)", fontWeight: 600 }}>{suffix}</span>}
    </div>
  );
}

// ---- example picker ----
function ExamplePicker({ onPick }) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button onClick={() => setOpen((o) => !o)} style={{
        display: "flex", alignItems: "center", gap: 8, height: 42, padding: "0 22px",
        background: "#1a1f2e", color: "var(--tx-on-dark)", borderRadius: "var(--r-sm)",
        fontSize: 13.5, fontWeight: 600, border: "1px solid #2a3145",
      }}>
        <Icon name="list" size={15} /> Example <Icon name="chevU" size={14} style={{ opacity: 0.6 }} />
      </button>
      {open && (
        <div style={{ position: "absolute", bottom: "calc(100% + 6px)", left: 0, zIndex: 40, minWidth: 280,
          background: "#0f1320", border: "1px solid #2a3145", borderRadius: "var(--r-sm)", boxShadow: "0 16px 40px rgba(0,0,0,0.6)", overflow: "hidden" }}>
          {window.AB_DATA.examples.map((ex) => (
            <button key={ex.label} onClick={() => { onPick(ex.expr); setOpen(false); }} style={{
              display: "block", width: "100%", textAlign: "left", padding: "10px 14px",
              color: "var(--tx-on-dark-2)", fontSize: 13, borderBottom: "1px solid #1b2030",
            }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.05)"; e.currentTarget.style.color = "#fff"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--tx-on-dark-2)"; }}>
              <div style={{ fontWeight: 600 }}>{ex.label}</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--syn-fn)", marginTop: 3, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{ex.expr.split("\n")[0]}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---- left editor pane ----
function EditorPane({ expr, setExpr, settings, setSettings, showSettings, setShowSettings, simState, onSimulate, tweaks }) {
  const s = settings;
  const breadcrumb = `${s.region}/D${s.delay}/${s.universe.replace(/\s/g, "")}`;
  const canSim = simState !== "running" && expr.trim().length > 0;
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", width: "100%", background: "var(--editor-bg)", minWidth: 0 }}>
      {/* sub bar */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, height: 48, padding: "0 14px", background: "var(--simbar-bg)", borderBottom: "1px solid var(--simbar-line)", flexShrink: 0, position: "relative", zIndex: 26 }}>
        <button onClick={() => setShowSettings((v) => !v)} style={{
          display: "flex", alignItems: "center", gap: 8, height: 32, padding: "0 14px", borderRadius: 16,
          fontSize: 13, fontWeight: 600,
          background: showSettings ? "var(--cool)" : "rgba(47,124,224,0.85)", color: "#fff",
        }}>
          <Icon name="gear" size={15} /> Settings
        </button>
        <span style={{ fontFamily: "var(--font-num)", fontSize: 13, fontWeight: 700, letterSpacing: 1.5, color: "var(--tx-on-dark)" }}>{breadcrumb}</span>
      </div>

      {/* editor body */}
      <div style={{ position: "relative", flex: 1, minHeight: 0 }}>
        <CodeEditor expr={expr} setExpr={setExpr} tweaks={tweaks} />
        {showSettings && <SettingsPanel settings={settings} setSettings={setSettings} onClose={() => setShowSettings(false)} onApply={() => setShowSettings(false)} />}
      </div>

      {/* action bar */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: 16, background: "var(--editor-bg)", borderTop: "1px solid var(--editor-line)", flexShrink: 0 }}>
        <ExamplePicker onPick={setExpr} />
        <button onClick={onSimulate} disabled={!canSim} style={{
          display: "flex", alignItems: "center", gap: 9, height: 46, padding: "0 40px", borderRadius: "var(--r-sm)",
          fontSize: 15, fontWeight: 700, letterSpacing: 0.3,
          background: canSim ? "var(--accent)" : "#1c2230", color: canSim ? "#fff" : "var(--tx-on-dark-3)",
          cursor: canSim ? "pointer" : "not-allowed", transition: "background .15s",
        }}
          onMouseEnter={(e) => { if (canSim) e.currentTarget.style.background = "var(--accent-hi)"; }}
          onMouseLeave={(e) => { if (canSim) e.currentTarget.style.background = "var(--accent)"; }}>
          {simState === "running" ? <><Spinner /> Simulating…</> : <><Icon name="play" size={16} fill="#fff" /> Simulate</>}
        </button>
      </div>
    </div>
  );
}

function Spinner({ size = 15, color = "#fff" }) {
  return <span style={{ width: size, height: size, border: `2px solid ${color}`, borderTopColor: "transparent", borderRadius: "50%", display: "inline-block", animation: "spin .7s linear infinite" }} />;
}

Object.assign(window, { SettingsPanel, EditorPane, ExamplePicker, NumInput, Spinner });
