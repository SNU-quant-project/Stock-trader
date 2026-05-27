# 알파 파이프라인 단계별 검증
#
# Panel data 의 마지막 N 일치만 잘라서, compute_alpha 의 각 변환 단계가
# 의도대로 작동하는지 sample 종목 값과 row 통계로 확인한다.
#
# 검증 포인트:
#   STEP 1  returns        — 첫 행 NaN, 값 range
#   STEP 2  raw_alpha      — 부호 반전
#   STEP 3  ranked         — row 별 min/max ≈ 0/1, mean ≈ 0.5
#   STEP 4  demeaned       — row sum ≈ 0
#   STEP 5  neutralized    — 각 sector group 의 row mean ≈ 0
#   STEP 6  truncated      — 8% 한도 초과 종목 수
#   STEP 7  normalized     — row |sum| ≈ 1, sum ≈ 0
#   STEP 8  decay          — 재정규화 후 row |sum| ≈ 1
#   DIAG    sign stability — 같은 종목의 시그널이 며칠 동안 안정적인가?

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

pd.set_option("display.width", 140)
pd.set_option("display.max_columns", 20)

# === Config ===
N_DAYS = 10                                          # 마지막 N 일치 slice (decay 4 + 검증 5)
SAMPLE_SYMBOLS = ["AAPL", "MSFT", "JPM", "XOM", "JNJ", "NVDA"]  # 서로 다른 sector

def banner(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

# === 0. Load ===
banner("STEP 0  데이터 로드 & slice")

panel = pd.read_parquet("data/sp500_panel.parquet")
current = pd.read_csv("data/sp500_current.csv")
sector_map = dict(zip(current["Symbol"], current["GICS Sector"]))

close = panel["close"].unstack(level="symbol")
open_ = panel["open"].unstack(level="symbol")
close.index = close.index.date
open_.index = open_.index.date

for s in close.columns:
    if s not in sector_map:
        sector_map[s] = "Unknown"

close = close.iloc[-N_DAYS:]
open_ = open_.iloc[-N_DAYS:]

print(f"  Slice shape : {close.shape}  (날짜 x 종목)")
print(f"  Date range  : {close.index[0]} ~ {close.index[-1]}")

SAMPLE = [s for s in SAMPLE_SYMBOLS if s in close.columns]
print(f"  Sample      : {SAMPLE}")
print(f"  Sectors     : {[sector_map[s] for s in SAMPLE]}")

# === 1. returns ===
banner("STEP 1  returns = close.pct_change()")

returns = close.pct_change()
print(returns[SAMPLE].round(4))
print()
print(f"  첫 행 NaN ?            : {returns.iloc[0].isna().all()}  (expected True)")
r1 = returns.iloc[1].dropna()
print(f"  둘째 행 종목 수        : {len(r1)}")
print(f"  둘째 행 range          : [{r1.min():+.4f}, {r1.max():+.4f}]")
print(f"  둘째 행 |mean|         : {abs(r1.mean()):.5f}  (시장 전체 평균)")

# === 2. raw_alpha ===
banner("STEP 2  raw_alpha = -returns  (역모멘텀)")

raw_alpha = -returns
last = raw_alpha.iloc[-1][SAMPLE]
print("  마지막 날 sample:")
for s in SAMPLE:
    print(f"    {s:6s}  return = {returns.iloc[-1][s]:+.4f}   raw_alpha = {raw_alpha.iloc[-1][s]:+.4f}")
print("  → return 의 부호가 정확히 뒤집혀야 함")

# === 3. ranked ===
banner("STEP 3  ranked = raw_alpha.rank(axis=1, pct=True)")

ranked = raw_alpha.rank(axis=1, pct=True)
print(ranked[SAMPLE].round(4).tail())
print()
print(f"  마지막 날 min/max       : {ranked.iloc[-1].min():.4f} / {ranked.iloc[-1].max():.4f}  (expected ~0 / ~1)")
print(f"  마지막 날 mean          : {ranked.iloc[-1].mean():.4f}  (expected ~0.5)")
print(f"  NaN 보존 ?              : {(ranked.iloc[0].isna() == raw_alpha.iloc[0].isna()).all()}")

# === 4. demeaned ===
banner("STEP 4  demeaned = ranked - 0.5")

demeaned = ranked - 0.5
print(f"  마지막 날 sum           : {demeaned.iloc[-1].sum():+.6f}  (expected ~0)")
print(f"  마지막 날 mean          : {demeaned.iloc[-1].mean():+.6f}  (expected ~0)")
print(f"  마지막 날 range         : [{demeaned.iloc[-1].min():+.4f}, {demeaned.iloc[-1].max():+.4f}]")
print(f"  마지막 날 |값| 평균     : {demeaned.iloc[-1].abs().mean():.4f}  (expected ~0.25)")

# === 5. sector neutralize ===
banner("STEP 5  sector neutralize (sector 평균 빼기)")

sectors = pd.Series(sector_map)
symbol_to_sector = sectors.reindex(demeaned.columns)

neutralized = demeaned.copy()
for sector_name in symbol_to_sector.unique():
    mask = (symbol_to_sector == sector_name).values
    sector_cols = demeaned.columns[mask]
    sector_mean = demeaned[sector_cols].mean(axis=1)
    neutralized[sector_cols] = demeaned[sector_cols].sub(sector_mean, axis=0)

last_day = neutralized.index[-1]
print(f"  마지막 날 ({last_day}) sector 별 mean (모두 ~0 이어야 함):")
for sec in sorted(symbol_to_sector.unique()):
    cols = neutralized.columns[(symbol_to_sector == sec).values]
    mean = neutralized.loc[last_day, cols].mean()
    n = len(cols)
    flag = "" if abs(mean) < 1e-10 else "  ⚠"
    print(f"    {sec:30s}  n={n:3d}  mean={mean:+.2e}{flag}")
print()
print(f"  마지막 날 전체 sum      : {neutralized.iloc[-1].sum():+.6f}  (expected ~0)")
print(f"  마지막 날 range         : [{neutralized.iloc[-1].min():+.4f}, {neutralized.iloc[-1].max():+.4f}]")

# === 6. normalize ===
banner("STEP 6  normalize  |sum| = 1")

abs_sum = neutralized.abs().sum(axis=1)
normalized = neutralized.div(abs_sum, axis=0)

print(f"  정규화 전 |sum|         : {abs_sum.iloc[-1]:.4f}")
print(f"  정규화 후 |sum|         : {normalized.iloc[-1].abs().sum():.6f}  (expected 1.0)")
print(f"  정규화 후 sum           : {normalized.iloc[-1].sum():+.6f}  (expected ~0)")
print(f"  정규화 후 max |position|: {normalized.iloc[-1].abs().max():.4f}")
print(f"  Long/Short 종목 수      : "
      f"long {(normalized.iloc[-1] > 0).sum()}, "
      f"short {(normalized.iloc[-1] < 0).sum()}, "
      f"flat {(normalized.iloc[-1] == 0).sum()}")

# === 7. truncation (정규화 후) ===
banner("STEP 7  truncation at 8%  (정규화된 포지션 비중 기준)")

def apply_truncation(positions, limit=0.08):
    result = positions.copy()
    for date in result.index:
        row = result.loc[date].copy()
        long_excess = row > limit
        if long_excess.any():
            excess = (row[long_excess] - limit).sum()
            row[long_excess] = limit
            room = (row > 0) & (row < limit)
            if room.any():
                w = row[room] / row[room].sum()
                row[room] += excess * w
        short_excess = row < -limit
        if short_excess.any():
            excess = (row[short_excess] + limit).sum()
            row[short_excess] = -limit
            room = (row < 0) & (row > -limit)
            if room.any():
                w = row[room] / row[room].sum()
                row[room] += excess * w
        result.loc[date] = row
    return result

pre_max = normalized.iloc[-1].abs().max()
n_over = (normalized.iloc[-1].abs() > 0.08).sum()
print(f"  Truncation 전 max |pos| : {pre_max:.4f}")
print(f"  > 0.08 개수             : {n_over}")
truncated_norm = apply_truncation(normalized, limit=0.08)
diff = (truncated_norm - normalized).abs().sum().sum()
print(f"  Truncation 후 변경 총량 : {diff:.6f}  (~0 이면 no-op, 이 universe 에서는 정상)")
normalized = truncated_norm

# === 8. decay ===
banner("STEP 8  decay [4, 3, 2, 1]  (D-1, D-2, D-3, D-4)")

alpha = normalized
weights = [4, 3, 2, 1]
total = sum(weights)
position = sum(w * alpha.shift(i + 1) for i, w in enumerate(weights)) / total
abs_sum_p = position.abs().sum(axis=1)
position = position.div(abs_sum_p, axis=0)

valid = position.dropna(how="all")
print(f"  Decay 가능 첫 날짜       : {valid.index[0]}")
print(f"  마지막 날 |sum|         : {position.iloc[-1].abs().sum():.6f}  (expected 1.0)")
print(f"  마지막 날 sum           : {position.iloc[-1].sum():+.6f}  (expected ~0)")
print(f"  마지막 날 max |position|: {position.iloc[-1].abs().max():.4f}")

# === DIAG. Sign stability across days ===
banner("DIAG  같은 종목 시그널의 일별 안정성")

print("  Sample 종목별, 최근 5일 신호 (sector neutralize 후, decay 전):")
print(f"  {'symbol':8s} " + " ".join(f"{str(d)[-5:]:>9s}" for d in normalized.index[-5:]))
for sym in SAMPLE:
    vals = normalized[sym].iloc[-5:].values
    str_vals = " ".join(f"{v:+9.4f}" if not np.isnan(v) else f"{'nan':>9s}" for v in vals)
    n_flips = sum(np.sign(vals[i]) != np.sign(vals[i+1])
                  for i in range(len(vals)-1)
                  if not np.isnan(vals[i]) and not np.isnan(vals[i+1]))
    print(f"  {sym:8s} {str_vals}   flips={n_flips}")
print()
print("  → 1일 mean-reversion 시그널이면 부호가 자주 뒤집힐 것 (flips 多)")
print("    decay 4 가 누적하면 서로 다른 부호가 평균되어 약해질 수 있음")

# Lag correlation: cross-sectional corr of α_t with α_{t-k}
print()
print("  α_t 와 α_{t-k} 의 cross-sectional correlation (전 기간 평균):")
print(f"  {'lag':>4s}  {'corr':>8s}")
for k in [1, 2, 3, 4]:
    corrs = []
    for t in range(k, len(alpha)):
        a_t = alpha.iloc[t]
        a_tk = alpha.iloc[t - k]
        c = a_t.corr(a_tk)
        if not np.isnan(c):
            corrs.append(c)
    avg = np.mean(corrs) if corrs else float("nan")
    print(f"  {k:>4d}  {avg:+8.4f}")
print()
print("  → lag 가 클수록 0 에 가까우면 (또는 음수면) 옛날 시그널은 노이즈")
print("    decay weight [4,3,2,1] 중 weight 1, 2 (lag 3, 4) 가 노이즈 누적")

# === VERIFY. D 일 returns vs D+1 포지션 ===
banner("VERIFY  D 일 returns vs D+1 포지션 (의도 확인)")

# decay 4 가 적용된 position 이 정상인 날 중 마지막에서 두 번째 선택
# (마지막 날은 position.shift(-1) 이 없어서 백테스트에서 의미 없음)
D_idx = -2
D       = normalized.index[D_idx]
D_next  = normalized.index[D_idx + 1]
print(f"  D    = {D}   (이 날 종가 기준 returns 가 알파에 들어감)")
print(f"  D+1  = {D_next} (이 날 시가에 들어갈 포지션을 검증)")

rets_D    = returns.iloc[D_idx]
alpha_D   = normalized.iloc[D_idx]       # decay 전, D 일에 계산된 raw 알파
pos_Dnext = position.iloc[D_idx + 1]     # decay 후, D+1 에 들어갈 포지션

print()
print("  [1] D 일 가장 많이 떨어진 5 종목  (예상: alpha_D > 0, pos_D+1 > 0)")
print(f"      {'symbol':6s} {'sector':25s} {'ret_D':>9s} {'α_D':>10s} {'pos_D+1':>10s}")
for sym in rets_D.nsmallest(5).index:
    print(f"      {sym:6s} {sector_map[sym]:25s} {rets_D[sym]:+9.4f} {alpha_D[sym]:+10.5f} {pos_Dnext[sym]:+10.5f}")

print()
print("  [2] D 일 가장 많이 오른 5 종목  (예상: alpha_D < 0, pos_D+1 < 0)")
print(f"      {'symbol':6s} {'sector':25s} {'ret_D':>9s} {'α_D':>10s} {'pos_D+1':>10s}")
for sym in rets_D.nlargest(5).index:
    print(f"      {sym:6s} {sector_map[sym]:25s} {rets_D[sym]:+9.4f} {alpha_D[sym]:+10.5f} {pos_Dnext[sym]:+10.5f}")

print()
print("  [3] Information Technology sector 안 returns 와 α_D 비교 (sector neutralize 확인)")
print("      같은 sector 내에서 ret_D 작은 종목 → α_D 큰 양수,  ret_D 큰 종목 → α_D 큰 음수")
it_syms = [s for s in normalized.columns if sector_map[s] == "Information Technology"]
it_df = pd.DataFrame({"ret_D": rets_D[it_syms], "alpha_D": alpha_D[it_syms]}).sort_values("ret_D")
print(f"      {'symbol':6s} {'ret_D':>9s} {'α_D':>10s}")
for sym in list(it_df.index[:3]):
    print(f"      {sym:6s} {it_df.loc[sym, 'ret_D']:+9.4f} {it_df.loc[sym, 'alpha_D']:+10.5f}")
print(f"      ...  (n={len(it_df)} 종목 중간 생략)")
for sym in list(it_df.index[-3:]):
    print(f"      {sym:6s} {it_df.loc[sym, 'ret_D']:+9.4f} {it_df.loc[sym, 'alpha_D']:+10.5f}")
sector_mean_alpha = it_df["alpha_D"].mean()
print(f"      → IT sector α_D 평균 = {sector_mean_alpha:+.2e}  (sector neutralize 후 ~0 이어야 함)")

print()
print("  [4] D+1 가장 큰 long 포지션 5 의 출처 (decay 4 가중)")
print("      pos_D+1 = (4·α_D + 3·α_{D-1} + 2·α_{D-2} + 1·α_{D-3}) / 10, 후 |sum|=1 재정규화")
print(f"      {'symbol':6s} {'pos_D+1':>10s}  {'α_D':>9s} {'α_D-1':>9s} {'α_D-2':>9s} {'α_D-3':>9s}")
for sym in pos_Dnext.nlargest(5).index:
    a0 = normalized.iloc[D_idx][sym]
    a1 = normalized.iloc[D_idx - 1][sym]
    a2 = normalized.iloc[D_idx - 2][sym]
    a3 = normalized.iloc[D_idx - 3][sym]
    print(f"      {sym:6s} {pos_Dnext[sym]:+10.5f}  {a0:+9.5f} {a1:+9.5f} {a2:+9.5f} {a3:+9.5f}")

print()
print("  [5] D+1 가장 큰 short 포지션 5")
print(f"      {'symbol':6s} {'pos_D+1':>10s}  {'α_D':>9s} {'α_D-1':>9s} {'α_D-2':>9s} {'α_D-3':>9s}")
for sym in pos_Dnext.nsmallest(5).index:
    a0 = normalized.iloc[D_idx][sym]
    a1 = normalized.iloc[D_idx - 1][sym]
    a2 = normalized.iloc[D_idx - 2][sym]
    a3 = normalized.iloc[D_idx - 3][sym]
    print(f"      {sym:6s} {pos_Dnext[sym]:+10.5f}  {a0:+9.5f} {a1:+9.5f} {a2:+9.5f} {a3:+9.5f}")
