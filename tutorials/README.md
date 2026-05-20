# Tutorials

단계별 실행 가이드.

루트 [README.md](../README.md) 의 환경 설정 (계정 생성, API 키, 가상환경, `.env`) 을 먼저 완료해야 한다.

## 실행 전 체크리스트

- [ ] `Stock-trader/.env` 파일에 API 키 두 개가 들어있음
- [ ] 가상환경이 활성화된 상태 (프롬프트 앞에 `(venv)` 표시)
- [ ] 현재 작업 디렉토리가 `Stock-trader/` 루트 (즉 `tutorials/` 의 상위)
- [ ] `pip list` 로 `alpaca-py`, `pandas`, `matplotlib` 등이 보임

모든 스크립트는 **루트 디렉토리에서** 실행한다:

**Windows:**
```powershell
python tutorials\01_check_account.py
```

**macOS:**
```bash
python tutorials/01_check_account.py
```

VSCode 의 ▶ 버튼으로 실행해도 된다. 단, VSCode 좌하단의 Python 인터프리터가 `venv` 안의 것으로 선택돼 있어야 한다.

---

# Step 01. 계좌 연결 확인

**파일**: `tutorials/01_check_account.py`

**목적**: `.env` 의 API 키가 유효한지, Alpaca 서버에 연결되는지 확인.

**실행**:
```powershell
python tutorials\01_check_account.py   # Windows
python tutorials/01_check_account.py   # macOS
```

**기대 출력**:
```
계좌 상태   : AccountStatus.ACTIVE
현금 잔고   : $100000
총 자산     : $100000
매수 가능   : $200000
```

`AccountStatus.ACTIVE` 와 가상 자금 `$100,000` 이 보이면 성공.

**자주 발생하는 에러**:
- `401 Unauthorized` → API 키가 틀렸거나 `.env` 가 안 읽힘. `.env` 위치와 내용 확인
- `ModuleNotFoundError: alpaca` → 가상환경 활성화 안 됨. 프롬프트의 `(venv)` 확인

---

# Step 02. 첫 주문 넣어보기

**파일**: `tutorials/02_first_order.py`

**목적**: AAPL 1주를 시장가로 매수 주문. 주문 API 사용법 익히기.

**실행 전 주의**: 미국 정규장이 닫혀있는 시간 (한국 기준 새벽 6시 ~ 밤 11:30) 에 실행하면 주문은 받아들여지지만 `accepted` 상태로 대기하다가 다음 장 개장 시 체결된다. 이건 정상.

**실행**:
```powershell
python tutorials\02_first_order.py
```

**기대 출력**:
```
주문 ID  : (UUID 문자열)
종목     : AAPL
수량     : 1
방향     : OrderSide.BUY
주문 유형: OrderType.MARKET
상태     : OrderStatus.ACCEPTED
```

장 마감 후 실행 시 상태가 `ACCEPTED` 또는 `PENDING_NEW`, 장 중 실행 시 `FILLED`.

**확인**: https://app.alpaca.markets/paper/dashboard/overview → 좌측 **Orders** 탭에서 방금 넣은 주문 확인 가능.

---

# Step 03. 과거 데이터 받아오기

**파일**: `tutorials/03_fetch_data.py`

**목적**: AAPL 1년치 일봉 데이터를 받아 pandas DataFrame 으로 출력.

**실행**:
```powershell
python tutorials\03_fetch_data.py
```

**기대 출력**:
```
받은 데이터 행 수: 약 250

처음 5행:
                              open    high     low   close      volume  ...
symbol timestamp
AAPL   2025-XX-XX ...

마지막 5행:
AAPL   2026-XX-XX ...
```

거래일 약 250개. 주말과 미국 휴장일은 제외되어 365 가 아닌 252 거래일 ± α.

**자주 발생하는 에러**:
- `403 Forbidden: subscription does not permit querying recent SIP data` → 코드의 `end` 시각이 현재로부터 15분 이내. 코드 안의 시간 계산이 잘못된 경우 발생. 정상 코드라면 발생 안 함

---

# Step 04. S&P 500 종목 멤버십 데이터 받기

**파일**: `tutorials/04_fetch_sp500_membership.py`

**목적**: 위키피디아에서 현재 S&P 500 종목 리스트와 과거 변경 이력을 받아 CSV 두 개로 저장.

**실행 전 준비**: `Stock-trader/data/` 폴더가 있어야 함. 없으면 생성:

**Windows:**
```powershell
mkdir data
```

**macOS:**
```bash
mkdir data
```

**실행**:
```powershell
python tutorials\04_fetch_sp500_membership.py
```

**기대 출력**:
```
위키피디아 페이지 다운로드 중...
다운로드 완료 (약 80만 글자)
HTML에서 표 추출 중...
총 3개의 표를 발견
[Table 0] 현재 S&P 500 종목
행 수: 약 503
...
[Table 1] 종목 변경 이력
행 수: 약 395
...
저장 완료:
  - data/sp500_current.csv
  - data/sp500_changes.csv
```

`data/` 폴더에 두 CSV 파일이 생성된다.

**자주 발생하는 에러**:
- `HTTPError: 403 Forbidden` → User-Agent 헤더 누락. 코드 안의 `headers = {"User-Agent": ...}` 부분 확인
- `ModuleNotFoundError: lxml` → `pip install lxml` 실행 후 재시도

---

# Step 05. 1년치 S&P 500 Panel Data 받기

**파일**: `tutorials/05_fetch_panel_data.py`

**목적**: Step 04 에서 받은 멤버십 데이터를 이용해 "지난 1년간 한 번이라도 S&P 500 이었던 종목" 의 일봉을 모두 받아 parquet 파일로 저장.

**전제**: Step 04 가 먼저 실행되어 `data/sp500_current.csv` 와 `data/sp500_changes.csv` 가 있어야 한다.

**실행**:
```powershell
python tutorials\05_fetch_panel_data.py
```

**소요 시간**: 약 30초 ~ 1분. 50종목씩 11개 배치로 받는다.

**기대 출력**:
```
[1/3] ... 기간 유니버스 구성 중...
      유니버스 크기: 약 524개 종목
[2/3] Alpaca 에서 일봉 데이터 다운로드 중...
  배치 1/11 (A ~ AXON) 요청 중... OK (약 12,000행)
  ...
  배치 11/11 (...) 요청 중... OK
[3/3] 저장 중...
      파일: data/sp500_panel.parquet
완료
전체 행 수      : 약 130,000
고유 종목 수    : 약 524
날짜 범위       : 2025-XX-XX ~ 2026-XX-XX
누락 종목 수    : 0
```

`data/sp500_panel.parquet` 가 생성된다 (약 5MB).

**자주 발생하는 에러**:
- `FileNotFoundError: data/sp500_current.csv` → Step 04 를 먼저 실행
- `ModuleNotFoundError: lib` → 현재 디렉토리가 루트가 아님. `cd Stock-trader` 로 이동 후 재실행

---

# Step 06. 알파 백테스팅

**파일**: `tutorials/06_backtest_meanrev.py`

**목적**: 단순한 단기 평균회귀 알파를 1년치 panel 에 적용해 성과 측정.

**알파 명세**:
- Alpha: `rank(-returns)` — 어제 많이 떨어진 종목을 long, 많이 오른 종목을 short
- Neutralization: GICS Sector (11개 그룹)
- Decay: 4일 가중평균 (D-1:D-2:D-3:D-4 = 4:3:2:1)
- Delay: 1 (D-1 종가 데이터로 알파 계산 → D 시가에 진입)
- 체결 모델: D 시가 진입, D+1 시가 청산
- 포지션: 매일 리밸런싱, 차이만 거래

**전제**: Step 04, 05 가 먼저 실행되어 `data/sp500_current.csv`, `data/sp500_panel.parquet` 가 있어야 한다.

**실행 전 준비**: `results/` 폴더 생성:
```powershell
mkdir results
```

**실행**:
```powershell
python tutorials\06_backtest_meanrev.py
```

**기대 출력**:
```
[1/5] 데이터 로드 중...
  Sector 정보 없는 종목 수: 약 20개
  Panel shape: (250, 524)
  날짜 범위: 2025-XX-XX ~ 2026-XX-XX
[2/5] 알파 계산 중...
  알파 절댓값 합 평균: 약 1.0
  알파 단순 합 평균:   약 0
[3/5] Decay 적용 중...
  포지션 절댓값 합 평균: 약 1.0
[4/5] 백테스팅 실행 중...
[5/5] 결과:
  거래일 수      : 250일
  총 수익률      : X.XX%
  연환산 수익률  : X.XX%
  Sharpe         : X.XXX
  MDD            : X.XX%
  승률           : XX.XX%
  평균 회전율    : XX.XX%/일
  차트 저장: results/backtest_result.png
```

`results/backtest_result.png` 에 자산 곡선과 drawdown 차트가 저장된다.

**검증 포인트**:
- 알파 절댓값 합 ≈ 1.0 (정규화 OK)
- 알파 단순 합 ≈ 0 (sector neutral OK)
- 포지션 절댓값 합 ≈ 1.0 (decay 후 재정규화 OK)

위 값들이 크게 어긋나면 데이터/코드에 문제가 있다.

---

# 작업 재개 시 빠른 실행 순서

처음 한 번 환경 셋업 끝났으면, 다음부터는:

**Windows:**
```powershell
cd C:\Users\사용자명\Desktop\Stock-trader
.\venv\Scripts\Activate.ps1

# 데이터가 이미 있으면 04, 05 는 생략 가능
python tutorials\06_backtest_meanrev.py
```

**macOS:**
```bash
cd ~/Desktop/Stock-trader
source venv/bin/activate

python tutorials/06_backtest_meanrev.py
```

---

# 다음 단계

이 튜토리얼은 인프라 구축까지가 목표. 이후로 가능한 방향:

1. **알파 개선**: `rank(-returns)` 대신 다른 알파 시도 (예: `-ts_zscore(cap/equity, 5)`). Truncation 추가.
2. **유니버스 확장**: S&P 500 → TOP 3000 종목 (거래량 기준)
3. **페이퍼 트레이딩 자동화**: 매일 종가 직후 알파 계산 → Alpaca 페이퍼 계좌에 자동 주문
4. **Multi-day holding**: 일별 리밸런싱 대신 주별/월별

각 방향은 새 브랜치 + PR 로 진행. 자세한 작업 흐름은 루트 README 참조.
