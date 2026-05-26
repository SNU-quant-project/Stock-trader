# Phase 3 작업 보고서 — Base Classifier + Meta Model

**작성일:** 2026-05-03
**대상 Phase:** Phase 3 (분류기 + 메타 모델)
**연결 문서:** `SNU Quant/HMM_regime_plan.md`, `phase1_work_report.md`, `phase2_work_report.md`

---

## 📌 이 문서의 목적과 사용법

Phase 4 작업을 새 대화창에서 시작하기 위한 인계 자료. Phase 4 진행 시 다음 네 문서를 함께 읽음:

1. `HMM_regime_plan.md` — 전체 프로젝트 큰 그림
2. `phase1_work_report.md` — 피처 엔지니어링 인계
3. `phase2_work_report.md` — HMM 라벨러 인계
4. `phase3_work_report.md` (이 문서) — Base Classifier + Meta Model 인계

**문서 간 충돌 시 이 보고서가 우선** (가장 최신).

**⚠️ Phase 4 진입 전에 반드시 4장(중대 문제) + 5장(Label Smoother 도입) 을 읽을 것.**

---

# 1. Phase 3에서 완료된 내용

## 1-1. 새로 추가/수정된 파일 트리

```
Coin-trader-main/
│
├── strategy/HMM_strategy/
│   ├── config.py                                ★ 수정 — Phase 3 변수 추가 (smoother 포함)
│   ├── classifiers/
│   │   ├── base_classifier.py                   ★ 신규 — 추상 베이스 클래스
│   │   ├── adx_classifier.py                    ★ 신규 — ADX sigmoid 분류기
│   │   └── r2_classifier.py                     ★ 신규 — R² sigmoid 분류기 (slope_norm 입력)
│   ├── regime/
│   │   ├── transition.py                        ★ 신규 — 마르코프 전이 예측기
│   │   └── label_smoother.py                    ★ 신규 — 5장 후향적 라벨 보정
│   ├── meta_model/
│   │   ├── base_meta_model.py                   ★ 신규 — 메타 모델 추상 클래스
│   │   └── logistic_meta_model.py               ★ 신규 — 로지스틱 회귀 메타
│   └── scripts/
│       ├── build_hmm_cache.py                   ★ 신규 — HMM 캐시 빌더
│       ├── verify_meta_model.py                 ★ 신규 — Phase 3 통합 검증
│       ├── sweep_window_size.py                 ★ 신규 — 윈도우 크기 비교
│       └── verify_label_smoother.py             ★ 신규 — Label Smoother 검증
│
├── models/
│   └── hmm_btc.joblib                           ★ 신규 — HMM 라벨러 캐시
│
└── tests/
    └── test_hmmclassifiers.py                   ★ 신규 — Phase 3 단위 테스트 (46개, smoother 포함)
```

★ = Phase 3에서 새로 만들어진/수정된 파일.

## 1-2. 각 파일의 역할

### `classifiers/base_classifier.py` — 추상 베이스 클래스

```python
class BaseClassifier(ABC):
    @abstractmethod
    def predict(self, window: pd.Series) -> int: ...        # 0/1/2
    @abstractmethod
    def predict_proba(self, window: pd.Series) -> np.ndarray: ...  # (3,)

    # 자동 제공 (재정의 가능)
    def predict_batch(self, windows: pd.DataFrame) -> np.ndarray: ...
    def predict_proba_batch(self, windows: pd.DataFrame) -> np.ndarray: ...

    @property
    def name(self) -> str: ...
```

**클래스 라벨 정수값**: `BULL=0, SIDE=1, BEAR=2` — HMMLabeler와 통일 (기획서의 1/0/-1 안 따름, 변경사항은 2-1 참조).

### `classifiers/adx_classifier.py` — ADX 시그모이드 분류기

3단계 sigmoid 로직:
1. `P_trend = sigmoid(adx_steepness × (adx_mean - threshold))` → 추세 vs 횡보
2. `bull_share = sigmoid(direction_steepness × cum_return)` → Bull vs Bear
3. `P_Side = 1-P_trend, P_Bull = P_trend × bull_share, P_Bear = P_trend × (1-bull_share)`

**기본 파라미터** (config.py 기준):
- `threshold=25`, `adx_steepness=0.2`, `direction_steepness=50`
- 입력 컬럼: `adx_mean`, `cum_return`

### `classifiers/r2_classifier.py` — R² 시그모이드 분류기

ADX와 동일 구조, 다만:
- 추세 강도: `r2_mean` (0~1 범위 → steepness 8.0)
- 방향: `slope_norm` (RollingStandardScaler로 정규화된 z-score → steepness 1.0)

**호출자 책임:** features에 `slope_norm` 컬럼을 미리 계산해 넣어둘 것 (1-3 사용 예시 참조).

### `regime/transition.py` — TransitionPredictor

```python
class TransitionPredictor:
    def __init__(self, transmat: np.ndarray): ...
    def predict_next(self, current_proba: np.ndarray) -> np.ndarray: ...    # (3,)
    def predict_next_batch(self, current_proba_batch: np.ndarray) -> np.ndarray: ...  # (n, 3)

    @classmethod
    def from_labeler(cls, labeler) -> 'TransitionPredictor':
        """HMMLabeler에서 transmat 추출 + Bull/Side/Bear 순서 재배열."""
```

**핵심:** hmmlearn의 `transmat_`은 내부 state ID 기준이라 학습마다 무작위. `from_labeler`가 `regime_to_state_` 매핑으로 [Bull, Side, Bear] 순서로 재배열 처리.

### `meta_model/base_meta_model.py` — 메타 모델 추상 클래스

```python
class BaseMetaModel(ABC):
    @abstractmethod
    def fit(self, X, y) -> 'BaseMetaModel': ...
    @abstractmethod
    def predict_proba(self, X) -> np.ndarray: ...   # (n, 3)
    @abstractmethod
    def save(self, path: str) -> None: ...
    @abstractmethod
    def load(self, path: str) -> None: ...

    # 자동 제공
    def predict(self, X) -> np.ndarray: ...   # argmax of predict_proba
```

### `meta_model/logistic_meta_model.py` — Logistic Regression 메타

내부 구조:
```
LogisticMetaModel
   ├── StandardScaler        ← 피처 스케일 통일
   └── LogisticRegression    ← multinomial (lbfgs solver)
```

**기본 파라미터:** `C=1.0`, `class_weight='balanced'`, `max_iter=1000`, `random_state=42`.

**부가 메서드:**
- `get_coef_summary() -> pd.DataFrame` — 클래스별 계수 + 절편을 보기 좋게 반환

### `scripts/build_hmm_cache.py` — HMM 캐시 빌더

목적: HMM 한 번 학습해서 `models/hmm_btc.joblib`로 저장. 메타 모델 학습 시 매번 재학습 안 하도록.

```bash
# 캐시 없으면 학습, 있으면 종료
python -m strategy.HMM_strategy.scripts.build_hmm_cache

# 강제 재학습
python -m strategy.HMM_strategy.scripts.build_hmm_cache --retrain
```

### `scripts/verify_meta_model.py` — Phase 3 통합 검증

전체 파이프라인 실행 + 시각화:
```bash
python -m strategy.HMM_strategy.scripts.verify_meta_model --no-show \
    --save-cm conf.png --save-coef coef.png
```

**출력:**
- 각 fold 정확도, F1(macro), 전환시점 정확도
- 평균 혼동행렬 (heatmap)
- 계수 막대그래프 (피처별 클래스 영향)
- Persistence baseline vs 메타 모델 비교

## 1-3. 사용 예시 (Phase 4 진입 시 그대로 활용 가능)

```python
import numpy as np
from strategy.HMM_strategy import config
from strategy.HMM_strategy.features.resampler import load_and_resample
from strategy.HMM_strategy.features.window_features import compute_window_features
from strategy.HMM_strategy.features.scaling import RollingStandardScaler
from strategy.HMM_strategy.regime.hmm_labeler import HMMLabeler
from strategy.HMM_strategy.regime.transition import TransitionPredictor
from strategy.HMM_strategy.classifiers.adx_classifier import ADXClassifier
from strategy.HMM_strategy.classifiers.r2_classifier import R2Classifier
from strategy.HMM_strategy.meta_model.logistic_meta_model import LogisticMetaModel

# 1. 데이터 + 윈도우 피처
df = load_and_resample(config.DATA_PATH, timeframe=config.TIMEFRAME)
features = compute_window_features(df, window_size=config.WINDOW_SIZE,
                                    adx_period=config.ADX_PERIOD,
                                    r2_period=config.R2_PERIOD)

# 2. slope_norm 추가 (R²Classifier 입력용)
slope_scaler = RollingStandardScaler(window=config.ROLLING_SCALER_WINDOW)
features['slope_norm'] = slope_scaler.fit_transform(features[['slope']].values).flatten()

# 3. HMM 라벨러 로드
labeler = HMMLabeler()
labeler.load(config.HMM_MODEL_PATH)

# 4. 분류기들
adx_clf = ADXClassifier()
r2_clf = R2Classifier()
adx_proba = adx_clf.predict_proba_batch(features)
r2_proba = r2_clf.predict_proba_batch(features)

# 5. 전이 예측기
predictor = TransitionPredictor.from_labeler(labeler)

# 6. 메타 모델 학습 (생략 — verify_meta_model.py 참조)
```

## 1-4. 단위 테스트 현황

**총 91개 테스트 전부 통과** (`pytest tests/test_hmmfeatures.py tests/test_hmmlabeler.py tests/test_hmmclassifiers.py`)

| 그룹 | 테스트 수 | 검증 내용 |
|---|---|---|
| Phase 1 (test_hmmfeatures.py) | 34 | 회귀 — 변경 없음 |
| Phase 2 (test_hmmlabeler.py) | 23 | 회귀 — 변경 없음 |
| TestBaseClassifier | 3 | 추상 클래스 차단, 상수, 배치 자동 제공 |
| TestADXClassifier | 7 | Bull/Side/Bear, 합=1, 배치, NaN, 잘못된 steepness |
| TestR2Classifier | 7 | 동일 패턴 + custom slope_col |
| TestTransitionPredictor | 6 | 행렬곱, 검증, from_labeler 재배열 |
| TestBaseMetaModel | 1 | 추상 클래스 차단 |
| TestLogisticMetaModel | 10 | fit/predict/계수/save/load/검증 |

## 1-5. 실데이터 (BTC 4h) 검증 결과

```
[1/5] 데이터 로드 + 윈도우 피처
      → 원본 봉: 15,848, 윈도우: 15,789
      → slope_norm 추가 (cold start NaN: 2,199행)

[2/5] HMM 라벨러 로드 (캐시 사용)
      → 전이행렬 대각선: [0.978, 0.987, 0.983]

[3/5] Base Classifier + 전이행렬 사전확률 + HMM 사후확률 계산
      → X_meta shape: (15789, 16)

[4/5] 라벨 y 구성 (다음 윈도우 HMM 라벨, shift=-1)
      → 최종 학습 가능: X=(13589, 16), y=(13589,)
      → 라벨 분포: Bull=24.7%, Side=48.2%, Bear=27.1%

[5/5] TimeSeriesSplit 학습 (5 folds, gap=60)

      Fold    train     test    acc   F1(macro)   trans  trans_acc
         1   2,209    2,264   0.985      0.983      35      0.114
         2   4,473    2,264   0.981      0.978      42      0.143
         3   6,737    2,264   0.985      0.982      35      0.086
         4   9,001    2,264   0.986      0.985      33      0.061
         5  11,265    2,264   0.985      0.984      36      0.083

      평균 정확도:        0.984 ± 0.002
      평균 F1 (macro):    0.982 ± 0.002
      평균 전환시점 정확도: 0.097 ± 0.028   ← ★ 매우 낮음
      Persistence baseline (현재 라벨 그대로): 0.984   ← ★ 메타와 동일
      다수클래스(Side) baseline:                0.482

[혼동행렬]
              Bull    Side    Bear
        Bull  0.975  0.014  0.011
        Side  0.007  0.987  0.006
        Bear  0.006  0.009  0.985
```

---

# 2. 진행 과정에서 변경된 사항

기획서/Phase 1·2 보고서와 다른 결정. **Phase 4 이후는 모두 이 변경을 따른다.**

## 2-1. 클래스 라벨 정수값을 0/1/2로 통일

**기획서 4-3:** `BaseClassifier.predict()`가 `1(Bull) / 0(Side) / -1(Bear)` 반환

**Phase 3 변경:** `0(Bull) / 1(Side) / 2(Bear)`로 통일

**이유:** HMMLabeler가 이미 0/1/2 사용. 메타 모델 라벨 정합성을 위해 분류기도 같은 컨벤션. 변환 코드 없어 혼동 방지.

**영향:** Phase 4의 strategy.py 작성 시, `0/1/-1`로 매핑이 필요하면 generate_signals 단계에서 명시적으로 변환 (`{0: +1, 1: 0, 2: -1}` 같은 dict).

## 2-2. R²Classifier는 slope_norm을 입력으로 받음

**기획서:** ADX/R² 분류기 모두 cum_return으로 방향 판단

**Phase 3 변경:** R²는 `slope` 사용 + RollingStandardScaler로 z-score 정규화 → `slope_norm` 컬럼

**이유:** slope의 절대 스케일이 시간에 따라 변동(BTC 가격 단위 의존). z-score화로 시간 드리프트 제거.

**호출자 책임 명시:** 분류기 자체는 정규화 안 함. caller(verify_meta_model.py 등)가 미리 `features['slope_norm']`를 만들어 둘 것.

## 2-3. ADX 분류기와 R² 분류기의 direction_steepness가 다름

**Phase 3 결정:**
- `DIRECTION_STEEPNESS = 50.0` — ADX용 (cum_return 단위 ±0.05 범위)
- `R2_DIRECTION_STEEPNESS = 1.0` — R²용 (slope_norm z-score 단위 ±2 범위)

**이유:** 두 입력의 분포 스케일이 다르므로 sigmoid 입력 단위도 다르게 설정해야 적절히 분배됨.

## 2-4. HMM 라벨러를 Phase 3에서 캐시로 사용

**기획서:** 메타 모델 학습 시 HMM 매번 재학습

**Phase 3 변경:** `models/hmm_btc.joblib` 캐시 도입. `--retrain-hmm` 플래그로만 재학습.

**이유:** 메타 모델 튜닝(C값 변경 등)할 때 30 restart × 13.5K행 HMM 재학습은 시간 낭비. 한 번 학습해 저장.

**캐시 무효화 조건 (재학습 필요):**
- HMM_FEATURE_COLS 변경
- SCALER_MODE / ROLLING_SCALER_WINDOW 변경
- N_STATES, HMM_COVARIANCE_TYPE 변경
- WINDOW_SIZE, ADX_PERIOD, R2_PERIOD 변경
- 데이터 자체 갱신

## 2-5. 메타 모델 입력 X 구성 — 16개 피처

기획서 4-4의 입력 명세를 구체화:

```
[ADX 분류기 출력      : 3개]   adx_p_bull, adx_p_side, adx_p_bear
[R²  분류기 출력      : 3개]   r2_p_bull,  r2_p_side,  r2_p_bear
[윈도우 피처          : 4개]   cum_return, volatility, adx_mean, r2_mean
[HMM 사후확률         : 3개]   hmm_p_bull, hmm_p_side, hmm_p_bear
[마르코프 전이 후 확률 : 3개]   trans_p_bull, trans_p_side, trans_p_bear
```

**기획서와의 차이:** 기획서에는 `adx_end`, `r2_end`도 포함 가능성 언급. Phase 3에서는 단순화 위해 제외 (adx_mean, r2_mean이 윈도우 평균이므로 충분히 추세 정보 포함).

## 2-6. sklearn 1.5+ 호환 — multi_class 파라미터 제거

`LogisticRegression(multi_class='multinomial')`이 deprecated. lbfgs solver는 자동 multinomial 모드 → 명시 안 해도 됨. FutureWarning 제거.

---

# 3. 새롭게 정해진 방향성 및 계획 (Phase 4+)

## 3-1. 메타 모델 출력 → 포지션 변환 (Phase 4)

```
LogisticMetaModel.predict_proba(X) → [P_Bull, P_Side, P_Bear]   shape (n, 3)
                ↓
PositionSizer (Phase 4 신규)
                ↓
포지션 비중 (-1.0 ~ +1.0 또는 분리형 long/short)
                ↓
HMMStrategy.generate_signals() → BaseStrategy 호환 출력
```

## 3-2. 룩어헤드 방지 — Phase 3 검증 완료

- ✅ y는 `shift(-1)` (다음 윈도우 라벨)
- ✅ TimeSeriesSplit + gap=WINDOW_SIZE
- ✅ 매 fold마다 새 LogisticMetaModel (이전 fold 학습 누설 X)
- ✅ slope_norm은 RollingStandardScaler (룩어헤드 안전, Phase 2 검증)

Phase 4에서 추가로 주의:
- 백테스트 시 generate_signals이 t시점에 t+1 라벨 정보를 쓰면 안 됨

## 3-3. Phase 4의 핵심 구현 항목 (기획서 6장 기준)

- [ ] `position/sizer.py` 구현 (net / dual 모드)
- [ ] `strategy.py` HMMStrategy 통합 — `BaseStrategy` 상속
- [ ] 기존 Engine으로 백테스트 실행
- [ ] DonchianADXR2Strategy / Buy&Hold 대비 성능 비교
- [ ] 이동평균 크로스 베이스라인 추가 (기획서 9장)

## 3-4. 향후 사용자 컨텍스트 (변동 없음)

- 코딩 초보 → 자세한 설명, 비유 활용
- 한국어
- **수정 전 확인 필수** — "어떻게 수정할 지" + "실행해도 될지" 항상 물어볼 것
- Pattern B (config는 기본값, 함수는 인자로 받음)
- 모든 새 모듈에 단위 테스트
- 검증 스크립트는 `scripts/`

---

# 4. ⚠️ 중대 문제 — Phase 4 진입 전 반드시 다룰 것

## 4-1. 문제 요약

**메타 모델이 단순히 "현재 라벨을 그대로 출력"하는 것 이상의 가치를 보이지 않음.**

| 지표 | 값 |
|---|---|
| 메타 모델 정확도 | 98.4% |
| Persistence baseline (현재 라벨 그대로 예측) | **98.4%** ← 동일 |
| 전환 시점 정확도 (next ≠ current) | **9.7%** |

→ 메타 모델은 사실상 "이번 윈도우에서 HMM이 Bull이라고 했으니 다음도 Bull"이라는 단순 규칙만 학습. 분류기/윈도우 피처가 들어가도 실질적 기여 없음.

## 4-2. 원인 분석

전이행렬 대각선이 **0.978~0.987로 매우 높음** → 학습 데이터의 98%는 "다음 라벨 = 현재 라벨". 메타 모델 입력에 HMM 사후확률이 포함되어 있어, 모델이 그것만 보고도 98% 정확도를 얻을 수 있음.

거시적 원인:
- BTC 4h × 60봉(10일) 윈도우는 국면 전환을 잡기엔 너무 긴 시간 단위
- 진짜 전환 데이터 포인트가 매우 희박 (전체 13,589행 중 약 180건, 1.3%)
- 클래스 가중(`balanced`)으로도 13×30=390 sample weight 정도, 학습 데이터 절대량 부족
- 16개 피처 중 HMM 사후확률 3개가 거의 정답에 가까운 신호

## 4-3. Phase 4에서 시도해야 할 4가지 옵션

**(1) HMM 사후확률을 메타 입력에서 제외** ⭐ 가장 직접적
- 메타가 base classifier + 윈도우 피처 + 전이 사전확률만 보고 판단
- HMM은 라벨 생성기로만 활용, 입력 피처에선 빠짐
- 단점: 분류기들의 표현력이 부족하면 성능 더 떨어질 수 있음

**(2) 전환 시점 가중치 부여**
- `class_weight` 대신 `sample_weight`로 전환 직전 시점에 큰 가중
- 예: 다음 윈도우에서 라벨 변하는 시점은 가중 50, 그 외는 1
- LogisticMetaModel.fit에 sample_weight 인자 추가 필요

**(3) 라벨을 "변화 여부(0/1)"로 변환**
- "다음 윈도우에 라벨이 바뀔 것인가?"라는 이진 분류 문제로 단순화
- 바뀐다면 어느 방향인지는 다른 모델(or 단순 규칙)로 후처리
- 단점: 정보 압축 → Bull→Bear 같은 큰 전환과 Side→Bull 같은 작은 전환 구분 못 함

**(4) 백테스트 결과로만 평가** ← Phase 3 마무리 결정
- 정확도가 높든 낮든 실제 PnL/Sharpe로 검증
- 전환 시점 9.7% 맞추는 것이 PnL에 실제로 얼마나 영향 주는지 봐야 결정 가능
- Phase 4 백테스트가 끝나면 (1)~(3)을 실험 가능

## 4-4. Phase 4 진입 첫 의제 (반드시 처리)

1. **(4) 옵션으로 일단 백테스트 진행** — 메타 모델을 그대로 두고 PortfolioContinuous로 백테스트
2. **결과가 만족스러우면**: 메타가 분류 정확도 외 PnL 측면에서 가치 있는 것. 그대로 진행.
3. **결과가 불만족스러우면**: (1) 옵션부터 시도. HMM 사후확률 제외 + 재학습 → 백테스트 재실행.
4. **그래도 부족하면**: (2), (3) 차례로.

## 4-5. 실험 설계 시 주의

- 옵션 비교는 같은 백테스트 환경에서 (수수료/슬리피지 동일)
- 단순히 "어떤 모델이 더 정확한가"가 아니라 "어떤 모델이 더 큰 risk-adjusted return을 주는가"로 평가
- 가능하면 옵션별 별도 모델 인스턴스로 저장해 비교 가능하게

---

# 5. Retrospective Label Smoother — 정답지 개선 도입

## 5-1. 도입 배경

4장에서 발견한 문제(메타 모델이 persistence baseline 대비 가치 없음)의 한 가지 원인은 **HMM Viterbi 라벨 자체의 지연성**이다. HMM이 국면 지속성(persistence)을 강하게 가정하므로 급격한 폭락/폭등이 발생해도 라벨을 늦게 바꾸는 경향:

```
[9봉 상승] [1봉 -10% 폭락] [후속 5봉 하락]
              ↓
HMM:  Bull Bull ... Bull Bull Bull Side Bear Bear ...
                                ↑ HMM은 폭락 후에야 전환
                       ↓ 진짜 전환은 폭락 시점
```

**이 라벨로 학습하면 메타 모델이 "HMM이 늦게 잡는 시점"을 정답으로 학습**하므로, 평가 자체도 "늦은 정답을 더 늦게 따라잡기"가 된다. 사용자가 정확히 짚어준 문제.

## 5-2. 알고리즘 — 후향적 라벨 보정

`strategy/HMM_strategy/regime/label_smoother.py`의 `RetrospectiveLabelSmoother` 클래스.

**입력:** HMM Viterbi 라벨 + 각 윈도우의 마지막 1봉 수익률
**출력:** backdate된 라벨 + 변경 이벤트 로그

**알고리즘:**
1. 전환점 찾기: `label[t-1] != label[t]`
2. 안전장치 1: 후속 N봉(persistence_check=3) 모두 새 국면 (깜빡임 방지)
3. 안전장치 2: SIDE 전환 제외 (점진적 전환이라 큰 충격 신호 없음)
4. lookback K=10봉 안에서 |1봉 수익률| > threshold(=5%)인 봉 찾기
5. 방향 일치 검증: Bear 전환 → 음수 큰 봉, Bull 전환 → 양수 큰 봉
6. 해당 시점부터 새 라벨 적용 (backdate)

**파라미터** (`config.py`):
```python
LABEL_SMOOTHER_LOOKBACK     = 10     # backdate 최대 봉 수
LABEL_SMOOTHER_THRESHOLD    = 0.05   # 5% 임계값
LABEL_SMOOTHER_PERSISTENCE  = 3      # 후속 일관성 봉 수
LABEL_SMOOTHER_INCLUDE_SIDE = False  # SIDE 전환 backdate 여부
```

## 5-3. 룩어헤드 안전성 (중요)

이 기법은 **학습용 정답지(y)만 개선**하며 예측 모델 입력(X)에는 어떤 미래 정보도 들어가지 않는다.

```
룩어헤드 = "예측 시점에 미래 데이터 사용"
라벨링  = "정답을 만드는 일 — 미래 데이터 사용 OK"
```

기존 코드도 `y = label[t+1]` (shift -1)로 미래 라벨을 정답으로 사용 중이며, smoother는 그 원칙의 연장이다. Phase 1 보고서 3-4 룩어헤드 규칙 위반 아님.

## 5-4. BTC 데이터 분포 조사 결과

7년치 BTC 4h봉 (15,847개) 수익률 분포:

| 임계값 | 폭락 (<-X%) | 폭등 (>+X%) | 합계 | 전체 대비 |
|---|---|---|---|---|
| 3% | 294 | 324 | 618 | 3.90% |
| **5%** | **71** | **70** | **141** | **0.89%** |
| 7% | 20 | 21 | 41 | 0.26% |
| 10% | 4 | 5 | 9 | 0.06% |

5% 임계값으로 약 141건의 후보 충격 이벤트. TOP-5 폭락: -20.50%, -17.93%, -12.17%, -10.53%, -9.61%. TOP-5 폭등: +14.75%, +12.83%, +11.16%, +10.89%, +10.39%.

## 5-5. 실데이터 적용 결과

**파라미터:** lookback=10, threshold=5%, persistence=3, SIDE 제외

**Backdate 통계:**
- 총 이벤트: **10건** (141개 후보 충격 중 — 대부분은 기존 국면 내 충격이라 전환 트리거 안 됨)
- 평균 shift: 5.4봉 (약 22시간), median 5.5봉, max 10봉
- 평균 |shock|: 6.62%, max 9.61%
- 방향별: Bull로 backdate 3건, Bear로 backdate 7건 (폭락이 더 흔함)

**라벨 분포 변화:**
| 국면 | Original | Smoothed | Diff |
|---|---|---|---|
| Bull | 5,555 | 5,544 | -11 |
| Side | 6,546 | 6,517 | -29 |
| Bear | 3,688 | 3,728 | +40 |

Bear가 가장 많이 늘어남 — 폭락 시 라벨이 앞당겨지면서 Side로 분류되던 구간이 Bear가 됨.

**메타 모델 비교 (5-fold TimeSeriesSplit):**

| Metric | Original | Smoothed | Diff |
|---|---|---|---|
| 평균 정확도 | 0.984 | 0.978 | **-0.006** |
| **전환시점 정확도** | **0.097** | **0.129** | **+0.032** |
| Persistence baseline | 0.984 | 0.984 | 0.000 |

→ **전환시점 정확도가 9.7% → 12.9%로 약 33% 상대 개선**. 전체 정확도는 -0.6%p 약간 떨어짐 (정답지가 "더 어려워졌으므로" 자연스러운 trade-off).

## 5-6. 평가 — 부분적 성공

**긍정:**
- 룩어헤드 없이 정답지를 개선했고, 전환시점 정확도가 의미 있게 향상
- 시각화에서 폭락 시점의 라벨이 실제로 앞당겨진 것 확인 가능

**한계:**
- 12.9%는 여전히 매우 낮은 절대 수치
- backdate 이벤트가 10건뿐이라 학습 데이터에 미치는 영향이 제한적
- Persistence baseline은 변화 없음 — 메타 모델이 여전히 "다수 시점에서 현재 라벨 그대로 출력"하는 패턴 유지

**결론:** Smoother는 정답지를 의미 있게 개선했지만, **4장의 근본 문제(메타가 HMM 사후확률에만 의존)는 해결하지 못함**. Phase 4의 (1) 옵션(HMM 사후확률 제외)과 함께 사용해야 시너지.

## 5-7. Phase 4에서의 활용 방침

- **기본값으로 smoother 적용**: `verify_meta_model.py`에 `--smooth-labels` 플래그 추가 검토
- **Phase 4 백테스트의 정답지(y)는 smoothed labels** 사용
- **HMM 사후확률 제외 옵션과 결합 실험**: 두 변경의 조합 효과 측정

## 5-8. 단위 테스트 — 12개 추가 통과

```
TestRetrospectiveLabelSmoother
  ├ test_invalid_params
  ├ test_no_transitions_no_change
  ├ test_bear_transition_with_crash
  ├ test_bull_transition_with_spike
  ├ test_threshold_not_met_no_backdate
  ├ test_persistence_check_filters_flicker
  ├ test_side_excluded_by_default
  ├ test_side_included_when_requested
  ├ test_lookback_limit
  ├ test_wrong_direction_no_backdate
  ├ test_length_mismatch_raises
  └ test_summarize_changes
```

Phase 1+2+3 전체 단위 테스트: **103개 통과** (Phase 1: 34, Phase 2: 23, Phase 3: 46).

---

# 6. 마무리 — Phase 3 종료 선언

- ✅ BaseClassifier + ADX/R² 분류기 (sigmoid soft probability)
- ✅ TransitionPredictor (transmat 자동 재배열 포함)
- ✅ BaseMetaModel + LogisticMetaModel (StandardScaler + multinomial LR)
- ✅ HMM 캐시 시스템 (`models/hmm_btc.joblib`)
- ✅ 통합 검증 스크립트 (verify_meta_model.py) — 정확도/F1/전환정확도/혼동행렬/계수
- ✅ 윈도우 크기 sweep 도구 (sweep_window_size.py) — 60/30/15봉 비교
- ✅ Retrospective Label Smoother (label_smoother.py) — 후향적 라벨 보정
- ✅ Smoother 검증 스크립트 (verify_label_smoother.py) — before/after 시각화
- ✅ 단위 테스트 46개 추가 (Phase 1+2+3 = 103개 전부 통과)
- ✅ 실데이터 검증 — 16개 피처 메타 입력 X 구성, 5-fold TimeSeriesSplit 학습 완료
- ⚠️ **중대 발견**: 메타 모델이 persistence baseline 대비 가치 없음 (4장 참조)
- ✅ **부분 해결**: Smoother로 전환시점 정확도 9.7% → 12.9% 개선 (5장)
- ✅ Phase 4 인계 가능 상태 (단, 4장 의제 우선 처리 필수)

**다음 단계:** 새 대화창에서 Phase 4 (포지션 사이저 + HMMStrategy 통합) 시작.
**첫 번째 작업:** 4장의 (4) 옵션 + 5장의 smoothed labels로 백테스트 → 결과 확인 → (1)~(3) 선택적 적용.
