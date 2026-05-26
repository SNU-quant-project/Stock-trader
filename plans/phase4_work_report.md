# Phase 4 작업 보고서 — Position Sizer + HMMStrategy 통합 + OOS 백테스트

**작성일:** 2026-05-06
**대상 Phase:** Phase 4 (포지션 사이저 + 전략 통합 + 백테스트)
**연결 문서:** `SNU Quant/HMM_regime_plan.md`, `phase1_work_report.md`, `phase2_work_report.md`, `phase3_work_report.md`

---

## 📌 이 문서의 목적과 사용법

Phase 5 작업을 새 대화창에서 시작하기 위한 인계 자료. Phase 5 진행 시 다음 다섯 문서를 함께 읽음:

1. `HMM_regime_plan.md` — 전체 프로젝트 큰 그림
2. `phase1_work_report.md` — 피처 엔지니어링 인계
3. `phase2_work_report.md` — HMM 라벨러 인계
4. `phase3_work_report.md` — Base Classifier + Meta Model 인계 (★중대 문제 4장)
5. `phase4_work_report.md` (이 문서) — 전략 통합 + OOS 검증 결과 인계

**문서 간 충돌 시 이 보고서가 우선** (가장 최신).

**⚠️ Phase 5 진입 전에 반드시 4장(OOS 검증 결론) + 5장(Phase 5 의제)을 읽을 것.**

---

# 1. Phase 4에서 완료된 내용

## 1-1. 새로 추가/수정된 파일 트리

```
Coin-trader-main/
│
├── strategy/HMM_strategy/
│   ├── config.py                                ★ 수정 — Phase 4 변수 4개 추가
│   ├── strategy.py                              ★ 신규 — HMMStrategy 통합 클래스
│   └── position/
│       └── sizer.py                             ★ 신규 — PositionSizer (net/dual)
│
├── backtester/
│   └── visualizer_run_backtest_hmm.py           ★ 신규 — Phase 4 통합 시각화
│
├── run_backtest_hmm.py                          ★ 신규 — 통합 백테스트 진입점
│
├── models/
│   └── hmm_btc.joblib                           (Phase 3에서 만든 HMM 캐시 활용)
│
└── tests/
    ├── test_position_sizer.py                   ★ 신규 — Phase 4 단위 테스트 30개
    └── test_hmm_strategy.py                     ★ 신규 — Phase 4 단위 테스트 30개
```

★ = Phase 4에서 새로 만들어진/수정된 파일.

## 1-2. 각 파일의 역할

### `position/sizer.py` — 메타 확률 → 포지션 비중

```python
from strategy.HMM_strategy.position.sizer import PositionSizer, BULL_IDX, SIDE_IDX, BEAR_IDX

sizer = PositionSizer(mode='net', min_threshold=0.1)

# 단일 시점
weight = sizer.compute(np.array([0.7, 0.2, 0.1]))   # → 0.6 (= P_Bull - P_Bear)

# 배치 (메타 모델 출력 전체)
weights = sizer.compute_batch(proba_batch)           # shape (n,)
```

**주요 동작:**
- `mode='net'`: `P(Bull) - P(Bear)` 단일 float, `|net| < threshold` 시 0 (노이즈 컷)
- `mode='dual'`: `{'long': P(Bull), 'short': P(Bear)}`, 각각 strict less than 컷
- 입력 검증: shape (3,) 또는 (n,3), NaN 거부, [0,1] 범위, 합≈1 (atol=1e-3)

**룩어헤드 안전성:** 입력 외 데이터 접근 안 함 → 위험 0.

### `strategy.py` — HMMStrategy 통합 클래스

```python
from strategy.HMM_strategy.strategy import HMMStrategy

# 1. config.py 값 그대로 사용
strategy = HMMStrategy.from_config()

# 2. variant 비교
strategy_v2 = HMMStrategy.from_config(include_hmm_proba=False)

# 3. fit + 예측
strategy.fit(df_train)
signals = strategy.generate_signals(df_test)   # float64 (-1~+1)
```

**파이프라인 (fit + generate_signals 공통):**
```
df (4h OHLCV)
  ├─ compute_window_features              (Phase 1)
  ├─ RollingStandardScaler (slope_norm)   (Phase 2)
  ├─ HMMLabeler (load 또는 fit)            (Phase 2)
  ├─ ADXClassifier / R2Classifier         (Phase 3)
  ├─ TransitionPredictor.predict_next     (Phase 3)
  ├─ X_meta = stack(...)                  (variant 따라 10/16 피처)
  ├─ (학습 시) RetrospectiveLabelSmoother (Phase 3, 옵션)
  ├─ LogisticMetaModel                    (Phase 3)
  └─ PositionSizer.compute_batch          (Phase 4)
       ↓
   signals: float [-1.0, +1.0]
```

**variant 스위치 (Phase 4 핵심):**
- `include_hmm_proba=True/False`: 메타 입력에 HMM 사후확률 + 전이확률 포함 여부 (16 vs 10 피처)
- `use_smoothed_labels=True/False`: RetrospectiveLabelSmoother 적용 여부

### `run_backtest_hmm.py` — 통합 백테스트 진입점

```bash
# BTC 기본 (OOS 2025-01-01 ~ 2025-12-31)
python run_backtest_hmm.py

# 다른 자산
python run_backtest_hmm.py \
    --csv-path data/historical/ETH_USDT_1m.csv \
    --asset-name "ETH/USDT" \
    --hmm-cache models/hmm_eth.joblib \
    --output-html backtest_hmm_eth.html

# OOS 기간 변경 (2년치)
python run_backtest_hmm.py --test-start 2024-01-01 --test-end 2025-12-31
```

**모든 자산-특화 변수가 CLI 인자**로 분리되어 있어 BTC/ETH/SOL/XRP/주식 등 어떤 자산이든 같은 인터페이스로 백테스트 가능.

### `backtester/visualizer_run_backtest_hmm.py` — 5-그래프 시각화

5개 그래프가 들어 있는 1개 HTML 파일 생성:
- 그래프 1: 벤치마크 비교 (7개 전략 한 그래프, OOS 시작 0% 기준 normalize)
- 그래프 2~5: 4개 HMM variant 각각
  - Bull(초록)/Side(회색)/Bear(빨강) 음영
  - HMM equity (검은 굵은 선)
  - Buy & Hold = 비트코인 가격 변화율 (회색 가는 선) — 음영이 가격 움직임과 정합하는지 검증용
  - 포지션 비중 점선 (보조 y축)
  - hover: 날짜 / 자산 / 누적수익률 / 포지션 비중 (이전→현재) / 변화량 / 국면

**OOS-only 표시 (Phase 4에서 결정):** 워밍업 구간(약 30%)을 시각화에서 자동 제외. `result['test_start']`, `result['test_end']` 기반 동적 슬라이싱이라 OOS 기간을 6개월로든 2년으로든 바꿔도 자동 적응.

### `config.py` 추가 변수

```python
# Phase 4 추가
INCLUDE_HMM_PROBA   = True   # 메타 입력에 HMM 사후확률 포함
USE_SMOOTHED_LABELS = True   # 학습 라벨 smoothing
META_C            = 1.0
META_CLASS_WEIGHT = 'balanced'
```

## 1-3. 단위 테스트 현황

**총 163개 테스트 전부 통과** (`pytest tests/test_hmmfeatures.py tests/test_hmmlabeler.py tests/test_hmmclassifiers.py tests/test_position_sizer.py tests/test_hmm_strategy.py`)

| Phase | 파일 | 테스트 수 | 비고 |
|---|---|---|---|
| Phase 1 | test_hmmfeatures.py | 34 | 회귀 — 변경 없음 |
| Phase 2 | test_hmmlabeler.py | 23 | 회귀 — 변경 없음 |
| Phase 3 | test_hmmclassifiers.py | 46 | 회귀 — 변경 없음 |
| Phase 4 | test_position_sizer.py | 30 | net/dual, threshold, 입력 검증 |
| Phase 4 | test_hmm_strategy.py | 30 | fit/predict, 4 variant, 룩어헤드 자동검증 |

**룩어헤드 자동검증 (test_no_lookahead):** 미래 봉 50% 확대 → 과거 signal 변화 0 검증.

## 1-4. 실데이터 OOS 백테스트 결과 (BTC 4h)

**설정:**
- 학습 기간: 2020-01-01 ~ 2024-12-31 (5년, 10,956봉)
- 워밍업 (백테스트 데이터 형성용): 2024-09-03 ~ 2024-12-31 (4개월)
- OOS 백테스트: **2025-01-01 ~ 2025-12-31** (1년, 진짜 미래 데이터)
- 초기 자본: 10,000 USDT, 수수료 0.1%, 리밸런싱 임계값 0.15

**결과 (OOS 1년치 통계):**

| # | 전략 | CAGR | Sharpe | MDD | Trades | Win% |
|---|---|---:|---:|---:|---:|---:|
| 1 | HMM (HMM✓ Smooth✓) | +3.03% | 0.26 | -13.78% | 20 | 40.00% |
| 2 | HMM (HMM✓ Smooth✗) | **+5.52%** | **0.40** | -13.25% | 16 | 37.50% |
| 3 | HMM (HMM✗ Smooth✓) | -6.19% | -0.33 | -14.35% | 46 | 50.00% |
| 4 | HMM (HMM✗ Smooth✗) | -7.41% | -0.40 | -14.62% | 47 | 48.94% |
| 5 | **Donchian + ADX/R²** | **+17.22%** | **0.69** | -14.50% | 32 | 50.00% |
| 6 | MA Cross (20/60) | -20.52% | -0.33 | -36.07% | 45 | 33.33% |
| 7 | Buy & Hold | -5.86% | 0.08 | -34.37% | 0 | 0.00% |

---

# 2. 진행 과정에서 변경된 사항

기획서/Phase 1·2·3 보고서와 다른 결정. **Phase 5 이후는 모두 이 변경을 따른다.**

## 2-1. `from_config()` 클래스메서드 패턴 도입

**기획서 4-6 시그니처:** `HMMStrategy.__init__(window_size=, predict_size=, ...)` 평범한 인자.

**Phase 4 변경:** 14개 파라미터를 호출 쪽에서 `config.XXX=config.XXX` 식으로 일일이 명시 전달하기 번거로움. `from_config(**overrides)` 클래스메서드 추가.

```python
# 일반 호출
strategy = HMMStrategy.from_config()                      # config 값 자동 적용

# 일부 튜닝
strategy = HMMStrategy.from_config(include_hmm_proba=False)

# 단위 테스트
strategy = HMMStrategy(window_size=30, ...)               # 인자 직접 주입 가능
```

**Pattern B 유지:** 일반 메서드(__init__, fit, generate_signals)는 config 직접 import 안 함. `from_config()`만 명시적으로 import해서 default 채움.

## 2-2. 시점 정렬 — 1단계 시프트만 사용

**초기 설계:** 2단계 시프트 (signals[i+1]에 봉 i 정보 저장 → open[i+2] 체결).

**최종 설계:** 1단계 시프트만 (signals[i]에 봉 i 정보 저장 → EngineHMM이 자동으로 open[i+1] 체결).

**이유:**
- EngineHMM이 이미 `signals[i] → open[i+1]` 시프트를 처리
- 봉 i 종가까지의 정보로 결정 → 룩어헤드 없음
- 정보 1봉 낭비 없음
- 실제 거래 흐름과 일치 (봉 i 종가 시점에 결정해서 i+1 시가 주문)

**검증:** `test_no_lookahead`가 자동 통과 (미래 봉 변경 시 과거 signal 불변).

## 2-3. config.py에 Phase 4 변수 4개 추가

```python
INCLUDE_HMM_PROBA   = True
USE_SMOOTHED_LABELS = True
META_C            = 1.0
META_CLASS_WEIGHT = 'balanced'
```

## 2-4. 시각화 — OOS 구간만 동적 슬라이싱

**초기 설계:** 워밍업 구간 회색 음영 + OOS 구간 분리 표시.

**최종 설계:** 워밍업 완전 제거, OOS 구간만 시각화. `result['test_start']`/`result['test_end']` 기반 동적 슬라이싱 헬퍼 `_slice_oos(eq, dt, start, end)` 추가.

**이유:**
- 워밍업은 HMM이 작동도 안하는 구간 — 시각적 노이즈
- 하드코딩 없이 사용자가 OOS 기간을 변경하면 자동 적응 (Phase 5의 walk-forward나 다른 자산 적용에 강건)

## 2-5. HMMStrategy의 dual 모드 처리 (PortfolioContinuous 한계 우회)

**문제:** `PortfolioContinuous`는 양방향 동시 보유 미지원 (Phase 4 시점).

**해결:** `mode='dual'`이어도 `generate_signals()`는 `long - short`로 합쳐서 net float 반환. 사용자가 `dual` 모드를 명시해도 백테스트는 net 기준으로 동작.

**Phase 5에서 dual 진정 지원하려면:** PortfolioContinuous를 long/short 분리 보유 가능하도록 수정 필요.

## 2-6. 자산 일반화 — CLI 인자로 자산-특화 변수 분리

기획서 1장은 "BTC/USDT (추후 ETH/SOL/XRP)"만 언급. Phase 4에서 다음을 모두 CLI 인자로 분리:

- `--csv-path`, `--asset-name`, `--timeframe`
- `--train-start`, `--train-end`, `--test-start`, `--test-end`, `--warmup-days`
- `--hmm-cache` (자산별 캐시 분리)
- `--initial-capital`, `--fee-rate`, `--rebalance-threshold`
- `--output-html`

**자산 변경 시 자동 처리되는 것 (Phase 2의 RollingStandardScaler 덕분):**
- 모든 HMM 입력 피처가 z-score 정규화 → 가격 단위 무관
- ADX/R² 분류기도 정규화된 입력 사용 (slope_norm)

## 2-7. Buy & Hold 곡선을 HMM variant 그래프에 추가

사용자 요청: 음영(Bull/Side/Bear)이 실제 가격 움직임과 정합하는지 검증하려면 HMM equity 그래프에 비트코인 가격 곡선이 함께 보여야 함.

→ 각 HMM variant 그래프에 회색 가는 선으로 Buy & Hold normalized equity 추가. 첫 variant(row=2)에서만 legend 표시 (중복 방지).

---

# 3. 새롭게 정해진 방향성 (Phase 5+)

## 3-1. 메타 모델의 PnL 가치 — Phase 3 4장의 OOS 검증 결과

Phase 3 4장에서 메타 모델의 분류 정확도가 persistence baseline(98.4%) 수준이라 가치가 의심됐었다. **Phase 4 OOS 백테스트로 PnL 측면 검증 완료:**

- HMM 4 variant 모두 Donchian보다 약함 (가장 강한 variant B: +5.52% vs Donchian +17.22%)
- HMM 알파의 **유일한 우위는 MDD** (HMM ~14% vs MA/B&H ~35%, 다만 Donchian도 -14.5%)
- 결론: 현재 형태의 HMM 메타 모델은 분류 정확도뿐만 아니라 PnL 측면에서도 기존 Donchian 대체 가치 부족

## 3-2. variant 비교 결과의 함의

**(1) `INCLUDE_HMM_PROBA=True`가 PnL에 더 좋음 → Phase 3 4-3의 (1) 옵션 PnL 측면 기각**
- HMM✓ variant (A,B): +3~5% CAGR
- HMM✗ variant (C,D): -6~7% CAGR
- 메타가 분류기/피처만으로 학습하면 오히려 성능 저하 → HMM 사후확률은 PnL에서는 정보 가치 있음

**(2) Smoother는 PnL에서 살짝 마이너스 (의외)**
- variant A (Smooth✓): +3.03% / variant B (Smooth✗): +5.52%
- 분류 정확도(전환시점 9.7%→12.9%) 개선과 PnL 개선이 상관 없음
- backdate된 라벨로 학습한 메타 모델이 실제 매매 시 너무 일찍 신호를 바꿔 손실 발생 가능성

**(3) 가장 좋은 variant: B (HMM✓ Smooth✗)** — Phase 5 베이스라인.

## 3-3. Phase 5에서 시도해야 할 의제

Phase 3 4-3의 남은 옵션 + 추가 아이디어.

### A. Phase 3 4-3 후속 옵션
- **(2) sample_weight 가중**: `LogisticMetaModel.fit`에 sample_weight 추가. 전환 시점에 가중 50, 그 외는 1.
- **(3) 변화 여부 이진분류**: 라벨을 "다음 윈도우에 라벨 바뀜?"으로 단순화. 메타가 전환점만 잡고 방향은 다른 모델로 후처리.

### B. 메타 모델 고도화 (기획서 5장)
- **XGBoost 메타 모델** — 비선형 결정 가능
- **신경망 메타 모델** — Phase 5 후반

### C. 하이브리드 (방향 I)
**기획서 1-3 방향 I**: HMM 메타를 Donchian의 보조 필터로만 사용.
- HMM이 Bull → Donchian 롱 신호만 허용
- HMM이 Bear → Donchian 숏 신호만 허용
- HMM이 Side → 반대매매 또는 현금
- → 기존 Donchian 강한 PnL을 유지하면서 HMM의 MDD 절감 효과만 활용

### D. 다자산 검증
- ETH/SOL/XRP에 동일 파이프라인 적용
- 자산별 캐시 분리 자동 (`--hmm-cache models/hmm_eth.joblib` 등)

### E. Walk-forward 백테스트
- 현재는 fixed train/test (2020~2024 학습, 2025 테스트)
- 매 분기마다 재학습하는 walk-forward로 강건성 검증

### F. 이동평균 크로스 (20/60) 결과 분석
- MA Cross가 -20.5%로 처참 (whipsaw 손실 + 추세 미감지). 단순 추세추종 baseline 의미 약함.
- 더 나은 단순 baseline (e.g. SMA200 vs price) 추가 검토 가능.

## 3-4. Phase 5 진입 시 권장 작업 순서

1. 환경 점검: `pytest tests/test_hmmfeatures.py tests/test_hmmlabeler.py tests/test_hmmclassifiers.py tests/test_position_sizer.py tests/test_hmm_strategy.py` — 163개 통과해야 함
2. 사용자와 의제 우선순위 결정 (3-3 A~F 중)
3. **방향 I (하이브리드) 권장:** Donchian의 강한 PnL + HMM의 MDD 절감 결합. Phase 4 결과상 가장 실용적.
4. 새 모듈마다 단위 테스트 + 룩어헤드 자동검증 같이 작성
5. OOS 백테스트로 PnL 검증, `run_backtest_hmm.py` 인프라 그대로 활용

## 3-5. 사용자 컨텍스트 (변동 없음)

- 코딩 초보 → 자세한 설명, 비유 활용
- 한국어
- **수정 전 확인 필수** — "어떻게 수정할 지" + "실행해도 될지" 항상 물어볼 것
- Pattern B (config는 기본값 모음, 함수는 인자로 받음, `from_config()` 헬퍼로 일괄 적용)
- 모든 새 모듈에 단위 테스트
- 검증 스크립트는 `scripts/`, 통합 백테스트는 프로젝트 루트의 `run_backtest_*.py`

---

# 4. ⚠️ Phase 4 OOS 검증의 결론 — Phase 5 진입 전 반드시 다룰 것

## 4-1. 결론 요약

**현재 형태의 HMM 메타 모델은 OOS 백테스트에서 기존 Donchian 알파보다 약함.**

| 지표 | HMM 최고 (variant B) | Donchian + ADX/R² |
|---|---:|---:|
| CAGR | +5.52% | **+17.22%** |
| Sharpe | 0.40 | **0.69** |
| MDD | **-13.25%** | -14.50% |
| Trades | 16 | 32 |
| Win% | 37.50% | 50.00% |

→ HMM의 유일한 우위는 MDD뿐인데, 그것도 Donchian과 큰 차이 없음.

## 4-2. 원인 분석 (Phase 3 4장 + Phase 4 백테스트)

1. **메타 모델이 persistence 학습**: HMM 사후확률에 거의 의존, 전환 시점 정확도 9.7%~12.9%
2. **OOS 시장 환경**: 2025년 BTC가 횡보/하락 위주 → 추세 추종 알파(Donchian)에 유리
3. **메타 학습 데이터 불균형**: 전환 시점이 1.3% (학습 데이터 13,589행 중 ~180건)

## 4-3. Phase 5 첫 의제 — 4가지 옵션

**옵션 1 — 방향 I (하이브리드) ★ 권장**
- HMM 메타를 Donchian의 국면 필터로만 사용
- 기획서 1-3에 명시된 권장 방향
- 기존 Donchian 강한 PnL 유지 + HMM의 MDD 절감 효과 시도
- 구현: HMMStrategy의 generate_signals에서 raw float 비중 대신 Bull/Side/Bear 라벨만 출력 → DonchianADXR2Strategy의 regime_filter로 대체 사용

**옵션 2 — sample_weight 가중**
- 전환 시점에 큰 가중치를 둬서 메타가 persistence를 덜 학습하도록
- LogisticMetaModel.fit에 sample_weight 인자 추가
- 빠른 실험 가능

**옵션 3 — XGBoost 메타 모델**
- 비선형 결정 가능 (현재는 logistic regression)
- 기획서 5장에 언급, 구현 부담은 적음 (scikit-learn 호환)

**옵션 4 — 변화 여부 이진분류**
- 라벨을 "다음 윈도우 라벨 바뀜?"로 단순화 → 메타는 전환점만 잡음
- 방향은 단순 규칙으로 (e.g. cum_return 부호)
- 정보 압축이지만 학습 데이터의 클래스 균형 개선

## 4-4. 권장 진행 순서

1. **옵션 1 (하이브리드)부터 시작** — Phase 4 결과가 가장 명확하게 시사하는 길
2. 옵션 1이 Donchian 단독보다 우월하지 않으면 옵션 2,3을 차례로 시도
3. 옵션 4는 마지막 — 정보 압축이라 가장 큰 변화

---

# 5. 마무리 — Phase 4 종료 선언

- ✅ PositionSizer 완성 (net/dual 모드, 단일/배치 변환, 입력 검증)
- ✅ HMMStrategy 통합 완성 (BaseStrategy 호환, fit + generate_signals, variant 4가지)
- ✅ from_config() 클래스메서드 패턴 도입 (Pattern B 유지하면서 14개 파라미터 일괄 적용)
- ✅ 룩어헤드 자동검증 통과 (1단계 시프트, EngineHMM과 자연 정합)
- ✅ run_backtest_hmm.py 통합 진입점 (자산 일반화 — CLI 인자만 바꾸면 ETH/SOL/주식 가능)
- ✅ visualizer_run_backtest_hmm.py 인터랙티브 시각화 (5 그래프, OOS-only 동적 슬라이싱, B&H 참조선, Bull/Side/Bear 음영, hover 풍부)
- ✅ OOS 백테스트 (2025-01-01~2025-12-31) — BTC 4h 데이터로 7개 전략 비교
- ✅ 단위 테스트 60개 추가 (Phase 1+2+3+4 = 163개 전부 통과)
- ⚠️ **OOS 결과**: 현재 HMM 메타가 Donchian보다 약함. Phase 5에서 하이브리드(방향 I)나 sample_weight/XGBoost 등으로 개선 시도 필요
- ✅ Phase 5 인계 가능 상태 (단, 4장 결론 반영해서 첫 의제 선택 필수)

**다음 단계:** 새 대화창에서 Phase 5 시작.
**첫 번째 작업:** 4-3의 4개 옵션 중 사용자와 우선순위 결정. 권장은 **옵션 1 (하이브리드, 방향 I)**.
