/* ===== Alphas: 유저가 만든 알파 공유 탭 ===== */

const ALPHA_NEUT_OPTIONS = ["None", "Market", "Sector", "Cap Bucket", "Sector + Cap Bucket", "Subindustry"];

function ShareAlphaModal({ onClose, onDone }) {
  const [author, setAuthor] = React.useState("");
  const [name, setName] = React.useState("");
  const [expression, setExpression] = React.useState("");
  const [neutralization, setNeut] = React.useState("Sector + Cap Bucket");
  const [delay, setDelay] = React.useState(1);
  const [decay, setDecay] = React.useState(0);
  const [truncation, setTruncation] = React.useState(0.08);
  const [description, setDescription] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  const canSubmit = expression.trim().length > 0 && !busy;
  const inputStyle = {
    width: "100%", padding: "9px 11px", border: "1px solid var(--res-line)", borderRadius: 8,
    fontSize: 13, color: "var(--tx-on-light)", outline: "none", background: "#fff",
  };
  const labelStyle = { fontSize: 11.5, fontWeight: 700, color: "var(--tx-on-light-2)", marginBottom: 5, display: "block" };

  async function submit() {
    if (!canSubmit) return;
    setBusy(true);
    try {
      const r = await fetch("/api/alphas", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          author, name, expression,
          settings: { neutralization, delay: +delay, decay: +decay, truncation: +truncation },
          description,
        }),
      });
      const res = await r.json();
      if (res.error) { onDone('⚠️ <b>공유 실패</b> — ' + res.error, false); setBusy(false); return; }
      onDone('✅ <b>알파가 공유되었습니다!</b>', true);
    } catch (e) {
      onDone('⚠️ <b>공유 실패</b> — ' + e.message, false); setBusy(false);
    }
  }

  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, zIndex: 200, background: "rgba(6,9,15,0.5)", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: "min(620px, 96vw)", maxHeight: "90vh", overflowY: "auto", background: "#fff", borderRadius: 14, boxShadow: "0 30px 80px rgba(0,0,0,0.4)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "18px 22px", borderBottom: "1px solid var(--res-line)" }}>
          <AlphaMark size={22} />
          <span style={{ fontSize: 16, fontWeight: 700, color: "var(--tx-on-light)" }}>알파 공유</span>
          <div style={{ flex: 1 }} />
          <button onClick={onClose} style={{ width: 32, height: 32, display: "grid", placeItems: "center", borderRadius: 8, color: "var(--tx-on-light-2)" }}><Icon name="close" size={16} /></button>
        </div>
        <div style={{ padding: "20px 22px", display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <div><label style={labelStyle}>작성자</label><input style={inputStyle} value={author} onChange={(e) => setAuthor(e.target.value)} placeholder="이름 (선택)" /></div>
            <div><label style={labelStyle}>알파 이름</label><input style={inputStyle} value={name} onChange={(e) => setName(e.target.value)} placeholder="예: 자산가치 (PP&E+현금)" /></div>
          </div>
          <div>
            <label style={labelStyle}>수식 *</label>
            <textarea style={{ ...inputStyle, minHeight: 92, fontFamily: "var(--font-mono)", lineHeight: 1.5, resize: "vertical" }}
              value={expression} onChange={(e) => setExpression(e.target.value)} spellCheck={false}
              placeholder="group_neutralize(winsorize((ppent + cash) / cap, std=4), bucket(rank(cap), range='0,1,0.1'))" />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr 1fr 1fr", gap: 12 }}>
            <div><label style={labelStyle}>Neutralization</label>
              <select style={inputStyle} value={neutralization} onChange={(e) => setNeut(e.target.value)}>
                {ALPHA_NEUT_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
              </select></div>
            <div><label style={labelStyle}>Delay</label>
              <select style={inputStyle} value={delay} onChange={(e) => setDelay(e.target.value)}><option value={0}>0</option><option value={1}>1</option></select></div>
            <div><label style={labelStyle}>Decay</label><input style={inputStyle} type="number" value={decay} onChange={(e) => setDecay(e.target.value)} /></div>
            <div><label style={labelStyle}>Truncation</label><input style={inputStyle} type="number" step="0.01" value={truncation} onChange={(e) => setTruncation(e.target.value)} /></div>
          </div>
          <div>
            <label style={labelStyle}>설명 (선택)</label>
            <textarea style={{ ...inputStyle, minHeight: 60, resize: "vertical" }} value={description} onChange={(e) => setDescription(e.target.value)}
              placeholder="어떤 아이디어인지, 왜 잘 되는지 간단히 적어주세요." />
          </div>
          <div style={{ fontSize: 11.5, color: "var(--tx-on-light-3)" }}>고정 데이터: USA · S&amp;P 500 · 일봉(D1). 누구나 백테스트에 불러와 검증할 수 있습니다.</div>
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, padding: "0 22px 20px" }}>
          <button onClick={onClose} style={{ padding: "10px 18px", borderRadius: 8, border: "1px solid var(--res-line)", background: "#fff", fontSize: 13.5, fontWeight: 600, color: "var(--tx-on-light-2)" }}>취소</button>
          <button onClick={submit} disabled={!canSubmit} style={{ padding: "10px 24px", borderRadius: 8, background: canSubmit ? "var(--accent)" : "#e9ecf1", color: canSubmit ? "#fff" : "var(--tx-on-light-3)", fontSize: 13.5, fontWeight: 700, cursor: canSubmit ? "pointer" : "default" }}>{busy ? "공유 중…" : "공유하기"}</button>
        </div>
      </div>
    </div>
  );
}

function AlphaCard({ a, onUse, onDelete }) {
  const s = a.settings || {};
  const chips = [["Neut", s.neutralization], ["Delay", s.delay], ["Decay", s.decay], ["Trunc", s.truncation]]
    .filter(([, v]) => v !== undefined && v !== null && v !== "");
  return (
    <Card style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 10 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--tx-on-light)" }}>{a.name}</div>
          <div style={{ fontSize: 12, color: "var(--tx-on-light-3)", marginTop: 2 }}>{a.author} · {a.ts}</div>
        </div>
        <button onClick={() => onUse(a.expression, a.settings)} style={{
          display: "flex", alignItems: "center", gap: 7, padding: "8px 14px", borderRadius: 8, flexShrink: 0,
          background: "var(--accent)", color: "#fff", fontSize: 12.5, fontWeight: 700, whiteSpace: "nowrap",
        }}
          onMouseEnter={(e) => e.currentTarget.style.background = "var(--accent-hi)"}
          onMouseLeave={(e) => e.currentTarget.style.background = "var(--accent)"}>
          <Icon name="flask" size={14} /> 백테스트에서 열기
        </button>
        <button onClick={() => onDelete(a)} title="삭제" style={{
          width: 36, height: 36, display: "grid", placeItems: "center", borderRadius: 8, flexShrink: 0,
          border: "1px solid var(--res-line)", background: "#fff", color: "var(--tx-on-light-3)",
        }}
          onMouseEnter={(e) => { e.currentTarget.style.color = "var(--down)"; e.currentTarget.style.borderColor = "var(--down)"; e.currentTarget.style.background = "#fdeceb"; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = "var(--tx-on-light-3)"; e.currentTarget.style.borderColor = "var(--res-line)"; e.currentTarget.style.background = "#fff"; }}>
          <Icon name="trash" size={15} />
        </button>
      </div>
      <pre style={{ margin: 0, fontFamily: "var(--font-mono)", fontSize: 12.5, color: "var(--tx-on-light)", background: "var(--res-alt)", border: "1px solid var(--res-line)", borderRadius: 8, padding: "11px 13px", whiteSpace: "pre-wrap", lineHeight: 1.5, overflowX: "auto" }}>{a.expression}</pre>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginTop: 10 }}>
        {chips.map(([k, v]) => (
          <span key={k} style={{ fontSize: 11, color: "var(--tx-on-light-2)", background: "var(--res-alt)", border: "1px solid var(--res-line)", borderRadius: 6, padding: "3px 9px" }}>{k} <b style={{ color: "var(--tx-on-light)" }}>{String(v)}</b></span>
        ))}
      </div>
      {a.description && <div style={{ fontSize: 12.5, color: "var(--tx-on-light-2)", marginTop: 10, lineHeight: 1.55 }}>{a.description}</div>}
    </Card>
  );
}

function AlphasTab({ onUse, toast }) {
  const [items, setItems] = React.useState(null);
  const [showShare, setShowShare] = React.useState(false);

  const load = React.useCallback(() => {
    fetch("/api/alphas").then((r) => r.json()).then((d) => setItems(d.items || []))
      .catch(() => setItems([]));
  }, []);
  React.useEffect(() => { load(); }, [load]);

  const del = (a) => {
    if (!window.confirm(`'${a.name}' 알파를 삭제할까요?`)) return;
    fetch(`/api/alphas/${a.id}`, { method: "DELETE" }).then((r) => r.json())
      .then((res) => {
        if (res.ok) { if (toast) toast('🗑 <b>알파가 삭제되었습니다</b>'); load(); }
        else if (toast) toast('⚠️ <b>삭제 실패</b> — ' + (res.error || ""));
      })
      .catch(() => { if (toast) toast('⚠️ <b>삭제 실패</b>'); });
  };

  return (
    <Page title="Alphas" sub="팀원·유저가 만든 알파를 공유하고, 클릭 한 번으로 백테스트에서 검증해보세요."
      right={
        <button onClick={() => setShowShare(true)} style={{ display: "flex", alignItems: "center", gap: 8, height: 40, padding: "0 18px", borderRadius: "var(--r-sm)", background: "var(--accent)", color: "#fff", fontSize: 13.5, fontWeight: 700, whiteSpace: "nowrap" }}>
          <Icon name="plus" size={16} /> 알파 공유
        </button>
      }>
      {items === null ? (
        <Card><div style={{ padding: 30, textAlign: "center", color: "var(--tx-on-light-3)", fontSize: 13 }}>불러오는 중…</div></Card>
      ) : items.length === 0 ? (
        <Card><div style={{ padding: "44px 20px", textAlign: "center" }}>
          <AlphaMark size={40} color="var(--res-line)" />
          <div style={{ fontSize: 15, fontWeight: 600, color: "var(--tx-on-light-2)", marginTop: 14 }}>아직 공유된 알파가 없습니다</div>
          <div style={{ fontSize: 13, color: "var(--tx-on-light-3)", marginTop: 6 }}>첫 알파를 공유해보세요. 다른 팀원이 바로 백테스트로 검증할 수 있어요.</div>
          <button onClick={() => setShowShare(true)} style={{ marginTop: 18, padding: "10px 22px", borderRadius: 8, background: "var(--accent)", color: "#fff", fontSize: 13.5, fontWeight: 700 }}>알파 공유하기</button>
        </div></Card>
      ) : (
        <div>
          <div style={{ fontSize: 12.5, color: "var(--tx-on-light-3)", marginBottom: 12 }}>공유된 알파 {items.length}개</div>
          {items.map((a) => <AlphaCard key={a.id} a={a} onUse={onUse} onDelete={del} />)}
        </div>
      )}

      {showShare && <ShareAlphaModal onClose={() => setShowShare(false)} onDone={(msg, ok) => {
        if (toast) toast(msg);
        if (ok) { setShowShare(false); load(); }
      }} />}
    </Page>
  );
}

Object.assign(window, { AlphasTab, ShareAlphaModal, AlphaCard });
