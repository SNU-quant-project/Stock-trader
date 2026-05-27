# Short-term Mean Reversion Backtest
#
# Alpha:          rank(-returns) — 단기 역모멘텀
# Neutralization: GICS Sector
# Decay:          4일 weighted MA (D-1:D-2:D-3:D-4 = 4:3:2:1)
# Entry/Exit:     D 시가 ~ D+1 시가
# Position mgmt:  일별 리밸런싱, 차이만 거래
# Universe:       S&P 500 panel data

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# === 1. 데이터 로드 ===

def load_panel_and_sectors():
    """Panel data와 종목별 GICS Sector 매핑을 로드."""
    # Panel data
    panel = pd.read_parquet("data/sp500_panel.parquet")

    # Sector 매핑 (현재 S&P 500 종목만)
    current = pd.read_csv("data/sp500_current.csv")
    sector_map = dict(zip(current["Symbol"], current["GICS Sector"]))

    # Panel에는 있는데 sector_map에 없는 종목 처리
    # (예: 1년 사이 방출된 JNPR, ANSS, HES 등은 current에 없음)
    # 이 경우 "Unknown" sector로 분류 → 이들끼리 묶임
    panel_symbols = panel.index.get_level_values("symbol").unique()
    missing = [s for s in panel_symbols if s not in sector_map]
    print(f"  Sector 정보 없는 종목 수: {len(missing)} (예: {missing[:5]})")
    for s in missing:
        sector_map[s] = "Unknown"

    return panel, sector_map


# === 2. 가격 행렬 만들기 ===

def build_price_matrices(panel):
    """Panel을 close/open 두 개의 wide 행렬로 변환.
    
    행: 날짜, 열: 종목.
    백테스팅 루프에서 빠른 접근을 위해 미리 wide 형식으로.
    """
    close = panel["close"].unstack(level="symbol")
    open_ = panel["open"].unstack(level="symbol")

    # 인덱스를 date 만 (timezone 제거)
    close.index = close.index.date
    open_.index = open_.index.date

    return close, open_

def apply_truncation(positions, limit=0.08):
    """한 번만 적용: 8% 초과분을 같은 부호의 미만 종목들에 비례 재분배.
    재분배 후에도 일부 종목이 8%를 초과할 수 있음 (Brain과 동일한 동작).
    """
    result = positions.copy()

    for date in result.index:
        row = result.loc[date].copy()

        # Long 사이드
        long_mask = row > 0
        long_excess_mask = row > limit
        if long_excess_mask.any():
            excess = (row[long_excess_mask] - limit).sum()
            row[long_excess_mask] = limit
            long_room_mask = long_mask & (row < limit)
            if long_room_mask.any():
                weights = row[long_room_mask] / row[long_room_mask].sum()
                row[long_room_mask] += excess * weights

        # Short 사이드
        short_mask = row < 0
        short_excess_mask = row < -limit
        if short_excess_mask.any():
            excess = (row[short_excess_mask] + limit).sum()  # 음수
            row[short_excess_mask] = -limit
            short_room_mask = short_mask & (row > -limit)
            if short_room_mask.any():
                weights = row[short_room_mask] / row[short_room_mask].sum()
                row[short_room_mask] += excess * weights

        result.loc[date] = row

    return result

# === 3. 알파 파이프라인 ===

def compute_alpha(close, sector_map):
    """매일 알파를 계산하여 (날짜 x 종목) DataFrame 반환.
    
    파이프라인:
      returns      = (close_t / close_{t-1}) - 1
      raw_alpha    = -returns
      ranked       = cross-sectional rank (0~1)
      demeaned     = ranked - 0.5
      neutralized  = sector별 평균 빼서 sector 합 = 0
      normalized   = |sum| = 1
    """
    # (1) Returns
    returns = close.pct_change()

    # (2) Raw alpha: -returns (음수 수익률에 양수 시그널 = 역모멘텀)
    raw_alpha = -returns

    # (3) Cross-sectional rank (0~1)
    #     rank(pct=True)는 각 행 안에서 0~1 분위수로 변환
    ranked = raw_alpha.rank(axis=1, pct=True)

    # (4) Demean: 0.5 빼서 -0.5 ~ +0.5
    demeaned = ranked - 0.5

    # (5) Sector neutralize: 각 sector 안에서 평균 빼기
    #     같은 sector 종목들끼리 합산이 0이 되도록
    sectors = pd.Series(sector_map)
    
    # 종목별 sector 정보를 컬럼 순서대로 정렬
    symbol_to_sector = sectors.reindex(demeaned.columns)
    
    # sector별 그룹화 후 평균 빼기
    # transform("mean") 은 그룹 평균을 원래 shape으로 broadcast
    neutralized = demeaned.copy()
    for sector_name in symbol_to_sector.unique():
        mask = (symbol_to_sector == sector_name).values
        sector_cols = demeaned.columns[mask]
        sector_mean = demeaned[sector_cols].mean(axis=1)
        neutralized[sector_cols] = demeaned[sector_cols].sub(sector_mean, axis=0)

    # (6) Normalize: 각 날짜에서 |sum| = 1
    #     절댓값 합으로 나눠서 long/short 합이 ±0.5 가 되도록
    abs_sum = neutralized.abs().sum(axis=1)
    normalized = neutralized.div(abs_sum, axis=0)

    # (7) Truncation: 정규화된 포지션 비중 기준으로 8% 캡
    #     long/short 사이드 합은 보존되므로 |sum|=1 도 유지됨
    normalized = apply_truncation(normalized, limit=0.08)

    return normalized


# === 4. Decay ===

def apply_decay(alpha, weights=[4, 3, 2, 1]):
    total = sum(weights)
    position = sum(w * alpha.shift(i + 1) for i, w in enumerate(weights)) / total

    # Decay 후 재정규화: |sum| = 1 유지
    abs_sum = position.abs().sum(axis=1)
    position = position.div(abs_sum, axis=0)

    return position


# === 5. 백테스팅 ===

def backtest(position, close, open_):
    """포지션 시계열을 받아 일별 수익을 계산.
    
    return_D = Σ position_D[i] * (open_{D+1}[i] / open_D[i] - 1)
    
    여기서 open_D는 D 시가 (진입), open_{D+1}은 다음날 시가 (청산).
    매일 새 포지션으로 갈아타지만 '차이만 거래' 가정.
    """
    # 다음날 시가로 평가
    # open_.shift(-1)은 t에서 보면 t+1 시가
    next_open = open_.shift(-1)
    daily_returns = next_open / open_ - 1  # 종목별 일수익률

    # 포지션 * 종목별 수익을 종목방향으로 합산 = 포트폴리오 일수익률
    portfolio_returns = (position * daily_returns).sum(axis=1)

    return portfolio_returns


# === 6. 성과 지표 ===

def compute_metrics(portfolio_returns, position):
    rets = portfolio_returns.dropna()

    cumulative = (1 + rets).cumprod()
    total_return = cumulative.iloc[-1] - 1

    sharpe = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else 0

    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    mdd = drawdown.min()

    win_rate = (rets > 0).mean()

    trade = position.diff().abs().sum(axis=1).dropna()
    avg_turnover = trade.mean()

    # Max weight concentration: 각 날짜의 최대 |포지션|, 1년 평균과 최댓값
    daily_max_weight = position.abs().max(axis=1).dropna()
    avg_max_weight = daily_max_weight.mean()
    peak_max_weight = daily_max_weight.max()

    return {
        "total_return": total_return,
        "annual_return": (1 + total_return) ** (252 / len(rets)) - 1,
        "sharpe": sharpe,
        "mdd": mdd,
        "win_rate": win_rate,
        "avg_turnover": avg_turnover,
        "avg_max_weight": avg_max_weight,
        "peak_max_weight": peak_max_weight,
        "n_days": len(rets),
        "cumulative": cumulative,
        "drawdown": drawdown,
    }


def print_metrics(m):
    print(f"  거래일 수      : {m['n_days']}일")
    print(f"  총 수익률      : {m['total_return']:+.2%}")
    print(f"  연환산 수익률  : {m['annual_return']:+.2%}")
    print(f"  Sharpe         : {m['sharpe']:.3f}")
    print(f"  MDD            : {m['mdd']:+.2%}")
    print(f"  승률           : {m['win_rate']:.2%}")
    print(f"  평균 회전율    : {m['avg_turnover']:.2%}/일")
    print(f"  평균 최대비중  : {m['avg_max_weight']:.2%}")
    print(f"  최고 최대비중  : {m['peak_max_weight']:.2%}")


# === 7. 시각화 ===

def plot_results(m, save_path="results/backtest_result.png"):
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # (위) 누적 수익
    axes[0].plot(m["cumulative"].index, m["cumulative"].values, color="#2ecc71", linewidth=1.5)
    axes[0].axhline(1.0, color="gray", linestyle="--", linewidth=0.5)
    axes[0].set_ylabel("Cumulative Return")
    axes[0].set_title("Short-term Mean Reversion (rank(-returns), Sector Neutral, Decay 4)")
    axes[0].grid(True, alpha=0.3)

    # (아래) Drawdown
    axes[1].fill_between(m["drawdown"].index, m["drawdown"].values, 0,
                         color="#e74c3c", alpha=0.3)
    axes[1].set_ylabel("Drawdown")
    axes[1].set_xlabel("Date")
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=100)
    print(f"  차트 저장: {save_path}")


# === Main ===

if __name__ == "__main__":
    print("[1/5] 데이터 로드 중...")
    panel, sector_map = load_panel_and_sectors()
    close, open_ = build_price_matrices(panel)
    print(f"  Panel shape: {close.shape} (날짜 x 종목)")
    print(f"  날짜 범위:  {close.index[0]} ~ {close.index[-1]}")
    print()

    print("[2/5] 알파 계산 중...")
    alpha = compute_alpha(close, sector_map)
    # 검증: 각 날짜에서 |sum| 이 1에 가까운지, sector별 합이 0에 가까운지
    print(f"  알파 절댓값 합 평균: {alpha.abs().sum(axis=1).mean():.4f} (1.0에 가까워야 함)")
    print(f"  알파 단순 합 평균:   {alpha.sum(axis=1).mean():.6f} (0에 가까워야 함)")
    print()

    print("[3/5] Decay 적용 중...")
    position = apply_decay(alpha)
    print(f"  포지션 절댓값 합 평균: {position.abs().sum(axis=1).mean():.4f}")
    print()

    print("[4/5] 백테스팅 실행 중...")
    portfolio_returns = backtest(position, close, open_)
    print()

    print("[5/5] 결과:")
    metrics = compute_metrics(portfolio_returns, position)
    print_metrics(metrics)
    print()
    plot_results(metrics)