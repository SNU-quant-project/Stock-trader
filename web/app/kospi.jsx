/* ===== KOSPI 모의 트레이딩 페이지 (독립 SPA) =====
   섹션: ① 현재 운용 알파  ② 지수(KOSPI) 대비 1년 수익률 비교  ③ 현재 포지션
   기존 components.jsx (MultiLineChart/Icon/AlphaMark) 재사용. */

const fmtKRW = (v) => "₩" + Math.round(v).toLocaleString("ko-KR");
const kpct = (v, d = 2) => (v >= 0 ? "+" : "") + Number(v).toFixed(d) + "%";

// KSIC 중분류(2자리) → 읽기 쉬운 업종명 (없으면 코드 표시)
const KSIC2 = {
  "10": "식료품", "11": "음료", "13": "섬유", "17": "펄프·종이", "18": "인쇄",
  "19": "석유정제", "20": "화학", "21": "의약품", "22": "고무·플라스틱", "23": "비금속광물",
  "24": "1차금속", "25": "금속가공", "26": "전자·반도체", "27": "의료·정밀기기", "28": "전기장비",
  "29": "기계·장비", "30": "자동차", "31": "기타운송장비", "32": "가구", "33": "기타제조",
  "35": "전기·가스", "36": "수도", "41": "건설", "42": "토목", "45": "자동차판매",
  "46": "도매", "47": "소매", "49": "육상운송", "50": "수상운송", "51": "항공운송",
  "52": "물류·창고", "58": "출판", "59": "영상·방송", "61": "통신", "62": "소프트웨어",
  "63": "정보서비스", "64": "금융", "65": "보험", "66": "금융지원", "68": "부동산",
  "70": "연구개발", "71": "전문서비스", "72": "건축기술", "73": "기타전문", "86": "의료",
};
const secName = (c) => KSIC2[String(c)] || ("업종 " + c);

function KCard({ children, style, pad = 20 }) {
  return <div style={{ background: "#fff", border: "1px solid var(--res-line)", borderRadius: "var(--r-lg,14px)", padding: pad, ...style }}>{children}</div>;
}
function KTitle({ children, sub }) {
  return <h2 style={{ fontSize: 16, fontWeight: 700, color: "var(--tx-on-light)", margin: "0 0 14px" }}>{children}
    {sub && <span style={{ fontSize: 12, fontWeight: 500, color: "var(--tx-on-light-3)", marginLeft: 8 }}>{sub}</span>}</h2>;
}

// ① 현재 운용 알파
function AlphaSection({ alpha, settings }) {
  return (
    <KCard style={{ marginBottom: 18, background: "linear-gradient(160deg,#0f1320,#161a28)", border: "none" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 12 }}>
        <AlphaMark size={20} color="var(--accent-hi)" />
        <span style={{ fontSize: 15, fontWeight: 700, color: "#fff" }}>현재 운용 중인 알파</span>
        <span style={{ fontSize: 10.5, fontWeight: 700, padding: "2px 8px", borderRadius: 5, background: "rgba(34,160,107,0.2)", color: "var(--accent-hi)", letterSpacing: 0.5 }}>LONG-ONLY</span>
        <span style={{ fontSize: 11.5, color: "var(--tx-on-dark-3)" }}>KOSPI 모의 트레이딩 · 이 포지션을 만든 수식</span>
      </div>
      <pre style={{ margin: 0, fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--accent-hi)", background: "rgba(0,0,0,0.28)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "12px 14px", whiteSpace: "pre-wrap", lineHeight: 1.55, overflowX: "auto" }}>{alpha}</pre>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
        {Object.entries(settings).map(([k, v]) => (
          <span key={k} style={{ fontSize: 11.5, color: "var(--tx-on-dark-2)", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, padding: "4px 10px" }}>{k} <b style={{ color: "#fff" }}>{String(v)}</b></span>
        ))}
      </div>
    </KCard>
  );
}

// ② 지수 대비 1년 수익률 비교
function CompareSection({ compare, summary }) {
  const final = (name) => { const s = compare.series.find((x) => x.name === name); if (!s) return null; for (let i = s.values.length - 1; i >= 0; i--) if (s.values[i] != null) return s.values[i]; return null; };
  return (
    <KCard style={{ marginBottom: 18 }}>
      <KTitle sub={`지난 ${summary.days}거래일 · 기간 시작 = 0%`}>KOSPI 지수 대비 수익률 비교</KTitle>
      <div style={{ display: "flex", gap: 20, flexWrap: "wrap", marginBottom: 8 }}>
        {compare.series.map((s) => { const f = final(s.name); return (
          <div key={s.name} style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span style={{ width: 16, height: 3, borderRadius: 2, background: s.color, display: "inline-block" }} />
            <span style={{ fontSize: 12.5, color: "var(--tx-on-light-2)" }}>{s.name}</span>
            {f != null && <span className="tabnum" style={{ fontSize: 12.5, fontWeight: 700, color: f >= 0 ? "var(--up)" : "var(--down)" }}>{kpct(f)}</span>}
          </div>
        ); })}
        <div style={{ flex: 1 }} />
        <div style={{ fontSize: 12.5, color: "var(--tx-on-light-2)" }}>지수 대비 초과수익 <b style={{ color: summary.excess1y >= 0 ? "var(--up)" : "var(--down)" }}>{kpct(summary.excess1y)}</b></div>
      </div>
      <MultiLineChart series={compare.series} labels={compare.labels} height={300} />
    </KCard>
  );
}

// ③ 현재 포지션
function PositionsSection({ positions, nPositions, asOf }) {
  return (
    <KCard>
      <KTitle sub={`${asOf} 기준 · long-only · 비중합 100% · 종목당 최대 8%`}>현재 포지션 <span style={{ color: "var(--tx-on-light-2)", fontWeight: 600 }}>{nPositions}종목</span></KTitle>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
        <thead>
          <tr style={{ color: "var(--tx-on-light-3)", fontSize: 11, textAlign: "left", borderBottom: "1px solid var(--res-line)" }}>
            <th style={{ padding: "7px 4px", fontWeight: 600 }}>#</th>
            <th style={{ padding: "7px 4px", fontWeight: 600 }}>종목코드</th>
            <th style={{ padding: "7px 4px", fontWeight: 600 }}>종목명</th>
            <th style={{ padding: "7px 4px", fontWeight: 600 }}>업종</th>
            <th style={{ padding: "7px 4px", fontWeight: 600, textAlign: "right" }}>현재가</th>
            <th style={{ padding: "7px 4px", fontWeight: 600, textAlign: "right" }}>비중</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p, i) => (
            <tr key={p.sym} style={{ borderBottom: "1px solid #f0f2f6" }}>
              <td style={{ padding: "8px 4px", color: "var(--tx-on-light-3)" }}>{i + 1}</td>
              <td style={{ padding: "8px 4px", fontWeight: 700 }}>
                <a href={`https://finance.naver.com/item/main.naver?code=${p.sym}`} target="_blank" rel="noopener noreferrer"
                   style={{ color: "var(--tx-on-light)", textDecoration: "none" }}
                   onMouseEnter={(e) => { e.currentTarget.style.color = "var(--cool)"; e.currentTarget.style.textDecoration = "underline"; }}
                   onMouseLeave={(e) => { e.currentTarget.style.color = "var(--tx-on-light)"; e.currentTarget.style.textDecoration = "none"; }}>{p.sym}</a>
              </td>
              <td style={{ padding: "8px 4px", color: "var(--tx-on-light)" }}>{p.name}</td>
              <td style={{ padding: "8px 4px", color: "var(--tx-on-light-2)", fontSize: 11.5 }}>{secName(p.sector)}</td>
              <td className="tabnum" style={{ padding: "8px 4px", textAlign: "right" }}>{fmtKRW(p.price)}</td>
              <td className="tabnum" style={{ padding: "8px 4px", textAlign: "right", fontWeight: 700, color: "var(--accent)" }}>{(p.weight * 100).toFixed(2)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </KCard>
  );
}

function KospiApp() {
  const [d, setD] = React.useState(null);
  const [err, setErr] = React.useState(null);
  React.useEffect(() => {
    fetch("/api/kospi").then((r) => r.json()).then((res) => {
      if (res.error) setErr(res.error); else setD(res);
    }).catch((e) => setErr(e.message));
  }, []);

  return (
    <div style={{ minHeight: "100vh", background: "var(--res-alt,#f3f5f8)" }}>
      <header style={{ display: "flex", alignItems: "center", gap: 12, background: "var(--nav-bg,#0f1320)", height: 54, padding: "0 24px", color: "#fff" }}>
        <AlphaMark size={26} />
        <div style={{ lineHeight: 1.05 }}>
          <div style={{ fontSize: 9.5, letterSpacing: 3, color: "var(--tx-on-dark-2,#9aa3b8)", fontWeight: 600 }}>SNU&nbsp;QUANT</div>
          <div style={{ fontSize: 16, fontWeight: 700 }}>KOSPI 모의 트레이딩</div>
        </div>
        <div style={{ flex: 1 }} />
        <a href="/" style={{ fontSize: 12.5, color: "var(--tx-on-dark-2,#9aa3b8)", textDecoration: "none" }}>← AlphaBot(미국)</a>
      </header>
      <div style={{ maxWidth: 1080, margin: "0 auto", padding: "24px 24px 64px" }}>
        {err ? (
          <KCard><div style={{ padding: 30, textAlign: "center", color: "var(--down)" }}>데이터 로드 실패: {err}</div></KCard>
        ) : !d ? (
          <KCard><div style={{ padding: 40, textAlign: "center", color: "var(--tx-on-light-3)" }}>불러오는 중… (알파 평가 + 1년 백테스트)</div></KCard>
        ) : (
          <>
            <AlphaSection alpha={d.alpha} settings={d.settings} />
            <CompareSection compare={d.compare} summary={d.summary} />
            <PositionsSection positions={d.positions} nPositions={d.nPositions} asOf={d.asOf} />
          </>
        )}
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<KospiApp />);
