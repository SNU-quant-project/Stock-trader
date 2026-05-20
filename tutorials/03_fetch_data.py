# Alpaca에서 AAPL 일봉 데이터 1년치 받아오기

import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# 1. 환경변수 로드
load_dotenv()

# 2. 데이터 전용 클라이언트 생성
#    TradingClient랑 다른 클래스인 점에 주의!
#    paper 옵션 없음 — 데이터 조회는 paper/live 구분 안 함
client = StockHistoricalDataClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
)

# 3. 요청 객체 생성
#    어떤 종목을, 어떤 시간 단위로, 언제부터 언제까지 받을지 정의

# UTC 기준 "오늘 0시" — 즉 어제 미국 장 마감 이후 시점
today_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

request = StockBarsRequest(
    symbol_or_symbols="AAPL",
    timeframe=TimeFrame.Day,
    start=today_utc - timedelta(days=365),
    end=today_utc,
)

# 4. 실제 데이터 요청
bars = client.get_stock_bars(request)

# 5. pandas DataFrame으로 변환
df = bars.df

# 6. 결과 확인
print(f"받은 데이터 행 수: {len(df)}")
print()
print("처음 5행:")
print(df.head())
print()
print("마지막 5행:")
print(df.tail())