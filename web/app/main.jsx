/* ===== Main app ===== */

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "#22a06b",
  "editorTheme": "Charcoal",
  "syntaxTheme": "VS Dark",
  "resultsStyle": "plain",
  "split": 50
}/*EDITMODE-END*/;

const EDITOR_THEMES = {
  "Charcoal":  { bg: "#0a0c12", gutter: "#0d1019", line: "#1b2030" },
  "Midnight":  { bg: "#0a1020", gutter: "#0c1426", line: "#1c2740" },
  "Slate":     { bg: "#14181f", gutter: "#181d26", line: "#262d3a" },
};
const SYNTAX_THEMES = {
  "VS Dark": { fn: "#4ec9b0", var: "#9cdcfe", num: "#b5cea8", str: "#ce9178", op: "#d4d4d4", com: "#6a9955", paren: "#ffd700" },
  "Brain":   { fn: "#e8836b", var: "#d4d4d4", num: "#b5cea8", str: "#ce9178", op: "#cfd3da", com: "#6a9955", paren: "#d4d4d4" },
  "Mono":    { fn: "#8fd0c0", var: "#cdd4e2", num: "#cdd4e2", str: "#a8b6c8", op: "#9aa3b8", com: "#5e6679", paren: "#cdd4e2" },
};
function shade(hex, amt) {
  const n = parseInt(hex.slice(1), 16);
  let r = (n >> 16) + amt, g = ((n >> 8) & 255) + amt, b = (n & 255) + amt;
  r = Math.max(0, Math.min(255, r)); g = Math.max(0, Math.min(255, g)); b = Math.max(0, Math.min(255, b));
  return "#" + ((r << 16) | (g << 8) | b).toString(16).padStart(6, "0");
}

function Toast({ msg, onClose }) {
  React.useEffect(() => { const t = setTimeout(onClose, 3200); return () => clearTimeout(t); }, []);
  return (
    <div style={{ position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)", zIndex: 200,
      background: "#11151f", color: "#fff", padding: "13px 22px", borderRadius: 10, fontSize: 13.5,
      boxShadow: "0 16px 40px rgba(0,0,0,0.4)", border: "1px solid #2a3145", maxWidth: 520,
      display: "flex", alignItems: "center", gap: 10, animation: "fadeUp .25s ease both" }}
      dangerouslySetInnerHTML={{ __html: msg }} />
  );
}

function LiveModal({ onConfirm, onCancel }) {
  const [ok, setOk] = React.useState(false);
  return (
    <div onClick={onCancel} style={{ position: "fixed", inset: 0, zIndex: 150, background: "rgba(6,8,15,0.55)", display: "grid", placeItems: "center" }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 480, background: "#fff", borderRadius: 14, overflow: "hidden", boxShadow: "0 30px 80px rgba(0,0,0,0.4)" }}>
        <div style={{ padding: "22px 26px", borderBottom: "1px solid var(--res-line)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 17, fontWeight: 700, color: "var(--down)" }}>
            <span style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--down)" }} /> Run LIVE — 실주문 제출
          </div>
        </div>
        <div style={{ padding: "20px 26px", fontSize: 13.5, color: "var(--tx-on-light-2)", lineHeight: 1.6 }}>
          이 알파를 <b style={{ color: "var(--tx-on-light)" }}>Alpaca 페이퍼 계좌</b>에 적용하고 <b style={{ color: "var(--down)" }}>실제 주문을 제출</b>합니다. 다음 봇 실행부터 반영됩니다.
          <label style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 16, padding: "12px 14px", background: "#fff7ed", border: "1px solid #f3d3a8", borderRadius: 8, cursor: "pointer" }}>
            <input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} style={{ width: 16, height: 16, accentColor: "var(--down)" }} />
            <span style={{ fontSize: 12.5, color: "#b9760f" }}>확인 — 페이퍼 계좌에 실주문을 제출하는 것에 동의합니다.</span>
          </label>
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, padding: "0 26px 22px" }}>
          <button onClick={onCancel} style={{ padding: "10px 20px", borderRadius: 8, border: "1px solid var(--res-line)", background: "#fff", fontSize: 13.5, fontWeight: 600, color: "var(--tx-on-light-2)" }}>취소</button>
          <button onClick={() => ok && onConfirm()} disabled={!ok} style={{ padding: "10px 24px", borderRadius: 8, background: ok ? "var(--down)" : "#e9ecf1", color: ok ? "#fff" : "var(--tx-on-light-3)", fontSize: 13.5, fontWeight: 700, cursor: ok ? "pointer" : "default" }}>Run LIVE</button>
        </div>
      </div>
    </div>
  );
}

function BacktestWorkspace({ state, tweaks }) {
  const { panel, setPanel } = state;
  const containerRef = React.useRef(null);
  const [dragging, setDragging] = React.useState(false);

  React.useEffect(() => {
    if (!dragging) return;
    const move = (e) => {
      const r = containerRef.current.getBoundingClientRect();
      let pct = ((e.clientX - r.left) / r.width) * 100;
      pct = Math.max(28, Math.min(72, pct));
      state.setTweak("split", Math.round(pct));
    };
    const up = () => setDragging(false);
    window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
    return () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
  }, [dragging]);

  const showCode = panel.code, showRes = panel.results;
  const split = tweaks.split;
  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
      <SimTabBar tabs={state.tabs} activeId={state.activeId} onSelect={state.selectTab} onClose={state.closeTab} onAdd={state.addTab} panel={panel} setPanel={setPanel} />
      {!state.hasActive ? (
        <div style={{ flex: 1, minHeight: 0, display: "grid", placeItems: "center", background: "var(--editor-bg)" }}>
          <button onClick={state.addTab} style={{
            display: "flex", flexDirection: "column", alignItems: "center", gap: 14, padding: "28px 40px",
            borderRadius: 12, border: "1px dashed var(--panel-border)", background: "transparent", color: "var(--tx-on-dark-2)",
          }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.03)"; e.currentTarget.style.borderColor = "var(--accent)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.borderColor = "var(--panel-border)"; }}>
            <span style={{ width: 52, height: 52, borderRadius: "50%", display: "grid", placeItems: "center", border: "1.5px solid var(--accent)", color: "var(--accent-hi)" }}>
              <Icon name="plus" size={26} />
            </span>
            <span style={{ fontSize: 15, fontWeight: 600, color: "var(--tx-on-dark)", whiteSpace: "nowrap" }}>New Simulation</span>
            <span style={{ fontSize: 12.5, whiteSpace: "nowrap" }}>새 시뮬레이션을 시작하세요</span>
          </button>
        </div>
      ) : (
      <div ref={containerRef} style={{ display: "flex", flex: 1, minHeight: 0, position: "relative" }}>
        {showCode && (
          <div style={{ width: showRes ? split + "%" : "100%", minWidth: 0, display: "flex", flexShrink: 0 }} className="on-dark">
            <EditorPane {...state} tweaks={tweaks} />
          </div>
        )}
        {showCode && showRes && (
          <div onMouseDown={() => setDragging(true)} style={{ width: 6, flexShrink: 0, cursor: "col-resize", background: dragging ? "var(--accent)" : "var(--simbar-line)", position: "relative", zIndex: 20 }}>
            <div style={{ position: "absolute", inset: "0 -3px", }} />
          </div>
        )}
        {showRes && (
          <div style={{ flex: 1, minWidth: 0 }}>
            <ResultsPane simState={state.simState} progress={state.progress} result={state.result} tweaks={tweaks}
              onDry={() => state.runBot("dry")}
              onLive={() => state.setLiveModal(true)} />
          </div>
        )}
      </div>
      )}
    </div>
  );
}

const newSettings = () => {
  const base = {
    language: "Fast Expression", instrument: "Equity", region: "USA", universe: "S&P 500",
    delay: 1, neutralization: "Sector", decay: 0, truncation: 0.08, pasteurization: "On",
    nanHandling: "Off", testYears: 1, testMonths: 0,
  };
  // 서버에서 받은 실제 알파 세팅 반영 (있으면)
  const live = (typeof window !== "undefined" && window.AB_LIVE_CONFIG) ? window.AB_LIVE_CONFIG.settings : null;
  return live ? { ...base, ...live } : base;
};
const liveExpr = () => (typeof window !== "undefined" && window.AB_LIVE_CONFIG && window.AB_LIVE_CONFIG.expression) || "rank(-returns)";
const newTab = (id, expr = "") => ({ id, name: "Simulation " + id, expr, settings: newSettings(), simState: "idle", progress: 0, result: null });

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [activeTab, setActiveTab] = React.useState("backtest");
  const [tabs, setTabs] = React.useState([newTab(1, liveExpr())]);  // 최초 탭만 저장된 알파
  const [activeId, setActiveId] = React.useState(1);
  const [showSettings, setShowSettings] = React.useState(false);
  const [panel, setPanel] = React.useState({ code: true, results: true });
  const [toastMsg, setToastMsg] = React.useState(null);
  const [liveModal, setLiveModal] = React.useState(false);
  const seqRef = React.useRef(1);
  const progRefs = React.useRef({});

  const toast = (m) => setToastMsg(m);
  const active = tabs.find((x) => x.id === activeId) || tabs[0];

  const updateTab = (id, patch) => setTabs((ts) => ts.map((x) => x.id === id ? { ...x, ...(typeof patch === "function" ? patch(x) : patch) } : x));
  const setExpr = (v) => updateTab(activeId, { expr: v });
  const setSettings = (fn) => updateTab(activeId, (x) => ({ settings: typeof fn === "function" ? fn(x.settings) : fn }));

  function addTab() {
    const id = tabs.length === 0 ? 1 : seqRef.current + 1;
    seqRef.current = id;
    setTabs((ts) => [...ts, newTab(id)]);
    setActiveId(id);
    setShowSettings(false);
  }
  function closeTab(id) {
    clearInterval(progRefs.current[id]);
    const idx = tabs.findIndex((x) => x.id === id);
    const next = tabs.filter((x) => x.id !== id);
    if (next.length === 0) {
      seqRef.current = 0;        // restart numbering from Simulation 1
      setActiveId(null);
    } else if (id === activeId) {
      setActiveId(next[Math.max(0, idx - 1)].id);
    }
    setTabs(next);
  }

  function onSimulate() {
    const id = activeId;
    const tab = tabs.find((x) => x.id === id);
    if (!tab) return;
    setShowSettings(false);
    setPanel((p) => ({ ...p, results: true }));
    updateTab(id, { simState: "running", progress: 4 });
    clearInterval(progRefs.current[id]);

    // 실제 백테스트 API 호출 (lib/backtest)
    const payload = {
      expression: tab.expr,
      settings: {
        neutralization: tab.settings.neutralization,
        decay: tab.settings.decay,
        truncation: tab.settings.truncation,
        delay: tab.settings.delay,
      },
    };
    let done = false;
    fetch("/api/backtest", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then((r) => r.json())
      .then((res) => {
        done = true;
        clearInterval(progRefs.current[id]);
        if (res.error) {
          updateTab(id, { simState: "idle", progress: 0 });
          toast('⚠️ <b>백테스트 실패</b> — ' + res.error);
          return;
        }
        // 결과는 탭별로 저장 (전역 공유 X → 탭마다 독립 result)
        updateTab(id, { simState: "done", progress: 100, result: res });
      })
      .catch((e) => {
        done = true;
        clearInterval(progRefs.current[id]);
        updateTab(id, { simState: "idle", progress: 0 });
        toast('⚠️ <b>API 연결 실패</b> — ' + e.message);
      });

    // 진행률 애니메이션 (응답 전까지 90% 까지만 차오름)
    progRefs.current[id] = setInterval(() => {
      setTabs((ts) => ts.map((x) => {
        if (x.id !== id || x.simState !== "running") return x;
        const cap = done ? 100 : 90;
        const next = Math.min(cap, x.progress + Math.random() * 9 + 3);
        return { ...x, progress: next };
      }));
    }, 230);
  }
  React.useEffect(() => () => Object.values(progRefs.current).forEach(clearInterval), []);

  // ---- config 저장 + 봇 실행 (Dry / LIVE) ----
  async function saveConfig() {
    if (!active) return;
    try {
      await fetch("/api/config", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expression: active.expr,
          settings: {
            neutralization: active.settings.neutralization, decay: active.settings.decay,
            truncation: active.settings.truncation, delay: active.settings.delay,
          },
        }),
      });
    } catch (e) { /* ignore */ }
  }
  async function runBot(mode) {
    await saveConfig();
    toast(mode === "live" ? '🔴 <b>LIVE 실행 중…</b> Alpaca 에 주문 제출 중' : '🟡 <b>Dry Run 실행 중…</b>');
    try {
      const r = await fetch("/api/run", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      const res = await r.json();
      toast(res.ok
        ? (mode === "live" ? '🔴 <b>LIVE 완료</b> — 주문 제출됨 (Bot Logs 탭 확인)' : '🟡 <b>Dry Run 완료</b> — 주문 미제출 (Bot Logs 탭 확인)')
        : '⚠️ <b>실행 실패</b>');
    } catch (e) { toast('⚠️ <b>실행 실패</b> — ' + e.message); }
  }

  // theme vars
  const et = EDITOR_THEMES[t.editorTheme] || EDITOR_THEMES.Charcoal;
  const syn = SYNTAX_THEMES[t.syntaxTheme] || SYNTAX_THEMES["VS Dark"];
  const themeVars = {
    "--accent": t.accent, "--accent-hi": shade(t.accent, 18), "--accent-lo": shade(t.accent, -22),
    "--editor-bg": et.bg, "--editor-gutter": et.gutter, "--editor-line": et.line,
    "--syn-fn": syn.fn, "--syn-var": syn.var, "--syn-num": syn.num, "--syn-str": syn.str,
    "--syn-op": syn.op, "--syn-com": syn.com, "--syn-paren": syn.paren,
  };

  const wsState = {
    expr: active ? active.expr : "", setExpr, settings: active ? active.settings : newSettings(), setSettings, showSettings, setShowSettings,
    simState: active ? active.simState : "idle", progress: active ? active.progress : 0, result: active ? active.result : null, onSimulate, panel, setPanel, setTweak, toast, setLiveModal,
    tabs, activeId, hasActive: !!active, selectTab: (id) => { setActiveId(id); setShowSettings(false); }, closeTab, addTab,
    runBot, saveConfig,
  };

  return (
    <div className="app" style={themeVars}>
      <TopNav active={activeTab} onChange={setActiveTab} />
      {activeTab === "backtest" && <BacktestWorkspace state={wsState} tweaks={t} />}
      {activeTab === "performance" && <PerformanceTab />}
      {activeTab === "orders" && <OrdersTab />}
      {activeTab === "positions" && <PositionsTab />}
      {activeTab === "botlogs" && <BotLogsTab />}
      {activeTab === "news" && <NewsTab />}

      {toastMsg && <Toast msg={toastMsg} onClose={() => setToastMsg(null)} />}
      {liveModal && <LiveModal onCancel={() => setLiveModal(false)} onConfirm={() => { setLiveModal(false); runBot("live"); }} />}

      <TweaksPanel>
        <TweakSection label="Brand / Accent" />
        <TweakColor label="Accent color" value={t.accent}
          options={["#22a06b", "#2f7ce0", "#7c5cff", "#e0792f", "#d94a6a"]}
          onChange={(v) => setTweak("accent", v)} />
        <TweakSection label="Code editor" />
        <TweakRadio label="Editor theme" value={t.editorTheme} options={["Charcoal", "Midnight", "Slate"]} onChange={(v) => setTweak("editorTheme", v)} />
        <TweakSelect label="Syntax palette" value={t.syntaxTheme} options={["VS Dark", "Brain", "Mono"]} onChange={(v) => setTweak("syntaxTheme", v)} />
        <TweakSection label="Results" />
        <TweakRadio label="Metric layout" value={t.resultsStyle} options={["plain", "cards"]} onChange={(v) => setTweak("resultsStyle", v)} />
        <TweakSlider label="Editor / results split" value={t.split} min={28} max={72} step={1} unit="%" onChange={(v) => setTweak("split", v)} />
      </TweaksPanel>
    </div>
  );
}

// 라이브 데이터(/api/data)를 먼저 받아 placeholder AB_DATA 를 덮어쓴 뒤 렌더.
// API 없이 파일 직접 열어도 placeholder 로 동작하도록 실패는 무시.
async function boot() {
  try {
    const r = await fetch("/api/data");
    if (r.ok) {
      const live = await r.json();
      Object.keys(live).forEach((k) => {
        if (live[k] !== null && live[k] !== undefined) window.AB_DATA[k] = live[k];
      });
      // config 의 expr/settings 를 기본 탭에 반영하고 싶으면 window.AB_LIVE_CONFIG 로 노출
      window.AB_LIVE_CONFIG = live.config || null;
    }
  } catch (e) { /* placeholder 사용 */ }
  ReactDOM.createRoot(document.getElementById("root")).render(<App />);
}
boot();
