/* ===== Shared UI: icons, charts, formatters ===== */

// ---- formatters ----
const fmtUSD = (v, d = 2) => "$" + v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const fmtUSD0 = (v) => "$" + Math.round(v).toLocaleString("en-US");
const fmtPct = (v, d = 2) => (v >= 0 ? "+" : "") + (v * 100).toFixed(d) + "%";
const fmtPctRaw = (v, d = 2) => (v * 100).toFixed(d) + "%";
const fmtNum = (v, d = 2) => v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const fmtPermil = (v) => (v * 1000).toFixed(2) + "‰";

// ---- icon set (simple line icons) ----
function Ic({ d, size = 18, sw = 1.6, fill, style }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={fill || "none"}
      stroke={fill ? "none" : "currentColor"} strokeWidth={sw} strokeLinecap="round"
      strokeLinejoin="round" style={style}>
      {Array.isArray(d) ? d.map((p, i) => <path key={i} d={p} />) : <path d={d} />}
    </svg>
  );
}

const ICONS = {
  play:   "M7 5l12 7-12 7V5z",
  chart:  ["M4 19V5", "M4 19h16", "M7 15l4-5 3 3 5-7"],
  bars:   ["M5 20V10", "M12 20V4", "M19 20v-7"],
  scatter:["M4 20h16", "M4 20V4"],
  scatterDots: ["M7 15a1 1 0 100-2 1 1 0 000 2z","M12 10a1 1 0 100-2 1 1 0 000 2z","M16 14a1 1 0 100-2 1 1 0 000 2z","M4 20h16","M4 20V4"],
  clipboard: ["M9 4h6v2H9z", "M9 5H6v15h12V5h-3", "M9 11h6", "M9 15h6"],
  toggle: ["M8 7h8a5 5 0 010 10H8a5 5 0 010-10z", "M8 16a4 4 0 100-8 4 4 0 000 8z"],
  edit:   ["M4 20h4L18 10l-4-4L4 16v4z", "M13 7l4 4"],
  gear:   ["M12 9a3 3 0 100 6 3 3 0 000-6z", "M19 12a7 7 0 00-.14-1.4l1.9-1.48-2-3.46-2.24.9a7 7 0 00-2.42-1.4L13.5 2h-3l-.6 2.36a7 7 0 00-2.42 1.4l-2.24-.9-2 3.46 1.9 1.48A7 7 0 005 12c0 .48.05.95.14 1.4l-1.9 1.48 2 3.46 2.24-.9a7 7 0 002.42 1.4L10.5 22h3l.6-2.36a7 7 0 002.42-1.4l2.24.9 2-3.46-1.9-1.48c.09-.45.14-.92.14-1.4z"],
  help:   ["M12 22a10 10 0 100-20 10 10 0 000 20z", "M9.5 9a2.5 2.5 0 014.8.9c0 1.7-2.3 2.1-2.3 3.6", "M12 17h.01"],
  bell:   ["M18 8a6 6 0 10-12 0c0 7-3 8-3 8h18s-3-1-3-8z", "M13.7 21a2 2 0 01-3.4 0"],
  user:   ["M12 12a4 4 0 100-8 4 4 0 000 8z", "M4 21a8 8 0 0116 0"],
  menu:   ["M3 6h18", "M3 12h18", "M3 18h18"],
  chevD:  "M6 9l6 6 6-6",
  chevR:  "M9 6l6 6-6 6",
  chevU:  "M6 15l6-6 6 6",
  close:  ["M6 6l12 12", "M18 6L6 18"],
  plus:   ["M12 5v14", "M5 12h14"],
  check:  "M5 12l5 5L20 6",
  list:   ["M8 6h13", "M8 12h13", "M8 18h13", "M3 6h.01", "M3 12h.01", "M3 18h.01"],
  ext:    ["M14 4h6v6", "M20 4l-9 9", "M19 13v6a1 1 0 01-1 1H5a1 1 0 01-1-1V6a1 1 0 011-1h6"],
  news:   ["M4 5h13v14H4z", "M17 8h3v9a2 2 0 01-2 2", "M7 9h7", "M7 12h7", "M7 15h4"],
  doc:    ["M6 3h8l4 4v14H6z", "M14 3v4h4"],
  flask:  ["M9 3h6", "M10 3v6l-5 9a1 1 0 001 1.5h12A1 1 0 0015 18l-5-9V3"],
  trash:  ["M4 7h16", "M10 11v6", "M14 11v6", "M6 7l1 13h10l1-13", "M9 7V4h6v3"],
  alpha:  "M16 6c-3 0-5 2.5-5 6s2 6 5 6c1.6 0 2.6-.9 3.2-2.2L18 7.5C17.4 6.6 16.8 6 16 6zM19 6v9c0 1.7.6 3 2 3",
};

function Icon({ name, size, sw, fill, style }) {
  return <Ic d={ICONS[name]} size={size} sw={sw} fill={fill} style={style} />;
}

// ---- Alpha glyph mark ----
function AlphaMark({ size = 26, color = "var(--accent)" }) {
  return (
    <span style={{
      width: size, height: size, flexShrink: 0, display: "inline-grid", placeItems: "center",
      border: `1.6px solid ${color}`, borderRadius: Math.round(size * 0.3), color,
    }} aria-hidden="true">
      <span style={{ fontFamily: '"IBM Plex Sans", system-ui, sans-serif', fontSize: Math.round(size * 0.6), fontWeight: 600, lineHeight: 1, transform: "translateY(-0.5px)" }}>α</span>
    </span>
  );
}

// ---- Sparkline ----
function Sparkline({ values, color, w = 110, h = 44 }) {
  if (!values || values.length < 2) return null;
  const min = Math.min(...values), max = Math.max(...values);
  const rng = max - min || 1, pad = 3;
  const pts = values.map((v, i) => {
    const x = (i * w) / (values.length - 1);
    const y = h - pad - ((v - min) / rng) * (h - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return (
    <svg width={w} height={h} style={{ display: "block" }}>
      <polyline fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" points={pts} />
    </svg>
  );
}

// ---- Area line chart (equity / pnl curve) ----
function LineChart({ values, labels, height = 300, color = "#16a36a", yFmt, fill = true, splitAt }) {
  const ref = React.useRef(null);
  const [w, setW] = React.useState(900);
  React.useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver((e) => setW(e[0].contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  const padL = 54, padR = 14, padT = 12, padB = 26;
  const min = Math.min(...values), max = Math.max(...values);
  const rng = max - min || 1;
  const X = (i) => padL + (i * (w - padL - padR)) / (values.length - 1);
  const Y = (v) => padT + (1 - (v - min) / rng) * (height - padT - padB);
  const linePts = values.map((v, i) => `${X(i)},${Y(v)}`).join(" ");
  const areaPts = `${padL},${height - padB} ${linePts} ${X(values.length - 1)},${height - padB}`;
  const gridN = 5;
  const grid = Array.from({ length: gridN + 1 }, (_, i) => {
    const v = min + (rng * i) / gridN;
    return { y: Y(v), v };
  });
  const tickEvery = Math.ceil(labels.length / 9);
  return (
    <div ref={ref} style={{ width: "100%" }}>
      <svg width={w} height={height} style={{ display: "block" }}>
        <defs>
          <linearGradient id="lcfill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.20" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        {grid.map((g, i) => (
          <g key={i}>
            <line x1={padL} y1={g.y} x2={w - padR} y2={g.y} stroke="#eceef3" strokeWidth="1" />
            <text x={padL - 8} y={g.y + 3} textAnchor="end" fontSize="10" fill="#9aa3b2"
              fontFamily="var(--font-num)">{yFmt ? yFmt(g.v) : g.v.toFixed(0)}</text>
          </g>
        ))}
        {fill && <polygon points={areaPts} fill="url(#lcfill)" />}
        <polyline points={linePts} fill="none" stroke={color} strokeWidth="2"
          strokeLinejoin="round" strokeLinecap="round" />
        {labels.map((lb, i) => i % tickEvery === 0 ? (
          <text key={i} x={X(i)} y={height - 8} textAnchor="middle" fontSize="10"
            fill="#9aa3b2" fontFamily="var(--font-num)">{lb}</text>
        ) : null)}
      </svg>
    </div>
  );
}

// ---- Multi-line chart (수익률 비교: 포트폴리오 vs 지수) ----
function MultiLineChart({ series, labels, height = 300, yFmt }) {
  const ref = React.useRef(null);
  const [w, setW] = React.useState(900);
  React.useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver((e) => setW(e[0].contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  const padL = 54, padR = 14, padT = 12, padB = 26;
  const all = series.flatMap((s) => s.values).filter((v) => v != null && !isNaN(v));
  if (!all.length || labels.length < 2) {
    return <div style={{ height, display: "grid", placeItems: "center", color: "var(--tx-on-light-3)", fontSize: 13 }}>비교할 데이터가 부족합니다.</div>;
  }
  const min = Math.min(...all, 0), max = Math.max(...all, 0);
  const rng = (max - min) || 1;
  const n = labels.length;
  const X = (i) => padL + (i * (w - padL - padR)) / Math.max(1, n - 1);
  const Y = (v) => padT + (1 - (v - min) / rng) * (height - padT - padB);
  const gridN = 5;
  const grid = Array.from({ length: gridN + 1 }, (_, i) => { const v = min + (rng * i) / gridN; return { y: Y(v), v }; });
  const tickEvery = Math.max(1, Math.ceil(n / 9));
  const segsFor = (vals) => {
    const segs = []; let cur = [];
    vals.forEach((v, i) => {
      if (v == null || isNaN(v)) { if (cur.length) { segs.push(cur); cur = []; } }
      else cur.push(`${X(i)},${Y(v)}`);
    });
    if (cur.length) segs.push(cur);
    return segs;
  };
  const zeroY = Y(0);
  return (
    <div ref={ref} style={{ width: "100%" }}>
      <svg width={w} height={height} style={{ display: "block" }}>
        {grid.map((g, i) => (
          <g key={i}>
            <line x1={padL} y1={g.y} x2={w - padR} y2={g.y} stroke="#eceef3" strokeWidth="1" />
            <text x={padL - 8} y={g.y + 3} textAnchor="end" fontSize="10" fill="#9aa3b2" fontFamily="var(--font-num)">{yFmt ? yFmt(g.v) : (g.v >= 0 ? "+" : "") + g.v.toFixed(1) + "%"}</text>
          </g>
        ))}
        <line x1={padL} y1={zeroY} x2={w - padR} y2={zeroY} stroke="#c0c7d2" strokeWidth="1" strokeDasharray="3 3" />
        {series.map((s, si) => segsFor(s.values).map((seg, gi) => (
          <polyline key={si + "-" + gi} points={seg.join(" ")} fill="none" stroke={s.color}
            strokeWidth={si === 0 ? 2.6 : 1.8} strokeLinejoin="round" strokeLinecap="round" opacity={si === 0 ? 1 : 0.85} />
        )))}
        {labels.map((lb, i) => i % tickEvery === 0 ? (
          <text key={i} x={X(i)} y={height - 8} textAnchor="middle" fontSize="10" fill="#9aa3b2" fontFamily="var(--font-num)">{lb}</text>
        ) : null)}
      </svg>
    </div>
  );
}

// ---- Donut ----
function Donut({ items, size = 220, colors }) {
  const total = items.reduce((s, x) => s + x.value, 0) || 1;
  const R = size / 2, r = R * 0.6, cx = R, cy = R;
  let a0 = -Math.PI / 2;
  const arcs = items.map((it, i) => {
    const frac = it.value / total;
    const a1 = a0 + frac * Math.PI * 2;
    const large = a1 - a0 > Math.PI ? 1 : 0;
    const x0 = cx + R * Math.cos(a0), y0 = cy + R * Math.sin(a0);
    const x1 = cx + R * Math.cos(a1), y1 = cy + R * Math.sin(a1);
    const xi0 = cx + r * Math.cos(a1), yi0 = cy + r * Math.sin(a1);
    const xi1 = cx + r * Math.cos(a0), yi1 = cy + r * Math.sin(a0);
    const d = `M${x0},${y0} A${R},${R} 0 ${large} 1 ${x1},${y1} L${xi0},${yi0} A${r},${r} 0 ${large} 0 ${xi1},${yi1} Z`;
    const mid = (a0 + a1) / 2;
    const lr = (R + r) / 2;
    const label = { x: cx + lr * Math.cos(mid), y: cy + lr * Math.sin(mid), frac, sym: it.label };
    a0 = a1;
    return { d, color: colors[i % colors.length], label };
  });
  return (
    <svg width={size} height={size} style={{ display: "block", margin: "0 auto" }}>
      {arcs.map((a, i) => <path key={i} d={a.d} fill={a.color} stroke="#fff" strokeWidth="1.5" />)}
      {arcs.map((a, i) => a.label.frac > 0.05 ? (
        <text key={"t" + i} x={a.label.x} y={a.label.y} textAnchor="middle" dominantBaseline="middle"
          fontSize="10" fontWeight="600" fill="#fff" fontFamily="var(--font-ui)">{a.label.sym}</text>
      ) : null)}
    </svg>
  );
}

Object.assign(window, {
  fmtUSD, fmtUSD0, fmtPct, fmtPctRaw, fmtNum, fmtPermil,
  Icon, Ic, ICONS, AlphaMark, Sparkline, LineChart, MultiLineChart, Donut,
});
