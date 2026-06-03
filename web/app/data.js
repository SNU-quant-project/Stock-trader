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

  // ---- 사용 가능한 데이터 필드 (실제 패널/EDGAR 펀더멘털 컬럼과 일치) ----
  // [name, desc] — 자동완성 + 레퍼런스 패널 공용 소스
  const FIELD_GROUPS = [
    { group: "가격 · 거래량", items: [
      ["close", "일별 종가"], ["open", "일별 시가"], ["high", "일별 고가"],
      ["low", "일별 저가"], ["volume", "일별 거래량"], ["returns", "일별 수익률 (close 변화율)"],
    ]},
    { group: "밸류에이션 (파생)", items: [
      ["cap", "시가총액 = shares × close"], ["pe", "주가수익비율 (close/eps)"],
      ["pb", "주가순자산비율"], ["ps", "주가매출비율"], ["book_value", "주당 순자산 (BPS)"],
    ]},
    { group: "수익성 (파생)", items: [
      ["roe", "자기자본이익률 (ni/equity)"], ["roa", "총자산이익률 (ni/assets)"],
    ]},
    { group: "재무상태표", items: [
      ["cash", "현금 및 현금성자산"], ["debt", "총부채"], ["assets", "총자산"],
      ["ppent", "유형자산 순액 (PP&E)"], ["equity", "자기자본"], ["inventory", "재고자산"],
      ["shares", "발행주식수"], ["retained_earnings", "이익잉여금"],
      ["current_assets", "유동자산"], ["current_liabilities", "유동부채"],
    ]},
    { group: "손익계산서", items: [
      ["revenue", "매출액"], ["ni", "순이익"], ["gross_profit", "매출총이익"],
      ["op_income", "영업이익"], ["ebit", "EBIT"], ["ebitda", "EBITDA"],
      ["eps", "주당순이익 (희석)"], ["cost_of_revenue", "매출원가"],
    ]},
    { group: "현금흐름", items: [
      ["fcf", "잉여현금흐름 (영업CF − capex)"], ["capex", "설비투자"], ["div_paid", "배당 지급액"],
    ]},
    { group: "그룹 (중립화용)", items: [
      ["sector", "GICS 섹터 (industry · subindustry 와 동일)"],
    ]},
  ];

  // ---- 사용 가능한 연산자 (lib/operators.py 와 일치) ----
  // [name, signature, desc]
  const OP_GROUPS = [
    { group: "산술", items: [
      ["add", "add(x, y)", "x + y (filter=true 면 NaN→0)"], ["subtract", "subtract(x, y)", "x − y"],
      ["multiply", "multiply(x, y, …)", "곱"], ["divide", "divide(x, y)", "x / y"],
      ["log", "log(x)", "자연로그"], ["sqrt", "sqrt(x)", "제곱근(|x|)"],
      ["abs", "abs(x)", "절댓값"], ["sign", "sign(x)", "부호 (−1/0/1)"],
      ["power", "power(x, y)", "x의 y승"], ["signed_power", "signed_power(x, y)", "sign(x)·|x|^y"],
      ["inverse", "inverse(x)", "1/x"], ["reverse", "reverse(x)", "−x"],
      ["max", "max(x, y, …)", "원소별 최대"], ["min", "min(x, y, …)", "원소별 최소"],
      ["to_nan", "to_nan(x, value=0)", "특정 값을 NaN 으로 (reverse=true 면 반대)"],
    ]},
    { group: "논리 · 조건", items: [
      ["비교", "x > y, x < y, x == y", "조건 → 참/거짓 (1/0 처럼 사용)"],
      ["삼항", "cond ? a : b", "조건이 참이면 a, 아니면 b (BRAIN 문법)"],
      ["if_else", "if_else(cond, a, b)", "삼항과 동일한 함수형"],
      ["is_nan", "is_nan(x)", "NaN 이면 1"],
    ]},
    { group: "횡단면 (그날 전 종목 기준)", items: [
      ["rank", "rank(x)", "순위 → 0~1"], ["zscore", "zscore(x)", "표준화 (평균0 표준편차1)"],
      ["winsorize", "winsorize(x, std=4)", "std 배 넘는 이상치 자르기"],
      ["normalize", "normalize(x)", "평균 0 으로 이동"], ["scale", "scale(x, scale=1)", "|합|=scale 로 정규화"],
      ["quantile", "quantile(x)", "분위수 변환 (정규/균등)"], ["scale_down", "scale_down(x)", "0~1 로 압축"],
    ]},
    { group: "시계열 (종목별 과거 d일)", items: [
      ["ts_mean", "ts_mean(x, d)", "d일 이동평균"], ["ts_sum", "ts_sum(x, d)", "d일 합"],
      ["ts_std_dev", "ts_std_dev(x, d)", "d일 표준편차"], ["ts_zscore", "ts_zscore(x, d)", "d일 z-score"],
      ["ts_rank", "ts_rank(x, d)", "최근 d일 내 순위"], ["ts_delta", "ts_delta(x, d)", "x − d일 전 x"],
      ["ts_delay", "ts_delay(x, d)", "d일 전 값"], ["ts_min", "ts_min(x, d)", "d일 최소"],
      ["ts_max", "ts_max(x, d)", "d일 최대"], ["ts_av_diff", "ts_av_diff(x, d)", "x − d일 평균"],
      ["ts_product", "ts_product(x, d)", "d일 곱"], ["ts_corr", "ts_corr(x, y, d)", "d일 상관계수"],
      ["ts_covariance", "ts_covariance(y, x, d)", "d일 공분산"],
      ["ts_decay_linear", "ts_decay_linear(x, d)", "최근일에 큰 가중치 (선형 감쇠)"],
      ["ts_scale", "ts_scale(x, d)", "최근 d일 기준 0~1"], ["ts_arg_max", "ts_arg_max(x, d)", "최댓값까지 경과일"],
      ["ts_arg_min", "ts_arg_min(x, d)", "최솟값까지 경과일"], ["ts_count_nans", "ts_count_nans(x, d)", "d일 내 NaN 개수"],
      ["ts_backfill", "ts_backfill(x, d)", "NaN 을 최근 d일 내 값으로 채움 (결측 보정)"],
      ["hump", "hump(x, hump=0.01)", "작은 변동 무시 (불필요한 거래 억제)"],
    ]},
    { group: "그룹 (섹터 등 그룹 내)", items: [
      ["group_neutralize", "group_neutralize(x, group)", "그룹 평균을 빼 중립화"],
      ["group_rank", "group_rank(x, group)", "그룹 내 순위"], ["group_zscore", "group_zscore(x, group)", "그룹 내 z-score"],
      ["group_mean", "group_mean(x, group)", "그룹 평균"], ["group_min", "group_min(x, group)", "그룹 최소"],
      ["group_max", "group_max(x, group)", "그룹 최대"], ["group_scale", "group_scale(x, group)", "그룹 내 0~1"],
    ]},
    { group: "변환", items: [
      ["bucket", "bucket(x, range='0,1,0.1')", "연속값 → 구간(버킷) 인덱스"],
      ["trade_when", "trade_when(cond, alpha, close)", "조건부 진입 / 청산"],
    ]},
  ];

  // 자동완성 풀: 데이터 필드 + 함수형 연산자(식별자만, 비교/삼항 제외)
  const variables = FIELD_GROUPS.flatMap((g) =>
    g.items.map(([name, desc]) => ({ name, type: g.group, desc })));
  const opAuto = OP_GROUPS.flatMap((g) =>
    g.items.filter(([name]) => /^[a-z_]+$/.test(name))
      .map(([name, sig, desc]) => ({ name, type: "함수 · " + g.group, desc, sig, fn: true })));
  const acItems = variables.concat(opAuto);
  const reference = { fields: FIELD_GROUPS, operators: OP_GROUPS };

  // example alphas
  const examples = [
    { label: "Short-term mean reversion", expr: "rank(-returns)" },
    { label: "Quality — high ROE", expr: "rank(roe)" },
    { label: "Value — low P/E", expr: "rank(-pe)" },
    { label: "FCF yield", expr: "rank(fcf / cap)" },
    { label: "Positive-day count (삼항)", expr: "ts_sum(returns > 0 ? 1 : 0, 250)" },
    { label: "Cap-bucket asset value", expr: "group_neutralize(\n  winsorize(ts_backfill((ppent + cash) / cap, 63), std=4),\n  bucket(rank(cap), range='0,1,0.1')\n)" },
  ];

  window.AB_DATA = {
    monthLabels, pnlScaled, isSummary, yearRows, indices, account,
    acctHist, dailyPerf, longs, shorts, buyOrders, sellOrders,
    botLogs, news, aiSummary, variables, acItems, reference, examples,
  };
})();
