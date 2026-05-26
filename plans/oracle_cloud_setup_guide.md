# Oracle Cloud Always Free — VM 배포 가이드

> 코딩 초보자 기준으로 단계별로 설명합니다.
> 터미널 명령은 **맥 터미널 앱**에서 실행하세요.

---

## 1단계 — Oracle Cloud 계정 생성

1. https://www.oracle.com/cloud/free/ 접속 → **Start for free** 클릭
2. 이메일·국가 등 입력 후 가입
   - 신용카드 정보를 요구하지만 **Always Free 한도 내에서는 절대 청구되지 않음**
   - 카드는 본인 확인용이에요 (처음에 $1 임시 승인 후 바로 취소됨)
3. 홈 리전(Home Region) 선택 — **한 번 고르면 바꿀 수 없음**
   - 권장: `Japan East (Tokyo)` — 한국에서 가장 가깝고 안정적

---

## 2단계 — VM 인스턴스 생성

1. Oracle Cloud 콘솔 로그인 → 좌상단 메뉴 → **Compute → Instances**
2. **Create instance** 클릭
3. 설정:
   - **Name**: `stock-trader` (자유롭게)
   - **Image**: Ubuntu 22.04 (Always Free 호환)
   - **Shape**: `VM.Standard.A1.Flex` (ARM) — **Always Free**
     - OCPU: 2, Memory: 12GB (무료 한도 절반, 넉넉함)
   - **Primary VNIC**: 기본값 유지
   - **SSH keys**: 아래 참고 ↓

4. **SSH 키 생성** (중요! VM 접속에 필요):
   - 맥 터미널에서 먼저 실행:
     ```bash
     ssh-keygen -t rsa -b 4096 -f ~/.ssh/oracle_stock_trader -N ""
     cat ~/.ssh/oracle_stock_trader.pub
     ```
   - 출력된 `ssh-rsa AAAA...` 텍스트 전체를 복사
   - Oracle 콘솔에서 **Upload public key files** 대신 **Paste public keys** 선택 후 붙여넣기

5. **Create** 클릭 → 1~2분 후 인스턴스 상태가 **Running**으로 바뀜

---

## 3단계 — VM에 SSH 접속

1. Oracle 콘솔에서 인스턴스 클릭 → **Public IP address** 확인 (예: `150.xxx.xxx.xxx`)
2. 맥 터미널에서:
   ```bash
   ssh -i ~/.ssh/oracle_stock_trader ubuntu@<공인IP>
   ```
   - 처음 접속 시 "Are you sure you want to continue connecting?" → `yes` 입력
   - `ubuntu@stock-trader:~$` 프롬프트가 뜨면 접속 성공!

---

## 4단계 — VM 기본 환경 구성

VM 터미널(SSH 접속 후)에서 아래 명령을 순서대로 실행하세요:

```bash
# 패키지 업데이트
sudo apt update && sudo apt upgrade -y

# Python 3.11 + pip + venv
sudo apt install -y python3.11 python3.11-venv python3-pip git

# 프로젝트 폴더 생성
mkdir -p ~/Stock-trader && cd ~/Stock-trader

# 가상환경 생성
python3.11 -m venv venv
source venv/bin/activate
```

---

## 5단계 — 코드 다운로드 & 데이터 전송

**코드 (GitHub에서 clone):**
```bash
# VM 터미널에서
cd ~
git clone https://github.com/SNU-quant-project/Stock-trader.git
cd Stock-trader
source venv/bin/activate
pip install -r requirements.txt
```

**parquet 데이터 & .env (맥 터미널 별도 창에서):**
```bash
# 맥 터미널에서 실행 — <공인IP>를 실제 IP로 교체
VM_IP=<공인IP>

# data/30min 폴더 전송
scp -i ~/.ssh/oracle_stock_trader -r \
  ~/Desktop/Stock-trader/data/30min \
  ubuntu@$VM_IP:~/Stock-trader/data/

# .env 파일 전송
scp -i ~/.ssh/oracle_stock_trader \
  ~/Desktop/Stock-trader/.env \
  ubuntu@$VM_IP:~/Stock-trader/.env

# models 폴더 전송 (HMM 모델 파일)
scp -i ~/.ssh/oracle_stock_trader -r \
  ~/Desktop/Stock-trader/models \
  ubuntu@$VM_IP:~/Stock-trader/
```

---

## 6단계 — 동작 테스트 (dry-run)

VM 터미널에서:
```bash
cd ~/Stock-trader
source venv/bin/activate

# 1회 dry-run (실주문 없음, 오류 없으면 OK)
python live_trade.py --once

# 정상이면 실주문 1회 테스트
python live_trade.py --once --execute
```

로그가 `Signal: LONG` 등 정상적으로 찍히면 다음 단계로!

---

## 7단계 — systemd 서비스 등록 (상시 자동 실행)

VM 터미널에서:
```bash
# 서비스 파일 복사 (setup/ 폴더에 미리 준비돼 있음)
sudo cp ~/Stock-trader/setup/live_trade.service /etc/systemd/system/

# systemd에 등록 & 시작
sudo systemctl daemon-reload
sudo systemctl enable live_trade
sudo systemctl start live_trade

# 상태 확인
sudo systemctl status live_trade
```

`Active: active (running)` 이 뜨면 배포 완료! 🎉

---

## 운영 중 유용한 명령어

```bash
# 실시간 로그 보기
sudo journalctl -u live_trade -f

# 서비스 재시작
sudo systemctl restart live_trade

# 서비스 중지
sudo systemctl stop live_trade

# 로그 파일 확인 (맥 터미널에서)
scp -i ~/.ssh/oracle_stock_trader \
  ubuntu@<공인IP>:~/Stock-trader/logs/live_log.csv \
  ~/Desktop/Stock-trader/logs/live_log_vm.csv
```
