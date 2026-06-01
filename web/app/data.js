/* ===== Placeholder data for SNU Quant Alpha Bot ===== */
(function () {
  // deterministic pseudo-random for repeatable curves
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // ---- equity curve (cumulative, x ~ 5y of trading days, monthly points) ----
  function buildCurve(seed, n, drift, vol, start) {
    const rnd = mulberry32(seed);
    const pts = [];
    let v = start;
    for (let i = 0; i < n; i++) {
      const shock = (rnd() - 0.5) * vol;
      v = v * (1 + drift + shock);
      pts.push(v);
    }
    return pts;
  }

  const months = [];
  const startY = 2019;
  for (let y = 0; y < 5; y++) {
    for (let m = 0; m < 12; m++) {
      months.push({ y: startY + y, m });
    }
  }
  const monthLabels = months.map(({ y, m }) => {
    const mm = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][m];
    return `${mm} '${String(y).slice(2)}`;
  });

  const pnlCurve = buildCurve(7, months.length, 0.028, 0.05, 1000);
  // scale so it ends near 6,800K like the reference
  const pnlScaled = pnlCurve.map((v) => v * 6.6);

  const MONO = ["#16a36a"]; // accent line

  // ---- IS summary aggregate ----
  const isSummary = {
    sharpe: 1.32,
    turnover: 1.342,
    fitness: 0.43,
    returns: 0.1424,
    drawdown: 0.0697,
    margin: 0.00213,
    win: 0.541,
    avgMaxWeight: 0.021,
    nDays: 1258,
    annual: 0.1112,
  };

  const yearRows = [
    { year: 2019, sharpe: 0.91, turnover: 1.3288, fitness: 0.17, returns: 0.0483, drawdown: 0.0440, margin: 0.00073, long: 1556, short: 1550 },
    { year: 2020, sharpe: 1.14, turnover: 1.3407, fitness: 0.37, returns: 0.1375, drawdown: 0.0697, margin: 0.00205, long: 1552, short: 1550 },
    { year: 2021, sharpe: 0.89, turnover: 1.3497, fitness: 0.25, returns: 0.1069, drawdown: 0.0604, margin: 0.00158, long: 1580, short: 1573 },
    { year: 2022, sharpe: 1.28, turnover: 1.3382, fitness: 0.47, returns: 0.1833, drawdown: 0.0524, margin: 0.00274, long: 1581, short: 1574 },
    { year: 2023, sharpe: 3.19, turnover: 1.3429, fitness: 1.36, returns: 0.2442, drawdown: 0.0406, margin: 0.00364, long: 1585, short: 1582 },
  ];

  // ---- market indices ----
  function spark(seed, up) {
    const rnd = mulberry32(seed); const a = []; let v = 100;
    for (let i = 0; i < 28; i++) { v += (rnd() - (up ? 0.42 : 0.58)) * 2.4; a.push(v); }
    return a;
  }
  const indices = [
    { sym: "^GSPC", label: "S&P 500", price: 5938.42, chg: 24.31, pct: 0.41, up: true, spark: spark(1, true) },
    { sym: "^IXIC", label: "NASDAQ", price: 19173.55, chg: 118.44, pct: 0.62, up: true, spark: spark(2, true) },
    { sym: "^DJI", label: "DOW", price: 42735.10, chg: -86.20, pct: -0.20, up: false, spark: spark(3, false) },
    { sym: "^VIX", label: "VIX", price: 14.22, chg: -0.63, pct: -4.24, up: false, spark: spark(4, false) },
  ];

  // ---- account ----
  const account = {
    equity: 104812.55,
    cash: 18204.11,
    buyingPower: 209625.10,
    lastEquity: 103990.02,
    positions: 312,
    openOrders: 6,
    marketOpen: true,
    nextEvent: "06/02 05:00 KST",
  };
  account.dailyReturn = (account.equity - account.lastEquity) / account.lastEquity;

  // ---- portfolio equity history (1M daily) ----
  const acctHist = (function () {
    const rnd = mulberry32(11); const a = []; let v = 99250;
    const days = 22;
    for (let i = 0; i < days; i++) {
      v = v * (1 + 0.0011 + (rnd() - 0.46) * 0.012);
      const d = new Date(2026, 4, 1 + i);
      a.push({ date: `${d.getMonth() + 1}/${d.getDate()}`, equity: v });
    }
    a[a.length - 1].equity = account.equity;
    return a;
  })();

  // daily perf table (recent first)
  const dailyPerf = (function () {
    const out = [];
    for (let i = acctHist.length - 1; i > 0; i--) {
      const eq = acctHist[i].equity;
      const prev = acctHist[i - 1].equity;
      const pl = eq - prev;
      const ret = pl / prev;
      const cum = eq / acctHist[0].equity - 1;
      out.push({ date: acctHist[i].date, equity: eq, pl, ret, cum });
    }
    return out;
  })();

  // ---- positions ----
  const COMPANIES = [
    ["NVDA","NVIDIA Corp","Information Technology"],["AAPL","Apple Inc.","Information Technology"],
    ["MSFT","Microsoft Corp","Information Technology"],["AMZN","Amazon.com","Consumer Discretionary"],
    ["META","Meta Platforms","Communication Services"],["GOOGL","Alphabet Inc.","Communication Services"],
    ["JPM","JPMorgan Chase","Financials"],["XOM","Exxon Mobil","Energy"],
    ["LLY","Eli Lilly","Health Care"],["AVGO","Broadcom Inc.","Information Technology"],
    ["TSLA","Tesla Inc.","Consumer Discretionary"],["UNH","UnitedHealth","Health Care"],
    ["V","Visa Inc.","Financials"],["PG","Procter & Gamble","Consumer Staples"],
    ["HD","Home Depot","Consumer Discretionary"],["COST","Costco","Consumer Staples"],
    ["MRK","Merck & Co.","Health Care"],["ABBV","AbbVie Inc.","Health Care"],
    ["CRM","Salesforce","Information Technology"],["KO","Coca-Cola","Consumer Staples"],
  ];
  function mkPositions(seed, side) {
    const rnd = mulberry32(seed);
    return COMPANIES.slice(0, 10).map(([sym, name, sector], i) => {
      const qty = (side === "long" ? 1 : -1) * (20 + rnd() * 180);
      const px = 60 + rnd() * 400;
      const mv = qty * px;
      const plpc = (rnd() - (side === "long" ? 0.42 : 0.5)) * 0.18;
      return { sym, name, sector, qty, price: px, marketValue: mv, plpc, pl: mv * plpc };
    });
  }
  const longs = mkPositions(21, "long");
  const shorts = mkPositions(22, "short");

  // open orders
  function mkOrders(seed, side) {
    const rnd = mulberry32(seed);
    return COMPANIES.slice(0, 6).map(([sym, name, sector]) => {
      const qty = (10 + rnd() * 60);
      const px = 60 + rnd() * 400;
      return { sym, name, sector, side, qty, price: px, cost: qty * px };
    });
  }
  const buyOrders = mkOrders(31, "buy");
  const sellOrders = mkOrders(32, "sell");

  // bot logs
  const botLogs = [
    { file: "run_20260601_0930.json", at: "2026-06-01 09:30 ET", mode: "LIVE", status: "ok", orders: 318, longs: 156, shorts: 156, note: "rank(-returns) · Sector neutral", durMs: 28420 },
    { file: "run_20260531_0930.json", at: "2026-05-31 09:30 ET", mode: "LIVE", status: "ok", orders: 312, longs: 154, shorts: 158, note: "rank(-returns) · Sector neutral", durMs: 26110 },
    { file: "run_20260530_1610.json", at: "2026-05-30 16:10 ET", mode: "DRY", status: "ok", orders: 0, longs: 0, shorts: 0, note: "Dry run — no orders submitted", durMs: 9240 },
    { file: "run_20260530_0930.json", at: "2026-05-30 09:30 ET", mode: "LIVE", status: "warn", orders: 298, longs: 149, shorts: 149, note: "14 symbols skipped (no data)", durMs: 31980 },
    { file: "run_20260529_0930.json", at: "2026-05-29 09:30 ET", mode: "LIVE", status: "ok", orders: 320, longs: 160, shorts: 160, note: "rank(-returns) · Sector neutral", durMs: 25770 },
  ];

  // news
  const news = [
    { title: "Fed holds rates steady, signals patience on first 2026 cut", titleKo: "연준 금리 동결, 2026년 첫 인하에 신중론", pub: "CNBC Markets", ago: "23분 전", tickers: ["SPY","TLT"] },
    { title: "Nvidia tops estimates as data-center revenue surges 78%", titleKo: "엔비디아, 데이터센터 매출 78% 급증하며 컨센서스 상회", pub: "MarketWatch", ago: "1시간 전", tickers: ["NVDA","AVGO"] },
    { title: "Oil slides below $70 as OPEC+ weighs output hike", titleKo: "OPEC+ 증산 검토에 유가 70달러 하회", pub: "Investing.com", ago: "2시간 전", tickers: ["XOM","CVX"] },
    { title: "Apple unveils on-device AI tier, shares pop in late trade", titleKo: "애플, 온디바이스 AI 등급 공개…시간외 강세", pub: "CNBC Markets", ago: "3시간 전", tickers: ["AAPL"] },
    { title: "Retail sales beat as consumer holds up into summer", titleKo: "소매판매 호조, 여름철 소비 견조", pub: "MarketWatch", ago: "4시간 전", tickers: ["AMZN","HD","COST"] },
    { title: "Treasury yields ease ahead of payrolls data Friday", titleKo: "금요일 고용지표 앞두고 국채 금리 하락", pub: "Investing.com", ago: "5시간 전", tickers: ["TLT"] },
  ];
  const aiSummary = [
    "연준 금리 동결 — 첫 인하 시점 지연 전망, 금리 민감 섹터($TLT) 변동성 주의",
    "엔비디아 어닝 서프라이즈로 반도체 전반 강세 ($NVDA, $AVGO)",
    "OPEC+ 증산 가능성에 에너지 섹터 약세 ($XOM, $CVX)",
    "애플 온디바이스 AI 발표 — IT 섹터 모멘텀 ($AAPL)",
    "소비 견조 확인, 임의소비재 우호적 ($AMZN, $HD)",
  ];

  // ---- autocomplete variables (Brain-style) ----
  const variables = [
    { name: "returns", type: "Matrix, Price Volume", desc: "Daily returns" },
    { name: "close", type: "Matrix, Price Volume", desc: "Daily close price" },
    { name: "open", type: "Matrix, Price Volume", desc: "Daily open price" },
    { name: "high", type: "Matrix, Price Volume", desc: "Daily high price" },
    { name: "low", type: "Matrix, Price Volume", desc: "Daily low price" },
    { name: "volume", type: "Matrix, Price Volume", desc: "Daily volume" },
    { name: "cap", type: "Matrix, Fundamental", desc: "Market capitalization" },
    { name: "revenue", type: "Matrix, Fundamental", desc: "Total revenue (TTM)" },
    { name: "ni", type: "Matrix, Fundamental", desc: "Net income" },
    { name: "fcf", type: "Matrix, Fundamental", desc: "Free cash flow" },
    { name: "roe", type: "Matrix, Fundamental", desc: "Return on equity" },
    { name: "pe", type: "Matrix, Fundamental", desc: "Price / Earnings" },
    { name: "pb", type: "Matrix, Fundamental", desc: "Price / Book" },
    { name: "sector", type: "Group, GICS", desc: "GICS Sector" },
    { name: "ppent", type: "Matrix, Fundamental", desc: "Net property, plant & equipment" },
  ];

  // example alphas
  const examples = [
    { label: "Short-term mean reversion", expr: "rank(-returns)" },
    { label: "Quality — high ROE", expr: "rank(roe)" },
    { label: "Value — low P/E", expr: "rank(-pe)" },
    { label: "FCF yield", expr: "rank(fcf / cap)" },
    { label: "Cap-bucket asset value", expr: "group_neutralize(\n  winsorize(ts_backfill((ppent + cash) / cap, 63), std=4),\n  bucket(rank(cap), range='0,1,0.1')\n)" },
  ];

  window.AB_DATA = {
    monthLabels, pnlScaled, isSummary, yearRows, indices, account,
    acctHist, dailyPerf, longs, shorts, buyOrders, sellOrders,
    botLogs, news, aiSummary, variables, examples,
  };
})();
