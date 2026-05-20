# 첫 주문 — AAPL 1주를 시장가로 매수

import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# 1. 환경변수 로드 및 클라이언트 생성 (이전과 동일)
load_dotenv()
client = TradingClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
    paper=True,
)

# 2. 주문 요청 객체 생성
#    - symbol: 종목 코드 (Apple은 'AAPL')
#    - qty: 수량 (1주)
#    - side: 매수(BUY) vs 매도(SELL)
#    - time_in_force: 주문 유효 기간. DAY = 당일 장 마감까지만 유효
order_request = MarketOrderRequest(
    symbol="AAPL",
    qty=1,
    side=OrderSide.BUY,
    time_in_force=TimeInForce.DAY,
)

# 3. 주문 제출 — Alpaca 서버로 실제 요청을 보내는 부분
order = client.submit_order(order_request)

# 4. 결과 출력
print(f"주문 ID  : {order.id}")
print(f"종목     : {order.symbol}")
print(f"수량     : {order.qty}")
print(f"방향     : {order.side}")
print(f"주문 유형: {order.order_type}")
print(f"상태     : {order.status}")