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

// ---- 함수 · 데이터 레퍼런스 모달 ----
function ReferenceModal({ onClose, onInsert }) {
  const [q, setQ] = React.useState("");
  const ref = (window.AB_DATA && window.AB_DATA.reference) || { fields: [], operators: [] };
  const lq = q.trim().toLowerCase();
  const hit = (...parts) => !lq || parts.some((p) => (p || "").toLowerCase().includes(lq));

  const Row = ({ token, sig, desc, isFn, color }) => {
    const insertable = /^[a-z_]+$/.test(token);
    return (
      <button
        onClick={insertable ? () => onInsert(token, isFn) : undefined}
        title={insertable ? "클릭하면 수식에 추가" : "참고용 문법"}
        style={{
          display: "block", width: "100%", textAlign: "left", padding: "8px 10px",
          borderRadius: 6, cursor: insertable ? "pointer" : "default",
          borderBottom: "1px solid rgba(255,255,255,0.04)",
        }}
        onMouseEnter={(e) => { if (insertable) e.currentTarget.style.background = "rgba(255,255,255,0.06)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, color, marginBottom: 2 }}>{sig}</div>
        <div style={{ fontSize: 11.5, color: "var(--tx-on-dark-2)" }}>{desc}</div>
      </button>
    );
  };

  const Col = ({ title, count, accent, children }) => (
    <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", minHeight: 0 }}>
      <div style={{ fontSize: 11, letterSpacing: 1, fontWeight: 700, color: accent, padding: "0 4px 10px" }}>
        {title} <span style={{ color: "var(--tx-on-dark-3)", fontWeight: 500 }}>· {count}</span>
      </div>
      <div className="editor-scroll" style={{ overflowY: "auto", paddingRight: 6, flex: 1 }}>{children}</div>
    </div>
  );

  const GroupLabel = ({ children }) => (
    <div style={{ fontSize: 10.5, fontWeight: 600, color: "var(--tx-on-dark-3)", margin: "12px 4px 4px" }}>{children}</div>
  );

  const fieldGroups = ref.fields
    .map((g) => ({ group: g.group, items: g.items.filter(([n, d]) => hit(n, d)) }))
    .filter((g) => g.items.length);
  const fieldCount = fieldGroups.reduce((s, g) => s + g.items.length, 0);
  const opGroups = ref.operators
    .map((g) => ({ group: g.group, items: g.items.filter(([n, sig, d]) => hit(n, sig, d)) }))
    .filter((g) => g.items.length);
  const opCount = opGroups.reduce((s, g) => s + g.items.length, 0);

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, zIndex: 200, background: "rgba(6,9,15,0.72)",
      display: "flex", alignItems: "center", justifyContent: "center", padding: 24,
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        width: "min(940px, 96vw)", height: "min(80vh, 760px)", display: "flex", flexDirection: "column",
        background: "var(--panel-bg, #11151f)", border: "1px solid var(--panel-border, #2a3145)",
        borderRadius: 12, boxShadow: "0 30px 80px rgba(0,0,0,0.6)", overflow: "hidden",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "16px 18px", borderBottom: "1px solid var(--panel-border, #2a3145)" }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--tx-on-dark)", whiteSpace: "nowrap" }}>📖 함수 · 데이터</div>
          <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="검색 (예: ts_, rank, 매출, returns)…"
            style={{
              flex: 1, height: 36, padding: "0 12px", background: "var(--panel-input, #0f1320)",
              border: "1px solid var(--panel-border, #2a3145)", borderRadius: 8, color: "var(--tx-on-dark)",
              fontSize: 13, outline: "none",
            }} />
          <button onClick={onClose} style={{ width: 32, height: 32, display: "grid", placeItems: "center", borderRadius: 8, color: "var(--tx-on-dark-2)", flexShrink: 0 }}
            onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.08)"}
            onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
            <Icon name="close" size={15} />
          </button>
        </div>
        <div style={{ display: "flex", gap: 18, padding: "16px 18px", flex: 1, minHeight: 0 }}>
          <Col title="데이터 필드" count={fieldCount} accent="var(--syn-var, #4ec9b0)">
            {fieldGroups.length === 0 && <div style={{ color: "var(--tx-on-dark-3)", fontSize: 12, padding: 8 }}>일치 항목 없음</div>}
            {fieldGroups.map((g) => (
              <div key={g.group}>
                <GroupLabel>{g.group}</GroupLabel>
                {g.items.map(([n, d]) => <Row key={n} token={n} sig={n} desc={d} isFn={false} color="var(--syn-var, #4ec9b0)" />)}
              </div>
            ))}
          </Col>
          <div style={{ width: 1, background: "var(--panel-border, #2a3145)", flexShrink: 0 }} />
          <Col title="연산자" count={opCount} accent="var(--syn-fn, #dcdcaa)">
            {opGroups.length === 0 && <div style={{ color: "var(--tx-on-dark-3)", fontSize: 12, padding: 8 }}>일치 항목 없음</div>}
            {opGroups.map((g) => (
              <div key={g.group}>
                <GroupLabel>{g.group}</GroupLabel>
                {g.items.map(([n, sig, d]) => <Row key={n} token={n} sig={sig} desc={d} isFn={true} color="var(--syn-fn, #dcdcaa)" />)}
              </div>
            ))}
          </Col>
        </div>
        <div style={{ padding: "10px 18px", borderTop: "1px solid var(--panel-border, #2a3145)", fontSize: 11.5, color: "var(--tx-on-dark-3)" }}>
          항목을 클릭하면 수식에 추가됩니다 · 고정: USA · S&amp;P 500 · 일봉(D1)
        </div>
      </div>
    </div>
  );
}

// ---- left editor pane ----
function EditorPane({ expr, setExpr, settings, setSettings, showSettings, setShowSettings, simState, onSimulate, tweaks }) {
  const s = settings;
  const breadcrumb = `${s.region}/D${s.delay}/${s.universe.replace(/\s/g, "")}`;
  const canSim = simState !== "running" && expr.trim().length > 0;
  const [showRef, setShowRef] = React.useState(false);
  const insertToken = (name, isFn) => {
    // setExpr 는 값만 받음(함수형 미지원) → 현재 expr 로 직접 계산
    const ins = isFn ? name + "()" : name;
    const sep = !expr || /[\s(,+\-*/]$/.test(expr) ? "" : " ";
    setExpr((expr || "") + sep + ins);
    setShowRef(false);
  };
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

      {showRef && <ReferenceModal onClose={() => setShowRef(false)} onInsert={insertToken} />}

      {/* action bar */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: 16, background: "var(--editor-bg)", borderTop: "1px solid var(--editor-line)", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <ExamplePicker onPick={setExpr} />
          <button onClick={() => setShowRef(true)} title="사용 가능한 함수 · 데이터 목록" style={{
            display: "flex", alignItems: "center", gap: 8, height: 42, padding: "0 18px",
            background: "transparent", color: "var(--tx-on-dark-2)", borderRadius: "var(--r-sm)",
            fontSize: 13.5, fontWeight: 600, border: "1px solid #2a3145",
          }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.05)"; e.currentTarget.style.color = "var(--tx-on-dark)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--tx-on-dark-2)"; }}>
            📖 함수·데이터
          </button>
        </div>
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

Object.assign(window, { SettingsPanel, EditorPane, ExamplePicker, ReferenceModal, NumInput, Spinner });
