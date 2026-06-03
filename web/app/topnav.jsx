/* ===== Top navigation ===== */

const NAV_TABS = [
  { id: "backtest",    label: "Backtest",    icon: "flask" },
  { id: "performance", label: "Performance", icon: "chart" },
  { id: "orders",      label: "Orders",      icon: "clipboard" },
  { id: "positions",   label: "Positions",   icon: "bars" },
  { id: "botlogs",     label: "Bot Logs",    icon: "doc" },
  { id: "news",        label: "News",        icon: "news" },
  { id: "alphas",      label: "Alphas",      icon: "alpha" },
  { id: "feedback",    label: "제안",        icon: "list" },
];

function TopNav({ active, onChange, onFeedback }) {
  const D = window.AB_DATA;
  const acct = D.account;
  return (
    <header style={{
      display: "flex", alignItems: "stretch", background: "var(--nav-bg)",
      height: 54, flexShrink: 0, borderBottom: "1px solid #000",
      color: "var(--tx-on-dark)", userSelect: "none",
    }}>
      {/* brand */}
      <div style={{
        display: "flex", alignItems: "center", gap: 11, padding: "0 22px 0 20px",
        background: "var(--nav-logo-bg)", minWidth: 232,
        clipPath: "polygon(0 0, 100% 0, calc(100% - 16px) 100%, 0 100%)",
      }}>
        <AlphaMark size={28} />
        <div style={{ lineHeight: 1.05 }}>
          <div style={{ fontSize: 9.5, letterSpacing: 3, color: "var(--tx-on-dark-2)", fontWeight: 600 }}>SNU&nbsp;QUANT</div>
          <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: 0.4 }}>ALPHA&nbsp;BOT</div>
        </div>
      </div>

      {/* tabs */}
      <nav style={{ display: "flex", alignItems: "stretch", marginLeft: 6 }}>
        {NAV_TABS.map((t) => {
          const on = active === t.id;
          return (
            <button key={t.id} onClick={() => onChange(t.id)} style={{
              display: "flex", alignItems: "center", gap: 8, padding: "0 18px",
              color: on ? "#fff" : "var(--tx-on-dark-2)",
              background: on ? "rgba(255,255,255,0.06)" : "transparent",
              boxShadow: on ? "inset 0 -2px 0 var(--accent)" : "none",
              fontSize: 13.5, fontWeight: on ? 600 : 500, whiteSpace: "nowrap", transition: "color .15s, background .15s",
            }}
              onMouseEnter={(e) => { if (!on) e.currentTarget.style.color = "#cdd4e2"; }}
              onMouseLeave={(e) => { if (!on) e.currentTarget.style.color = "var(--tx-on-dark-2)"; }}>
              <Icon name={t.icon} size={16} sw={1.7} style={{ opacity: on ? 1 : 0.8 }} />
              {t.label}
            </button>
          );
        })}
      </nav>

      <div style={{ flex: 1 }} />

      {/* status + icons */}
      <div style={{ display: "flex", alignItems: "center", gap: 4, paddingRight: 14 }}>
        <button onClick={onFeedback} title="이 사이트 개선 제안 남기기" style={{
          display: "flex", alignItems: "center", gap: 6, padding: "0 13px", marginRight: 8,
          height: 32, borderRadius: 16, background: "rgba(34,160,107,0.16)",
          border: "1px solid rgba(40,184,123,0.35)", color: "#5fe0a6", fontSize: 12.5, fontWeight: 600,
        }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(34,160,107,0.26)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(34,160,107,0.16)"; }}>
          <span style={{ fontSize: 13 }}>💡</span> 개선 제안
        </button>
        <div style={{
          display: "flex", alignItems: "center", gap: 8, padding: "0 14px", marginRight: 6,
          height: 32, borderRadius: 16, background: "rgba(255,255,255,0.05)",
          border: "1px solid rgba(255,255,255,0.07)",
        }}>
          <span style={{
            width: 7, height: 7, borderRadius: "50%",
            background: acct.marketOpen ? "var(--up)" : "var(--down)",
            boxShadow: acct.marketOpen ? "0 0 0 3px rgba(22,163,106,0.2)" : "none",
            animation: acct.marketOpen ? "pulse 2s infinite" : "none",
          }} />
          <span style={{ fontSize: 11.5, color: "var(--tx-on-dark-2)", fontWeight: 600, letterSpacing: 0.3 }}>
            US&nbsp;{acct.marketOpen ? "OPEN" : "CLOSED"}
          </span>
          <span style={{ width: 1, height: 16, background: "rgba(255,255,255,0.12)" }} />
          <span style={{ fontSize: 12.5, fontWeight: 600 }} className="tabnum">{fmtUSD(acct.equity, 0)}</span>
          <span className="tabnum" style={{ fontSize: 11, color: acct.dailyReturn >= 0 ? "var(--up)" : "var(--down)" }}>
            {fmtPct(acct.dailyReturn)}
          </span>
        </div>
      </div>
    </header>
  );
}

Object.assign(window, { TopNav, NAV_TABS });
