# 클라우드 상시 호스팅 — 작업 인계 프롬프트

> **사용법:** 새 대화를 시작할 때 이 문서 내용을 그대로 붙여넣거나,
> "이 프로젝트의 `plans/cloud_hosting_handoff.md` 를 보고 진행해줘" 라고 하면 됩니다.

---

## 한 줄 요약

이미 완성·검증된 `live_trade.py`(HMM 알파 → Alpaca 페이퍼 자동매매)를 클라우드 VM에
배포해서, **내 컴퓨터를 꺼도** 미국 정규장 중 30분마다 자동으로 돌게 한다.

## 배경 (프로젝트)

- 프로젝트: **SNU Quant_Stock** — 코인용 HMM 국면분류 알파를 미국 주식으로 이식한
  알고리즘 트레이딩 프로젝트. 작업 폴더 `~/Desktop/Stock-trader`.
- 자세한 맥락은 메모리(`project_snu_quant_stock` 등)와 `plans/` 폴더의
  phase 보고서를 참고할 것.
- **이미 완성된 라이브 트레이딩 — `live_trade.py`:**
  - 7종목(AAPL·AMZN·GOOGL·META·MSFT·NVDA·TSLA) 등가중, Alpaca 페이퍼 계좌.
  - `python live_trade.py --loop --execute` → 미국 정규장 중 30분마다 자동으로
    시그널 계산 + 주문 제출.
  - `--once`(1회) / `--loop`(30분 반복), `--execute`(실주문) / 미지정 시 dry-run.
  - 매 사이클 결과는 `logs/live_log.csv` 에 기록됨.
  - 로컬(맥)에서 `--once --execute` 까지 실제 체결 검증 완료.
- **한계:** `--loop` 는 사용자 맥에서 도는 프로세스 → 맥이 꺼지거나 잠자면 멈춤.
  한국 시간 기준 미국 장이 밤~새벽이라 매일 밤 맥을 켜둬야 하는 불편.

## 목표

`live_trade.py --loop --execute` 가 사용자 컴퓨터와 무관하게 클라우드에서
**24/5(미국 장중) 상시 작동**하도록 배포한다.

## 결정·구현할 항목

1. **클라우드 제공자 선택** — 무료/저가 위주로 사용자와 상의. 후보:
   - Oracle Cloud Always Free (ARM 인스턴스, 사양이 후해 RAM 여유 — 유력 후보)
   - AWS EC2 프리티어 (t2/t3.micro, RAM 1GB — 빠듯할 수 있음)
   - GCP e2-micro 무료 / 저가 VPS(DigitalOcean 등 월 $4~6)
   - 참고: 시작 시 7종목 HMM 학습에 CPU·RAM을 좀 쓰므로 **RAM 2GB 이상 권장**.
2. **VM 환경 구성** — Ubuntu 권장, Python 3.10+, 가상환경, `pip install -r requirements.txt`.
3. **코드·데이터 전송** — 아래 "전송 시 주의" 참고.
4. **상시 실행** — `systemd` 서비스로 등록 → 부팅 시 자동 시작 + 프로세스가 죽으면
   자동 재시작 (`nohup` 보다 견고). 실행 명령은 `python live_trade.py --loop --execute`.
5. **로그 회수** — `logs/live_log.csv` 와 stdout 로그를 사용자가 주기적으로
   확인할 방법(scp 등).
6. **(검토) 데이터 신선도** — `data/30min/*.parquet` 은 특정 날짜까지의 과거 데이터.
   `live_trade.py` 가 매 사이클 그 이후 구간을 Alpaca 에서 받아 채우지만, 갭이 계속
   커지면 비효율 → VM에서 주기적으로 parquet 을 갱신할지 검토.

## 전송 시 주의 (중요)

- **GitHub 동기화 상태부터 확인.** 레포: `github.com/SNU-quant-project/Stock-trader`.
  로컬의 최신 코드(`live_trade.py`, `strategy/` 등)가 push 안 돼 있을 가능성이 높음
  → push 후 VM에서 clone 하거나, 프로젝트 폴더 전체를 직접 전송(scp/rsync).
- **데이터·키 파일은 git에 없음.** `.gitignore` 가 `*.parquet`, `.env` 를 제외함.
  - `data/30min/*.parquet` (라이브에 필수) → 별도로 VM에 전송.
  - `.env` (`ALPACA_API_KEY`/`ALPACA_SECRET_KEY`) → VM에 직접 생성. **민감정보 주의.**
- 가장 간단한 방법: **프로젝트 폴더 전체를 VM에 올리는 것**(코드 + `data/30min/` +
  `.env`). `venv/` 는 제외하고 VM에서 새로 생성.

## `live_trade.py` 실행 요건

- 라이브러리: `requirements.txt` 전체 설치(alpaca-py, python-dotenv, pandas, numpy,
  pyarrow, hmmlearn, scikit-learn, joblib 등).
- 필요 파일: `.env`, `data/30min/` 의 7종목 parquet, `strategy/` 패키지.
  (`backtester/` 는 라이브에 불필요하나 폴더째 올리면 신경 안 써도 됨)
- 서버 타임존 무관 — 코드가 `America/New_York` 을 명시적으로 쓰고 Alpaca
  `get_clock()` 으로 장 개폐를 판단함.

## 운영 시 참고

- 사용자(Minjong)는 코딩 초보 — 단계별로 설명하고, 시스템/코드 수정 전 확인.
- 페이퍼 계좌라 실제 손실 위험은 없지만 API 키는 민감정보.
- 첫 배포 후 VM에서 `python live_trade.py --once`(dry-run)로 한 번 검증한 뒤
  `--loop --execute` 를 systemd 에 등록할 것.
