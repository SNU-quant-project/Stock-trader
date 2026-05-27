import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

panel = pd.read_parquet("data/sp500_panel.parquet")
close = panel["close"].unstack(level="symbol")
open_ = panel["open"].unstack(level="symbol")
close.index = close.index.date
open_.index = open_.index.date

# Returns
returns = close.pct_change()

# 단순 mean reversion 시그널: 어제 많이 떨어진 종목 = 오늘 사고 싶은 종목
# rank(-returns) 가 큰 종목 = -returns 가 큰 종목 = returns 가 작은 종목 = 많이 떨어진 종목 → long
raw_alpha = -returns
ranked = raw_alpha.rank(axis=1, pct=True)
demeaned = ranked - 0.5

# Normalize (sector neutralize 생략, 단순화)
abs_sum = demeaned.abs().sum(axis=1)
position = demeaned.div(abs_sum, axis=0)

# 시점별: D-1 알파로 D 진입, D+1 시가에 청산
# 그러니까 position 을 한 칸 shift 해야 D 시점의 포지션이 됨
position_for_D = position.shift(1)

# 수익: D 시가 진입, D+1 시가 청산
daily_returns = open_.shift(-1) / open_ - 1
portfolio_returns = (position_for_D * daily_returns).sum(axis=1).dropna()

# 결과
cum = (1 + portfolio_returns).cumprod()
sharpe = portfolio_returns.mean() / portfolio_returns.std() * np.sqrt(252)
print(f"Sharpe (단순 버전): {sharpe:.3f}")
print(f"총 수익률:          {cum.iloc[-1] - 1:+.2%}")
print(f"평균 일수익률:      {portfolio_returns.mean() * 100:.4f}%")
print()
print(f"양수 일수익률 비율: {(portfolio_returns > 0).mean():.2%}")

# 추가 진단: 가장 큰 손실/이익 며칠
print("\n최대 손실일 5개:")
print(portfolio_returns.nsmallest(5))
print("\n최대 이익일 5개:")
print(portfolio_returns.nlargest(5))


print("\n" + "="*60)
print("Decay 만 추가 (sector neutralize 없음)")
print("="*60)

# Decay 4
weights = [4, 3, 2, 1]
total = sum(weights)
position_decay = sum(w * position.shift(i) for i, w in enumerate(weights, start=1)) / total

# Decay 후 재정규화
abs_sum = position_decay.abs().sum(axis=1)
position_decay = position_decay.div(abs_sum, axis=0)

# 수익 계산
daily_returns = open_.shift(-1) / open_ - 1
portfolio_returns_decay = (position_decay * daily_returns).sum(axis=1).dropna()

sharpe_decay = portfolio_returns_decay.mean() / portfolio_returns_decay.std() * np.sqrt(252)
print(f"Sharpe (decay만):  {sharpe_decay:.3f}")
print(f"총 수익률:         {((1 + portfolio_returns_decay).cumprod().iloc[-1] - 1):+.2%}")


print("\n" + "="*60)
print("Sector neutralize 만 추가 (decay 없음)")
print("="*60)

import pandas as pd
current = pd.read_csv("data/sp500_current.csv")
sector_map = dict(zip(current["Symbol"], current["GICS Sector"]))
panel_symbols = position.columns
for s in panel_symbols:
    if s not in sector_map:
        sector_map[s] = "Unknown"

sectors = pd.Series(sector_map).reindex(position.columns)

# Sector neutralize 직접 적용 (단순 버전의 demeaned 에서)
neutralized = demeaned.copy()
for sector_name in sectors.unique():
    mask = (sectors == sector_name).values
    sector_cols = neutralized.columns[mask]
    sector_mean = neutralized[sector_cols].mean(axis=1)
    neutralized[sector_cols] = neutralized[sector_cols].sub(sector_mean, axis=0)

# Normalize
abs_sum = neutralized.abs().sum(axis=1)
position_sector = neutralized.div(abs_sum, axis=0)

# D-1 알파로 D 진입
position_sector_for_D = position_sector.shift(1)
portfolio_returns_sector = (position_sector_for_D * daily_returns).sum(axis=1).dropna()

sharpe_sector = portfolio_returns_sector.mean() / portfolio_returns_sector.std() * np.sqrt(252)
print(f"Sharpe (sector만): {sharpe_sector:.3f}")
print(f"총 수익률:         {((1 + portfolio_returns_sector).cumprod().iloc[-1] - 1):+.2%}")