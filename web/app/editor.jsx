/* ===== Backtest workspace: sim tab bar + code editor + settings panel ===== */

// ---- syntax highlight ----
const FUNCS = new Set(["rank","winsorize","zscore","normalize","scale","quantile","ts_mean","ts_sum","ts_std_dev","ts_zscore","ts_rank","ts_delta","ts_delay","ts_backfill","ts_min","ts_max","ts_decay_linear","ts_corr","group_neutralize","group_rank","group_zscore","group_mean","bucket","trade_when","log","sqrt","abs","sign","signed_power","power","max","min","add","subtract","multiply","divide"]);
const VARS = new Set(["returns","close","open","high","low","volume","cap","revenue","ni","fcf","ocf","roe","roa","pe","pb","ps","sector","industry","ppent","cash","debt","assets","equity","eps","beta","ev","shares"]);

function highlight(code) {
  const out = [];
  const re = /(\/\/[^\n]*)|("[^"]*"|'[^']*')|(\b\d+\.?\d*\b)|([A-Za-z_]\w*)|([()])|([+\-*/=,])|(\s+)|([^\s])/g;
  let m, key = 0;
  while ((m = re.exec(code)) !== null) {
    const [tok] = m;
    let color = "var(--syn-op)";
    if (m[1]) color = "var(--syn-com)";
    else if (m[2]) color = "var(--syn-str)";
    else if (m[3]) color = "var(--syn-num)";
    else if (m[4]) {
      const after = code.slice(m.index + tok.length).match(/^\s*\(/);
      if (after || FUNCS.has(tok)) color = "var(--syn-fn)";
      else if (VARS.has(tok)) color = "var(--syn-var)";
      else color = "#dcdcaa";
    } else if (m[5]) color = "var(--syn-paren)";
    else if (m[6]) color = "var(--syn-op)";
    if (m[7] || m[8] === undefined && !tok) { out.push(tok); continue; }
    out.push(<span key={key++} style={{ color }}>{tok}</span>);
  }
  return out;
}

// ---- dark custom select ----
function DarkSelect({ value, options, onChange, width }) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  return (
    <div ref={ref} style={{ position: "relative", width: width || "100%" }}>
      <button onClick={() => setOpen((o) => !o)} style={{
        width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
        gap: 8, height: 38, padding: "0 12px", background: "var(--panel-input)",
        border: "1px solid var(--panel-border)", borderRadius: "var(--r-sm)",
        color: "var(--tx-on-dark)", fontSize: 13, textAlign: "left",
        outline: open ? "1px solid var(--accent)" : "none",
      }}>
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{value}</span>
        <Icon name="chevD" size={15} style={{ color: "var(--tx-on-dark-3)", flexShrink: 0 }} />
      </button>
      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 40,
          background: "#0f1320", border: "1px solid var(--panel-border)", borderRadius: "var(--r-sm)",
          boxShadow: "0 12px 30px rgba(0,0,0,0.55)", overflow: "hidden", maxHeight: 260, overflowY: "auto",
        }}>
          {options.map((o) => {
            const sel = o === value;
            return (
              <button key={o} onClick={() => { onChange(o); setOpen(false); }} style={{
                width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "9px 12px", fontSize: 13, textAlign: "left",
                color: sel ? "#fff" : "var(--tx-on-dark-2)",
                background: sel ? "var(--accent)" : "transparent",
              }}
                onMouseEnter={(e) => { if (!sel) e.currentTarget.style.background = "rgba(255,255,255,0.05)"; }}
                onMouseLeave={(e) => { if (!sel) e.currentTarget.style.background = "transparent"; }}>
                {o}{sel && <Icon name="check" size={14} />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
      <label style={{ fontSize: 10.5, letterSpacing: 1, fontWeight: 600, color: "var(--tx-on-dark-2)", display: "flex", alignItems: "center", gap: 5 }}>
        {label.toUpperCase()}
        <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--cool)", opacity: 0.7 }} />
      </label>
      {children}
    </div>
  );
}

// ---- sim tab bar ----
function SimTabBar({ tabs, activeId, onSelect, onClose, onAdd, panel, setPanel }) {
  return (
    <div style={{ display: "flex", alignItems: "stretch", background: "var(--simbar-bg)", height: 44, flexShrink: 0, borderBottom: "1px solid var(--simbar-line)" }}>
      <div style={{ display: "flex", alignItems: "stretch", minWidth: 0, overflowX: "auto" }}>
        {tabs.map((t) => {
          const on = t.id === activeId;
          return (
            <div key={t.id} onClick={() => onSelect(t.id)} title={t.name} style={{
              display: "flex", alignItems: "center", gap: 9, padding: "0 12px 0 14px", cursor: "pointer",
              borderRight: "1px solid var(--simbar-line)", flexShrink: 0,
              background: on ? "var(--editor-bg)" : "transparent",
              boxShadow: on ? "inset 0 -2px 0 var(--accent)" : "none",
            }}
              onMouseEnter={(e) => { if (!on) e.currentTarget.style.background = "rgba(255,255,255,0.03)"; }}
              onMouseLeave={(e) => { if (!on) e.currentTarget.style.background = "transparent"; }}>
              <AlphaMark size={18} color={on ? "var(--accent-hi)" : "var(--tx-on-dark-3)"} />
              <span style={{ color: on ? "var(--tx-on-dark)" : "var(--tx-on-dark-2)", fontSize: 13, fontWeight: on ? 600 : 500, whiteSpace: "nowrap" }}>{t.name}</span>
              <span style={{ width: 6, height: 6, borderRadius: "50%", flexShrink: 0, background: t.simState === "done" ? "var(--accent)" : t.simState === "running" ? "var(--cool)" : "var(--tx-on-dark-3)" }} />
              <button onClick={(e) => { e.stopPropagation(); onClose(t.id); }} title="Close simulation" style={{ color: "var(--tx-on-dark-3)", width: 22, height: 22, display: "grid", placeItems: "center", borderRadius: 4, flexShrink: 0 }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.08)"; e.currentTarget.style.color = "var(--tx-on-dark)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--tx-on-dark-3)"; }}>
                <Icon name="close" size={13} />
              </button>
            </div>
          );
        })}
        <button onClick={onAdd} title="New simulation" style={{ width: 40, color: "var(--accent-hi)", display: "grid", placeItems: "center", borderRight: "1px solid var(--simbar-line)", flexShrink: 0 }}
          onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.04)"}
          onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}><Icon name="plus" size={16} /></button>
      </div>
      <div style={{ flex: 1 }} />
      <button style={{ width: 40, color: "var(--tx-on-dark-3)", display: "grid", placeItems: "center" }}><Icon name="chevD" size={16} /></button>
      {/* panel toggles */}
      <div style={{ display: "flex", alignItems: "center", gap: 2, background: "var(--res-rail)", paddingLeft: 6 }}>
        {[["code","CODE"],["results","RESULTS"]].map(([id, lb]) => {
          const on = panel[id];
          return (
            <button key={id} onClick={() => setPanel((p) => ({ ...p, [id]: !p[id] }))} style={{
              display: "flex", alignItems: "center", gap: 7, padding: "0 14px", height: 44,
              fontSize: 12, letterSpacing: 1, fontWeight: 600,
              color: on ? "var(--accent-lo)" : "#aab2c0", cursor: "pointer",
            }}>
              <span style={{
                width: 16, height: 16, borderRadius: 4, display: "grid", placeItems: "center",
                background: on ? "var(--accent)" : "transparent",
                border: on ? "none" : "1.5px solid #c2c9d4",
              }}>{on && <Icon name="check" size={12} style={{ color: "#fff" }} />}</span>
              {lb}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ---- code editor ----
function CodeEditor({ expr, setExpr, tweaks }) {
  const taRef = React.useRef(null);
  const [ac, setAc] = React.useState(null); // {items, top, left, idx, token}
  const lines = expr.split("\n");
  const lineH = 22, padT = 12, padL = 16, gutterW = 44, charW = 8.4;

  function updateAc(el) {
    const caret = el.selectionStart;
    const before = expr.slice(0, caret);
    const tokenMatch = before.match(/[A-Za-z_]\w*$/);
    if (!tokenMatch) { setAc(null); return; }
    const token = tokenMatch[0];
    const pool = window.AB_DATA.variables;
    const items = pool.filter((v) => v.name.toLowerCase().includes(token.toLowerCase())).slice(0, 9);
    if (!items.length) { setAc(null); return; }
    const lineIdx = before.split("\n").length - 1;
    const col = before.length - before.lastIndexOf("\n") - 1;
    setAc({ items, idx: 0, token,
      top: padT + (lineIdx + 1) * lineH + 2,
      left: gutterW + padL + (col - token.length) * charW });
  }

  function accept(item) {
    const el = taRef.current;
    const caret = el.selectionStart;
    const before = expr.slice(0, caret).replace(/[A-Za-z_]\w*$/, "");
    const after = expr.slice(caret);
    const next = before + item.name + after;
    setExpr(next);
    setAc(null);
    requestAnimationFrame(() => { el.focus(); const p = (before + item.name).length; el.setSelectionRange(p, p); });
  }

  function onKey(e) {
    if (!ac) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setAc((a) => ({ ...a, idx: (a.idx + 1) % a.items.length })); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setAc((a) => ({ ...a, idx: (a.idx - 1 + a.items.length) % a.items.length })); }
    else if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); accept(ac.items[ac.idx]); }
    else if (e.key === "Escape") setAc(null);
  }

  const sel = ac ? ac.items[ac.idx] : null;
  return (
    <div className="editor-scroll" style={{ position: "relative", flex: 1, background: "var(--editor-bg)", overflow: "auto", fontFamily: "var(--font-mono)", fontSize: 14 }}>
      <div style={{ position: "relative", minHeight: "100%", display: "flex" }}>
        {/* gutter */}
        <div style={{ width: gutterW, flexShrink: 0, background: "var(--editor-gutter)", paddingTop: padT, textAlign: "right", userSelect: "none", borderRight: "1px solid var(--editor-line)" }}>
          {lines.map((_, i) => (
            <div key={i} style={{ height: lineH, lineHeight: lineH + "px", paddingRight: 10, color: "var(--tx-on-dark-3)", fontSize: 12.5 }}>{i + 1}</div>
          ))}
        </div>
        {/* code area */}
        <div style={{ position: "relative", flex: 1, paddingTop: padT, paddingLeft: padL }}>
          <pre aria-hidden="true" style={{
            margin: 0, fontFamily: "var(--font-mono)", fontSize: 14, lineHeight: lineH + "px",
            whiteSpace: "pre", color: "var(--syn-op)", pointerEvents: "none",
          }}>{highlight(expr)}{"\n"}</pre>
          <textarea ref={taRef} value={expr} spellCheck={false}
            onChange={(e) => { setExpr(e.target.value); updateAc(e.target); }}
            onClick={(e) => updateAc(e.target)}
            onKeyDown={onKey}
            onBlur={() => setTimeout(() => setAc(null), 120)}
            style={{
              position: "absolute", top: padT, left: padL, right: 0, bottom: 0, width: "calc(100% - " + padL + "px)",
              margin: 0, padding: 0, border: "none", outline: "none", resize: "none", overflow: "hidden",
              background: "transparent", color: "transparent", caretColor: "var(--accent-hi)",
              fontFamily: "var(--font-mono)", fontSize: 14, lineHeight: lineH + "px", whiteSpace: "pre",
            }} />
          {/* autocomplete */}
          {ac && (
            <div style={{ position: "absolute", top: ac.top, left: ac.left, zIndex: 30, display: "flex", boxShadow: "0 14px 36px rgba(0,0,0,0.6)" }}>
              <div style={{ background: "#11151f", border: "1px solid #2a3145", borderRadius: 4, overflow: "hidden", minWidth: 240 }}>
                {ac.items.map((it, i) => (
                  <button key={it.name} onMouseDown={(e) => { e.preventDefault(); accept(it); }}
                    onMouseEnter={() => setAc((a) => ({ ...a, idx: i }))}
                    style={{ display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "6px 12px",
                      background: i === ac.idx ? "var(--accent)" : "transparent", color: i === ac.idx ? "#fff" : "var(--syn-var)",
                      fontFamily: "var(--font-mono)", fontSize: 13, textAlign: "left" }}>
                    <span style={{ opacity: 0.6 }}>◈</span>{it.name}
                  </button>
                ))}
              </div>
              {sel && (
                <div style={{ background: "#0b0e16", border: "1px solid #2a3145", borderLeft: "none", padding: "12px 14px", minWidth: 200, maxWidth: 230 }}>
                  <div style={{ color: "#fff", fontFamily: "var(--font-mono)", fontSize: 13, marginBottom: 8 }}>{sel.name}</div>
                  <div style={{ color: "var(--tx-on-dark-2)", fontSize: 12, marginBottom: 6 }}><b style={{ color: "var(--tx-on-dark)" }}>Type</b>: {sel.type}</div>
                  <div style={{ color: "var(--tx-on-dark-2)", fontSize: 12 }}>{sel.desc}</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { highlight, DarkSelect, Field, SimTabBar, CodeEditor });
