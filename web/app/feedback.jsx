/* ===== 개선 제안 (팀원 피드백) — 제출 모달 + 제안 목록 탭 ===== */

const FB_STATUS = {
  new:       { label: "🆕 접수",   bg: "var(--res-rail)",    color: "var(--tx-on-light-2)" },
  reviewing: { label: "👀 검토중", bg: "var(--cool-soft)",   color: "var(--cool)" },
  done:      { label: "✅ 반영됨", bg: "var(--accent-soft)", color: "var(--accent-lo)" },
};

function _screenOptions() {
  const tabs = (typeof window !== "undefined" && window.NAV_TABS) ? window.NAV_TABS : [];
  const labels = tabs.filter((t) => t.id !== "feedback").map((t) => t.label);
  return labels.concat(["전체 / 기타"]);
}

// ---- 제출 모달 ----
function FeedbackModal({ currentTab, onClose, onDone }) {
  const opts = _screenOptions();
  const curLabel = (() => {
    const tabs = (window.NAV_TABS || []).find((t) => t.id === currentTab);
    return tabs ? tabs.label : opts[0];
  })();
  const [author, setAuthor] = React.useState("");
  const [screen, setScreen] = React.useState(curLabel);
  const [text, setText] = React.useState("");
  const [shots, setShots] = React.useState([]);   // [{ url, name }] — 여러 장
  const [busy, setBusy] = React.useState(false);

  const onFile = (e) => {
    const files = Array.from(e.target.files || []);
    files.forEach((f) => {
      if (f.size > 4 * 1024 * 1024) { alert(f.name + " — 이미지는 4MB 이하로 첨부해줘."); return; }
      const reader = new FileReader();
      reader.onload = () => setShots((s) => (s.length >= 8 ? s : [...s, { url: reader.result, name: f.name }]));
      reader.readAsDataURL(f);
    });
    e.target.value = "";   // 같은 파일도 다시 선택 가능
  };
  const removeShot = (i) => setShots((s) => s.filter((_, idx) => idx !== i));

  const submit = async () => {
    if (!text.trim()) { alert("개선 내용을 입력해줘."); return; }
    setBusy(true);
    try {
      const r = await fetch("/api/feedback", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ author: author.trim(), tab: screen, text: text.trim(), screenshots: shots.map((s) => s.url) }),
      });
      const res = await r.json();
      if (res.ok) { onDone && onDone('💡 <b>제안 접수 완료</b> — 고마워! "제안" 탭에서 처리 상태를 볼 수 있어.'); onClose(); }
      else { alert(res.error || "제출 실패"); }
    } catch (e) { alert("제출 실패 — " + e.message); }
    setBusy(false);
  };

  const field = { width: "100%", padding: "10px 12px", borderRadius: 8, border: "1px solid var(--res-line)", fontSize: 13.5, color: "var(--tx-on-light)", background: "#fff", outline: "none" };
  const lbl = { fontSize: 12, fontWeight: 700, color: "var(--tx-on-light-2)", marginBottom: 6, display: "block" };

  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, zIndex: 150, background: "rgba(6,8,15,0.55)", display: "grid", placeItems: "center" }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 520, maxWidth: "92vw", background: "#fff", borderRadius: 14, overflow: "hidden", boxShadow: "0 30px 80px rgba(0,0,0,0.4)" }}>
        <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--res-line)", display: "flex", alignItems: "center", gap: 9 }}>
          <span style={{ fontSize: 18 }}>💡</span>
          <span style={{ fontSize: 16.5, fontWeight: 700, color: "var(--tx-on-light)" }}>개선 제안</span>
          <span style={{ fontSize: 12, color: "var(--tx-on-light-3)" }}>— 사이트에서 바꿨으면 하는 점을 남겨줘</span>
        </div>
        <div style={{ padding: "18px 24px", display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", gap: 12 }}>
            <div style={{ flex: 1 }}>
              <label style={lbl}>이름</label>
              <input value={author} onChange={(e) => setAuthor(e.target.value)} placeholder="누가 제안했는지 (선택)" style={field} />
            </div>
            <div style={{ flex: 1 }}>
              <label style={lbl}>어느 화면</label>
              <select value={screen} onChange={(e) => setScreen(e.target.value)} style={field}>
                {opts.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label style={lbl}>개선 내용 <span style={{ color: "var(--down)" }}>*</span></label>
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={5}
              placeholder="지금 어떤 점이 불편한지 + 어떻게 바뀌면 좋겠는지 구체적으로 적어줘. (예: Performance 탭의 차트가 너무 작아요 → 2배로 키워주세요)"
              style={{ ...field, resize: "vertical", lineHeight: 1.5 }} />
          </div>
          <div>
            <label style={lbl}>스크린샷 (선택 · 여러 장 가능)</label>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <label style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid var(--res-line)", background: "var(--res-alt)", fontSize: 12.5, fontWeight: 600, color: "var(--tx-on-light-2)", cursor: shots.length >= 8 ? "default" : "pointer", opacity: shots.length >= 8 ? 0.5 : 1 }}>
                파일 선택
                <input type="file" accept="image/*" multiple disabled={shots.length >= 8} onChange={onFile} style={{ display: "none" }} />
              </label>
              <span style={{ fontSize: 12, color: "var(--tx-on-light-3)" }}>{shots.length ? `${shots.length}장 첨부됨${shots.length >= 8 ? " (최대)" : ""}` : "캡처 이미지를 붙이면 더 정확히 반영돼 (여러 장 OK)"}</span>
            </div>
            {shots.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
                {shots.map((s, i) => (
                  <div key={i} style={{ position: "relative" }}>
                    <img src={s.url} alt="preview" style={{ width: 96, height: 66, objectFit: "cover", borderRadius: 6, border: "1px solid var(--res-line)" }} />
                    <button onClick={() => removeShot(i)} title="제거" style={{ position: "absolute", top: -7, right: -7, width: 18, height: 18, borderRadius: "50%", background: "var(--down)", color: "#fff", fontSize: 12, lineHeight: 1, display: "grid", placeItems: "center", border: "1.5px solid #fff", cursor: "pointer" }}>×</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, padding: "0 24px 20px" }}>
          <button onClick={onClose} style={{ padding: "10px 20px", borderRadius: 8, border: "1px solid var(--res-line)", background: "#fff", fontSize: 13.5, fontWeight: 600, color: "var(--tx-on-light-2)" }}>취소</button>
          <button onClick={submit} disabled={busy || !text.trim()} style={{ padding: "10px 24px", borderRadius: 8, background: (busy || !text.trim()) ? "#e9ecf1" : "var(--accent)", color: (busy || !text.trim()) ? "var(--tx-on-light-3)" : "#fff", fontSize: 13.5, fontWeight: 700, cursor: (busy || !text.trim()) ? "default" : "pointer" }}>
            {busy ? "제출 중…" : "제안 보내기"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---- 제안 목록 탭 ----
function FeedbackTab() {
  const [items, setItems] = React.useState(null);
  const [lightbox, setLightbox] = React.useState(null);

  const load = () => {
    fetch("/api/feedback").then((r) => r.json()).then((d) => setItems(d.items || []))
      .catch(() => setItems([]));
  };
  React.useEffect(() => { load(); }, []);

  const counts = (items || []).reduce((a, x) => { a[x.status] = (a[x.status] || 0) + 1; return a; }, {});

  const badge = (st) => {
    const s = FB_STATUS[st] || FB_STATUS.new;
    return <span style={{ fontSize: 11, fontWeight: 700, padding: "3px 9px", borderRadius: 12, background: s.bg, color: s.color, whiteSpace: "nowrap" }}>{s.label}</span>;
  };

  return (
    <Page title="개선 제안" sub="팀원들이 남긴 제안과 처리 상태. (검토 후 반영되면 ‘반영됨’으로 표시돼요)"
      right={<button onClick={load} style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid var(--res-line)", background: "#fff", fontSize: 12.5, fontWeight: 600, color: "var(--tx-on-light-2)" }}>새로고침</button>}>

      {items && items.length > 0 && (
        <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
          {[["new", "접수"], ["reviewing", "검토중"], ["done", "반영됨"]].map(([k, l]) => (
            <div key={k} style={{ display: "flex", alignItems: "center", gap: 7, padding: "6px 13px", borderRadius: 20, background: FB_STATUS[k].bg, color: FB_STATUS[k].color, fontSize: 12.5, fontWeight: 700 }}>
              {l} <span className="tabnum">{counts[k] || 0}</span>
            </div>
          ))}
        </div>
      )}

      {items === null ? (
        <div style={{ padding: "40px 4px", color: "var(--tx-on-light-3)", fontSize: 13 }}>불러오는 중…</div>
      ) : items.length === 0 ? (
        <Card><div style={{ padding: "30px 4px", textAlign: "center", color: "var(--tx-on-light-3)", fontSize: 13.5 }}>
          아직 제안이 없어요. 상단 우측 <b style={{ color: "var(--accent)" }}>💡 개선 제안</b> 버튼으로 첫 제안을 남겨보세요!
        </div></Card>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {items.map((it) => (
            <Card key={it.id} pad={16}>
              <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 9 }}>
                <span style={{ fontWeight: 700, fontSize: 13.5, color: "var(--tx-on-light)" }}>{it.author || "익명"}</span>
                {it.tab && <span style={{ fontSize: 10.5, fontWeight: 700, padding: "2px 7px", borderRadius: 4, background: "var(--res-alt)", color: "var(--tx-on-light-2)" }}>{it.tab}</span>}
                <span style={{ fontSize: 11.5, color: "var(--tx-on-light-3)" }}>{it.ts}</span>
                <div style={{ flex: 1 }} />
                {badge(it.status)}
              </div>
              <div style={{ fontSize: 13.5, color: "var(--tx-on-light)", lineHeight: 1.55, whiteSpace: "pre-wrap" }}>{it.text}</div>
              {it.shots > 0 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 11 }}>
                  {Array.from({ length: it.shots }).map((_, i) => (
                    <img key={i} src={`/api/feedback/shot/${it.id}/${i}`} alt="screenshot" onClick={() => setLightbox(`/api/feedback/shot/${it.id}/${i}`)}
                      style={{ maxHeight: 130, maxWidth: 200, borderRadius: 8, border: "1px solid var(--res-line)", cursor: "zoom-in" }} />
                  ))}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {lightbox && (
        <div onClick={() => setLightbox(null)} style={{ position: "fixed", inset: 0, zIndex: 160, background: "rgba(6,8,15,0.8)", display: "grid", placeItems: "center", cursor: "zoom-out" }}>
          <img src={lightbox} alt="screenshot" style={{ maxWidth: "92vw", maxHeight: "92vh", borderRadius: 8, boxShadow: "0 20px 60px rgba(0,0,0,0.5)" }} />
        </div>
      )}
    </Page>
  );
}

Object.assign(window, { FeedbackModal, FeedbackTab });
