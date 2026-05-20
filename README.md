# Stock-trader

미국 주식(S&P 500) 대상 알고리즘 트레이딩 백테스팅 및 페이퍼 트레이딩 프로젝트.

SNU Quant Project 스터디용.

## 무엇을 하는가

- Alpaca 페이퍼 트레이딩 계좌로 미국 주식 자동매매 실습
- S&P 500 시점별 멤버십 데이터 구축 (Survivorship-bias-free)
- 1년치 panel data 다운로드 및 cross-sectional 알파 백테스팅
- WorldQuant Brain 스타일 알파 (rank, decay, sector neutralize) 구현

## 시작하기

이 README 는 환경 설정까지만 다룬다. 실제 코드 실행은 [tutorials/README.md](./tutorials/README.md) 참조.

순서:
1. Alpaca 계정 만들기 + API 키 발급
2. 로컬 환경 설정 (가상환경, 라이브러리 설치)
3. API 키 등록
4. `tutorials/` 의 단계별 스크립트 실행

---

# 1. Alpaca 계정 만들기

## 1.1 회원가입

1. https://alpaca.markets/ 접속
2. 우상단 **Sign up** 클릭
3. **Trading API** 선택 (Broker API 아님)
4. 이메일, 비밀번호 입력하고 가입
5. 이메일 인증

가입 후 대시보드 진입 시 좌상단에 **Paper** 표시가 보여야 한다.

## 1.2 API 키 발급

1. 대시보드 우측 사이드바 **API Keys** 메뉴 클릭
2. **Generate New Key** 버튼 클릭
3. 화면에 표시된 두 값을 메모장에 임시 저장:
   - `API Key ID` (예: `PKABC...`)
   - `Secret Key` (예: `xyz123...`)

**주의**: Secret Key는 이 화면 한 번만 표시된다. 닫으면 다시 못 본다.

---

# 2. 로컬 환경 설정 (Windows)

> macOS 사용자는 [3. 로컬 환경 설정 (macOS)](#3-로컬-환경-설정-macos) 으로.

## 2.1 사전 준비

다음이 설치되어 있어야 한다:
- Python 3.10 이상 (https://www.python.org/downloads/)
- Git (https://git-scm.com/download/win)
- VSCode (https://code.visualstudio.com/) — 권장

PowerShell 에서 확인:
```powershell
python --version
git --version
```

둘 다 버전이 출력되면 OK.

## 2.2 레포 클론

```powershell
cd C:\Users\사용자명\Desktop
git clone https://github.com/SNU-quant-project/Stock-trader.git
cd Stock-trader
```

## 2.3 가상환경 생성

```powershell
python -m venv venv
```

폴더 안에 `venv` 디렉토리가 생긴다.

**문제 발생 시**: 만약 `venv\Scripts\` 가 아니라 `venv\bin\` 폴더가 생긴다면, 시스템에 MSYS2/Git Bash 의 Python 이 우선 잡힌 경우다. 다음 명령으로 PATH 확인:

```powershell
where.exe python
```

`C:\Users\...\AppData\Local\Programs\Python\Python312\python.exe` 같은 Windows 네이티브 Python 경로를 찾아서 직접 지정:

```powershell
Remove-Item -Recurse -Force venv
C:\Users\사용자명\AppData\Local\Programs\Python\Python312\python.exe -m venv venv
```

## 2.4 가상환경 활성화

```powershell
.\venv\Scripts\Activate.ps1
```

프롬프트 앞에 `(venv)` 가 붙으면 성공.

**스크립트 실행 차단 에러 발생 시**:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
실행 후 다시 활성화 시도.

## 2.5 라이브러리 설치

```powershell
pip install -r requirements.txt
```

1~2분 소요. 완료 후 확인:
```powershell
pip list
```

`alpaca-py`, `pandas`, `matplotlib` 등이 보이면 OK.

## 2.6 API 키 등록

`Stock-trader/` 루트에 `.env` 파일 생성.

> VSCode에서 새 파일 만들 때 파일명을 정확히 `.env` 로 입력. 메모장 사용 시 파일 형식을 "모든 파일" 로 바꾸고 `.env` 로 저장.

`.env` 내용:
```
ALPACA_API_KEY=발급받은_API_Key_ID
ALPACA_SECRET_KEY=발급받은_Secret_Key
```

규칙:
- `=` 양옆에 공백 없음
- 값을 따옴표로 감싸지 않음
- 값 끝에 공백 없음

저장 후 PowerShell 에서 확인:
```powershell
cat .env
```

두 줄이 정상적으로 보이면 OK.

설정 완료. [tutorials/README.md](./tutorials/README.md) 로 이동.

---

# 3. 로컬 환경 설정 (macOS)

## 3.1 사전 준비

다음이 설치되어 있어야 한다:
- Python 3.10 이상
- Git
- VSCode (권장)

터미널에서 확인:
```bash
python3 --version
git --version
```

Python 이 없으면 https://www.python.org/downloads/ 에서 설치하거나 Homebrew 사용:
```bash
brew install python
```

## 3.2 레포 클론

```bash
cd ~/Desktop
git clone https://github.com/SNU-quant-project/Stock-trader.git
cd Stock-trader
```

## 3.3 가상환경 생성

```bash
python3 -m venv venv
```

폴더 안에 `venv` 디렉토리가 생긴다.

## 3.4 가상환경 활성화

```bash
source venv/bin/activate
```

프롬프트 앞에 `(venv)` 가 붙으면 성공.

## 3.5 라이브러리 설치

```bash
pip install -r requirements.txt
```

1~2분 소요. 완료 후 확인:
```bash
pip list
```

`alpaca-py`, `pandas`, `matplotlib` 등이 보이면 OK.

## 3.6 API 키 등록

`Stock-trader/` 루트에 `.env` 파일 생성.

터미널에서:
```bash
touch .env
open -e .env  # 또는 code .env
```

`.env` 내용:
```
ALPACA_API_KEY=발급받은_API_Key_ID
ALPACA_SECRET_KEY=발급받은_Secret_Key
```

규칙:
- `=` 양옆에 공백 없음
- 값을 따옴표로 감싸지 않음
- 값 끝에 공백 없음

저장 후 확인:
```bash
cat .env
```

두 줄이 정상적으로 보이면 OK.

설정 완료. [tutorials/README.md](./tutorials/README.md) 로 이동.

---

# 4. 다음에 작업 재개할 때

새 터미널 창을 열 때마다 가상환경을 다시 활성화해야 한다.

**Windows:**
```powershell
cd C:\Users\사용자명\Desktop\Stock-trader
.\venv\Scripts\Activate.ps1
```

**macOS:**
```bash
cd ~/Desktop/Stock-trader
source venv/bin/activate
```

`(venv)` 표시가 뜨면 작업 가능 상태.

VSCode 에서 작업할 경우, 좌하단의 Python 인터프리터 선택에서 `./venv/Scripts/python.exe` (Windows) 또는 `./venv/bin/python` (macOS) 를 선택해두면 ▶ 버튼으로 바로 실행 가능.

---

# 폴더 구조

```
Stock-trader/
├── README.md                    이 파일
├── requirements.txt
├── .env                         (gitignore, 직접 생성)
├── .gitignore
├── venv/                        (gitignore)
├── data/                        (gitignore, 스크립트로 자동 생성)
│   ├── sp500_current.csv
│   ├── sp500_changes.csv
│   └── sp500_panel.parquet
├── lib/
│   └── sp500_universe.py        재사용 모듈
├── tutorials/
│   ├── README.md                단계별 실행 가이드
│   ├── 01_check_account.py
│   ├── 02_first_order.py
│   ├── 03_fetch_data.py
│   ├── 04_fetch_sp500_membership.py
│   ├── 05_fetch_panel_data.py
│   └── 06_backtest_meanrev.py
└── results/                     (gitignore)
    └── backtest_result.png
```
