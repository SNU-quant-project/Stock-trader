# Alpaca 계좌 정보 조회 — 연결 확인용

import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

# 1. .env 파일에서 환경변수 로드
load_dotenv()

# 2. 환경변수에서 API 키 두 개를 꺼냄
api_key = os.getenv("ALPACA_API_KEY")
secret_key = os.getenv("ALPACA_SECRET_KEY")

# 3. TradingClient 생성
#    paper=True 가 핵심 — "모의계좌(paper)에 연결" 이라는 뜻
client = TradingClient(api_key, secret_key, paper=True)

# 4. 계좌 정보 조회
account = client.get_account()

# 5. 결과 출력
print(f"계좌 상태   : {account.status}")
print(f"현금 잔고   : ${account.cash}")
print(f"총 자산     : ${account.equity}")
print(f"매수 가능   : ${account.buying_power}")