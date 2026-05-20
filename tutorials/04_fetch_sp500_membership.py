# S&P 500 현재 종목 + 변경 이력을 위키피디아에서 받아 CSV로 저장

import io
import requests
import pandas as pd

# 1. 위키피디아 페이지를 브라우저인 척 다운로드
url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}

print("위키피디아 페이지 다운로드 중...")
response = requests.get(url, headers=headers)
response.raise_for_status()  # 200 OK가 아니면 에러 발생
print(f"다운로드 완료 ({len(response.text):,} 글자)")

# 2. HTML에서 모든 표 추출
print("HTML에서 표 추출 중...")
tables = pd.read_html(io.StringIO(response.text))
print(f"총 {len(tables)}개의 표를 발견")

# 3. 첫 번째 표 = 현재 S&P 500 종목 리스트
current_constituents = tables[0]
print()
print("=" * 60)
print("[Table 0] 현재 S&P 500 종목")
print("=" * 60)
print(f"행 수: {len(current_constituents)}")
print(f"컬럼: {list(current_constituents.columns)}")
print()
print("처음 5행:")
print(current_constituents.head())

# 4. 두 번째 표 = 변경 이력
changes = tables[1]
print()
print("=" * 60)
print("[Table 1] 종목 변경 이력")
print("=" * 60)
print(f"행 수: {len(changes)}")
print(f"컬럼: {list(changes.columns)}")
print()
print("처음 10행:")
print(changes.head(10))

# 5. CSV로 저장
current_constituents.to_csv("data/sp500_current.csv", index=False)
changes.to_csv("data/sp500_changes.csv", index=False)

print()
print("=" * 60)
print("저장 완료:")
print("  - sp500_current.csv (현재 종목)")
print("  - sp500_changes.csv (변경 이력)")
print("=" * 60)