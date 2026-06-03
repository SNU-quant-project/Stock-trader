# 인수인계 (HANDOFF) — 코인 트레이딩으로 전환하려는 분께

> 이 문서는 **사람과 LLM(Claude Code 등) 둘 다** 읽으라고 만든 거예요.
> 코드를 깊게 몰라도 됩니다. **이 repo를 Fork 한 뒤, Claude Code/Cursor로 열고 LLM에게 시키면** 됩니다.

---

## 0. 이게 뭔가요? (한 줄 요약)

미국 주식(S&P 500) **알파 리서치 + 백테스트 + Alpaca 페이퍼(모의) 자동매매 + 웹 대시보드**를 한 줄기로 묶은 플랫폼입니다.
WorldQuant **BRAIN 스타일**(수식으로 알파를 만들고 → 백테스트 → 실거래)을 공개 데이터로 직접 구현했습니다.

목표: 이 구조를 **그대로 코인 트레이딩으로 바꾸는 것**. (변환은 받는 분이 LLM과 진행)

---

## 1. 시작하기 (이 순서대로)

1. **이 repo를 Fork** — GitHub 우측 상단 **`Fork`** 버튼 → 본인 계정에 복사본이 생깁니다.
   (원본 stock 프로젝트는 안 건드리고, 본인 fork에서 코인용으로 마음껏 고치면 됩니다.)
2. 본인 fork를 clone:
   ```bash
   git clone https://github.com/<본인-GitHub-아이디>/Stock-trader.git
   cd Stock-trader
   ```
3. 가상환경(권장) + 패키지 설치:
   ```bash
   python -m venv venv
   # Windows: venv\Scripts\activate   |  Mac/Linux: source venv/bin/activate
   pip install -r requirements.txt
   ```
4. **`.env` 파일을 새로 만들고** 본인 API 키 입력 (원작자 키는 안 들어있습니다):
   ```
   ALPACA_API_KEY=본인_키
   ALPACA_SECRET_KEY=본인_시크릿
   ```
   - Alpaca 무료 계정: https://alpaca.markets → Paper Trading 키 발급. **Alpaca 는 코인(BTC·ETH 등)도 지원**합니다.
5. **Claude Code / Cursor 로 이 폴더를 열고** LLM에게 지시 (아래 6번 프롬프트 참고).

> 데이터 파일(.csv/.parquet)은 repo에 없습니다 — 스크립트로 자동 생성됩니다. 코인은 어차피 새 수집 코드가 필요하니 신경 안 써도 됩니다.

---

## 2. 폴더 구조 지도 (LLM용)

```
lib/              # 핵심 엔진 (대부분 코인에 재사용 가능)
  alpha_eval.py     - 알파 수식 평가기 (rank, ts_*, group_neutralize, neutralize/decay/truncation, |w|=1 정규화)
  backtest.py       - 백테스트 (D→D+1 수익, Sharpe·Fitness·Turnover 등 지표)
  operators.py      - BRAIN 스타일 연산자 모음
  sp500_universe.py - S&P500 편입/방출 시점 재구성  ← 코인 리스트로 교체 대상
tutorials/        # 데이터 수집 스크립트 (번호순 실행)
  04_fetch_sp500_membership.py - S&P500 구성종목(위키)   ← 코인 리스트로 교체
  05_fetch_panel_data.py       - 가격 일봉(Alpaca)        ← 코인 가격으로 교체
  07/09_fetch_fundamentals*.py - 재무(yfinance/SEC EDGAR) ← 코인엔 없음, 삭제
  08_fetch_sectors.py          - 섹터(GICS)               ← 코인 카테고리 or 삭제
bot/
  run_alpha.py      - 매일 실행: 알파 계산 → 주문 제출 (Alpaca)  ← 코인 주문으로
  alpha_config.json - 현재 알파 수식 + 세팅
server/
  api.py            - FastAPI 백엔드 (/api/backtest, /api/data, /api/pnl …)
web/                # 프론트(React, 빌드 불필요) — 거의 그대로 재사용
README.md, tutorials/README.md  # 추가 설명
```

데이터 흐름: **데이터 수집 → 시점정합(PIT) → 알파 평가 → 백테스트/실거래 → 웹 표시**

---

## 3. 주식 → 코인 전환 시 바꿀 핵심 포인트 (LLM이 참고할 로드맵)

| 영역 | 지금(주식) | 코인으로 |
|---|---|---|
| 가격 데이터 | Alpaca `StockHistoricalDataClient` (`05_...py`) | `CryptoHistoricalDataClient` 또는 거래소 API |
| 유니버스 | S&P500 멤버십 (`sp500_universe.py`, `data/sp500_*.csv`) | **코인 리스트**(예: 시총 상위 N개). PIT 편입/방출 로직 단순화 가능 |
| 펀더멘털 | SEC EDGAR/yfinance (`07`,`09`), `cap·pe·pb·roe` 등 | **없음 → 제거.** 가격·거래량 기반 알파만 유지 |
| 섹터 | GICS 11섹터 (`08_...py`) | 코인 카테고리(L1/DeFi/밈) 옵션 또는 제거 |
| 시장 시간 | 개장/마감, 분할(split) 보정 | **24/7 → 개장/마감·split 로직 제거**(`server/api.py`, `05`) |
| 주문 실행 | Alpaca 주식 주문 (`bot/run_alpha.py`) | 코인 주문 (Alpaca 크립토는 거의 그대로, 다른 거래소면 SDK 교체) |
| 알파/백테스트 | `alpha_eval.py`, `backtest.py`, `operators.py` | **가격 기반은 거의 그대로 재사용**. 펀더멘털 필드 참조만 제거 |
| 웹 UI | `web/`, `server/api.py` | 거의 그대로. 종목명·링크만 코인용으로 |

요약: **가격 기반 알파 엔진·백테스트·웹은 재사용**, **펀더멘털·시장시간·유니버스·데이터소스만 코인용으로 교체**하면 됩니다.

---

## 4. LLM에게 줄 첫 지시 (그대로 복붙)

```
이 repo는 미국 주식(S&P500) 알파 리서치 + Alpaca 페이퍼 트레이딩 플랫폼이야.
HANDOFF.md를 먼저 읽고 전체 구조를 파악해줘.

이걸 [Alpaca 크립토 / 업비트 / 바이낸스] 기반 코인 트레이딩으로 바꾸고 싶어.
HANDOFF.md의 "주식→코인 전환 포인트" 표를 로드맵 삼아서:
1) 먼저 전체 변환 계획을 단계별로 세우고
2) 데이터 수집(코인 가격)부터 한 단계씩 바꿔줘.
펀더멘털 관련 코드(07/09 fetch, cap·pe·roe 등)는 제거해도 돼.
나는 코드를 잘 모르니 각 단계마다 뭘 왜 바꾸는지 짧게 설명해줘.
```

> 거래소를 아직 못 정했으면, 먼저 LLM에게 "Alpaca 크립토 / 업비트 / 바이낸스 중 뭐가 제일 적게 고쳐도 되는지" 물어보세요. (지금 코드가 전부 alpaca-py 기반이라 **Alpaca 크립토가 가장 손이 적게 갑니다.**)

---

## 5. 참고
- 먼저 **로컬에서** 데이터 수집 → 백테스트가 도는지 확인한 뒤, 실거래/배포는 나중에 해도 됩니다.
- 실서버 배포(EC2 등)는 선택 사항 — 로컬에서 충분히 개발/테스트 가능합니다.
- 막히면 LLM에게 에러 메시지를 그대로 붙여넣고 물어보면 됩니다.
