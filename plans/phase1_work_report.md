# Phase 1 작업 보고서 — HMM 기반 국면 분류 알파

**작성일:** 2026-05-01
**대상 Phase:** Phase 1 (기반 인프라)
**연결 문서:** `SNU Quant/HMM_regime_plan.md` (원본 기획서)

---

## 📌 이 문서의 목적과 사용법

이 문서는 **Phase 2 작업을 새로운 대화창에서 시작하기 위한 인계 자료**다.
Phase 2를 진행할 Claude는 다음 두 문서를 함께 읽고 작업한다:

1. `HMM_regime_plan.md` — 전체 프로젝트의 큰 그림과 설계 의도
2. `phase1_work_report.md` (이 문서) — Phase 1에서 실제 만들어진 것 + 결정 사항

**기획서와 이 보고서가 충돌하면 이 보고서가 우선한다** (이 보고서가 더 최신이고, Phase 1 진행 중 추가/변경된 결정을 반영하므로).

---

# 1. Phase 1을 진행하며 완료된 내용

## 1-1. 생성된 파일 트리

```
Coin-trader-main/
│
├── strategy/HMM_strategy/                    ★ 신규 패키지
│   ├── __init__.py
│   ├── config.py                             ★ 중앙 설정 파일 (모든 튜닝 변수)
│   ├── features/
│   │   ├── __init__.py
│   │   ├── resampler.py                      ★ 1m → 가변 타임프레임 변환
│   │   ├── indicators.py                     ★ ADX, R², slope 계산
│   │   └── window_features.py                ★ 9개 윈도우 피처 계산
│   ├── regime/
│   │   ├── __init__.py
│   │   └── regime_dataset.py                 ★ (X, y) 데이터셋 빌더
│   ├── classifiers/__init__.py               (Phase 3 자리)
│   ├── meta_model/__init__.py                (Phase 3 자리)
│   ├── position/__init__.py                  (Phase 4 자리)
│   └── scripts/
│       ├── __init__.py
│       └── verify_features.py                ★ 시각화/VIF 검증 스크립트
│
└── tests/
    └── test_hmmfeatures.py                   ★ pytest 단위 테스트 34개
```

★ = Phase 1에서 새로 작성된 코드 파일.
나머지 `__init__.py`는 빈 패키지 placeholder (Phase 2~4 자리 미리 마련).

## 1-2. 각 파일의 역할 (Phase 2 코딩 시 참조용)

### `config.py` — 모든 튜닝 가능 변수의 중앙 집중

**원칙:** 함수는 절대 config를 직접 import하지 않는다 (Pattern B).
호출하는 쪽에서 config 값을 인자로 명시 전달한다.

**현재 정의된 변수 (Phase 2에서 그대로 사용):**

```python
# 데이터/리샘플링
DATA_PATH = "data/historical/BTC_USDT_1m.csv"
TIMEFRAME = "4h"            # pandas 2.x 표준 (소문자 'h')

# 윈도우
WINDOW_SIZE  = 60
PREDICT_SIZE = 60
STEP_SIZE    = 1

# ADX/R²
ADX_PERIOD    = 12
ADX_THRESHOLD = 25
R2_PERIOD     = 40
R2_THRESHOLD  = 0.55

# HMM (Phase 2 활성)
N_STATES            = 3
HMM_N_ITER          = 200
HMM_RANDOM_RESTART  = 30
HMM_COVARIANCE_TYPE = 'diag'   # ★ 'full'에서 변경됨 (사유: 1-3 참조)

# 피처 분리
HMM_FEATURE_COLS = [
    'cum_return',
    'volatility',
    'adx_mean',
    'r2_mean',
    'up_candle_ratio',
]
META_FEATURE_COLS = None       # Phase 3에서 확정 (None = 전체 9개)

# 메타 모델 (Phase 3 활성)
META_MODEL_TYPE = 'logistic'
TS_SPLIT_N      = 5

# 포지션 (Phase 4 활성)
POSITION_MODE          = 'net'
MIN_POSITION_THRESHOLD = 0.1
REBALANCE_THRESHOLD    = 0.15

# 검증 스크립트
VERIFY_START = "2020-01-01"
VERIFY_END   = "2025-12-31"
```

### `features/resampler.py`

```python
def load_and_resample(csv_path, timeframe='4h', start=None, end=None) -> pd.DataFrame
```
- 1분봉 CSV를 읽어 임의 타임프레임으로 리샘플링
- 반환: `datetime`, `open`, `high`, `low`, `close`, `volume` 컬럼이 있는 DataFrame
- NaN 봉은 자동 제거됨

### `features/indicators.py`

```python
def compute_adx(df, period=12) -> pd.Series        # 0~100 범위
def compute_r2(df, period=40)  -> pd.Series        # 0.0~1.0 범위
def compute_slope(prices: np.ndarray) -> float     # 회귀 기울기 (1차원 배열용)
```
- ADX는 변동이 0인 구간에서 0을 반환 (NaN 아님 — 중요)
- R²는 가격이 일정한 구간에서 1.0을 반환 (정의에 의해)
- 워밍업 구간은 NaN

### `features/window_features.py`

```python
FEATURE_COLUMNS = [
    'cum_return', 'volatility', 'adx_mean', 'r2_mean',
    'adx_end', 'r2_end', 'slope', 'max_drawdown', 'up_candle_ratio',
]

def compute_window_features(
    df,
    window_size=60,
    step_size=1,
    adx_period=12,
    r2_period=40,
) -> pd.DataFrame
```

**반환 DataFrame 스키마:**
- `window_end_idx` (int): 원본 df의 마지막 봉 인덱스
- `window_end_time` (datetime): 마지막 봉 시각 (df에 datetime 컬럼이 있을 때만)
- `cum_return`, `volatility`, ..., `up_candle_ratio` (9개 피처)

**룩어헤드 의미론 (반드시 지킬 것):**
- `window_end_idx = i` → "i번째 봉 종가까지 본 정보로 만든 피처"
- 이 피처는 i+1번째 봉부터 사용 가능 (i번째 봉의 의사결정에는 사용 불가)
- Phase 2에서 라벨링 시 `shift(-1)` 등으로 시점 정렬

### `regime/regime_dataset.py`

```python
class RegimeDataset:
    def __init__(self, features_df, feature_cols=None)
    def set_labels(self, labels: np.ndarray) -> None
    def get_X(self, feature_cols=None) -> np.ndarray
    def get_y(self, shift=0) -> np.ndarray
    def get_aligned_Xy(self, shift=-1) -> tuple    # NaN 자동 제거
    def get_feature_names(self, feature_cols=None) -> list
    def get_window_end_times(self) -> pd.Series
    def get_train_test_split(self, train_end_date) -> tuple
    def __len__(self) -> int
```

**Phase 2 사용 예시 (이대로 쓸 것):**

```python
from strategy.HMM_strategy import config
from strategy.HMM_strategy.features.resampler import load_and_resample
from strategy.HMM_strategy.features.window_features import compute_window_features
from strategy.HMM_strategy.regime.regime_dataset import RegimeDataset

# 1. 데이터 로드
df = load_and_resample(config.DATA_PATH, timeframe=config.TIMEFRAME)

# 2. 윈도우 피처 계산
features = compute_window_features(
    df,
    window_size=config.WINDOW_SIZE,
    adx_period=config.ADX_PERIOD,
    r2_period=config.R2_PERIOD,
)

# 3. 데이터셋 구성
ds = RegimeDataset(features)

# 4. HMM 학습용 X (5개 피처)
X_hmm = ds.get_X(feature_cols=config.HMM_FEATURE_COLS)
# X_hmm.shape == (n_windows, 5)

# 5. (Phase 2에서) HMM 학습 → 라벨 추출 → 데이터셋에 주입
# labels = hmm.fit_predict(X_hmm)
# ds.set_labels(labels)

# 6. (Phase 3에서) 메타 모델용 X
# X_meta = ds.get_X(feature_cols=config.META_FEATURE_COLS)  # None = 9개 전체
# y      = ds.get_y(shift=-1)                                # 다음 윈도우 라벨
```

### `scripts/verify_features.py`

피처 검증 전용 스크립트 (백테스트와 분리됨).

```bash
# 기본 시각화 (BTC 종가 + 9개 피처 5단 그래프)
python -m strategy.HMM_strategy.scripts.verify_features

# 상관계수 히트맵 + VIF 표 추가
python -m strategy.HMM_strategy.scripts.verify_features --show-correlation

# 파라미터 변경
python -m strategy.HMM_strategy.scripts.verify_features --window-size 30 --timeframe 1h
```

**Phase 2~4에서 추가 검증 스크립트가 필요하면 같은 폴더(`scripts/`)에 만들면 된다.**

## 1-3. 단위 테스트 현황

**총 34개 테스트, 전부 통과 (`pytest tests/test_hmmfeatures.py`)**

| 그룹 | 테스트 수 | 검증 내용 |
|---|---|---|
| TestFeatureAccuracy | 9 | 9개 피처 합성 데이터 정확성 |
| TestNoLookahead | 1 | 룩어헤드 바이어스 자동 검증 |
| TestInterface | 7 | window_size 가변, 컬럼 존재, 워밍업 처리 |
| TestIndicators | 6 | ADX/R²/slope 자체 동작 |
| TestRegimeDataset | 11 | X/y 추출, shift, train/test 분할, 부분집합 |

**Phase 2 코딩 시 항상 이 테스트를 한 번 돌려서 회귀(regression)가 없는지 확인할 것.**

---

# 2. 진행 과정에서 변경된 내용

기획서와 다르게 결정한/추가한 부분이다. **Phase 2 이후의 결정은 모두 이 변경사항을 따른다.**

## 2-1. 패키지 구조 변경

**기획서(3장):**
```
strategy/HMM_strategy/
├── strategy.py
├── features/window_features.py
├── regime/{hmm_labeler, regime_dataset}.py
├── classifiers/...
├── meta_model/...
└── position/sizer.py
```

**실제 구현:**
- `config.py` 추가 (기획서에 없던 파일, 2-3 참조)
- `features/resampler.py` 추가 (기획서에 없던 파일)
- `features/indicators.py` 추가 (기획서에 없던 파일 — ADX/R² 새로 구현)
- `scripts/verify_features.py` 추가 (검증 스크립트 전용 폴더)

기획서의 다른 파일들은 자리(빈 `__init__.py`)만 마련되어 있고 Phase 2~4에서 채울 예정.

## 2-2. ADX/R² 계산을 새로 구현

**기획서(4-3절):** 기존 `strategy/filters/`의 ADX/R² 분류기를 "윈도우 단위 판단으로 래핑"

**변경:** HMM_strategy 패키지 내에 `indicators.py`로 새로 구현.

**이유:**
- HMM_strategy 패키지가 외부 모듈에 의존하지 않게 함 (자급자족)
- ETH/SOL/XRP 확장 시 영향 범위가 HMM_strategy 안으로 한정됨
- 파라미터 튜닝 시 부작용 격리

**수치는 기존과 동일:** `ADX_PERIOD = 12`, `R2_PERIOD = 40` (기존 `donchian_adx_r2_B.py`와 일치)

## 2-3. 중앙 설정 파일 (`config.py`) 신설

**기획서:** 없음

**추가 이유:** 사용자가 백테스트 파라미터 튜닝 시 여러 파일에 분산된 변수를 관리하기 번거로워짐을 우려.

**적용한 패턴 (Pattern B):**
- config.py는 "기본값 모음집" 역할만
- 함수 내부에서 직접 import 금지
- 호출하는 쪽에서 config 값을 인자로 명시 전달

```python
# ❌ 금지 (Pattern A)
from .config import ADX_PERIOD
def compute_adx(df):
    period = ADX_PERIOD     # 숨은 의존성

# ✅ 사용 (Pattern B)
def compute_adx(df, period=12):    # 기본값
    ...
# 호출하는 쪽:
adx = compute_adx(df, period=config.ADX_PERIOD)
```

**Phase 2 이후 추가 변수 모두 이 파일에 모아야 함.**

## 2-4. 1m → 4h 리샘플링을 함수화

**기획서:** 별도 언급 없음 (4시간봉 가정만)

**변경:** 기존 `run_backtest.py` 인라인 7줄 코드를 `resampler.py`의 `load_and_resample()` 함수로 분리.

**부가 효과:** `timeframe` 인자로 1H/4H/1D 자유 실험 가능.

## 2-5. ADX 함수의 0-나누기 처리

**구현 디테일:** 가격이 완전히 일정한 구간(`di_sum == 0`)에서 ADX는 NaN이 아니라 **0**을 반환하도록 함.

**이유:** "변동 없음 = 추세 강도 0"이 의미적으로 맞고, NaN이면 dropna에서 데이터가 사라져 단위 테스트가 깨짐.

## 2-6. TIMEFRAME 표기

**기획서:** "4시간봉"

**변경:** `'4h'` (소문자, pandas 2.x 표준).
대문자 `'4H'`는 deprecated이며 FutureWarning이 발생함.

---

# 3. 새롭게 정해진 방향성 및 계획

Phase 2~5에 영향을 미치는 결정들. **반드시 따를 것.**

## 3-1. HMM 입력 피처 (Option C 채택)

```python
HMM_FEATURE_COLS = [
    'cum_return',       # 방향 + 크기
    'volatility',       # 양방향 변동성
    'adx_mean',         # 추세 강도 평균
    'r2_mean',          # 추세 직선성 평균
    'up_candle_ratio',  # 양봉 비율
]
```

**제외된 피처와 사유:**
- `max_drawdown` (VIF 12.09): 다변량 중복 심각. cum_return + volatility + slope의 선형결합에 가까움.
- `slope` (VIF 2.67이지만): cum_return과 페어와이즈 |r|=0.77로 거의 같은 정보.
- `adx_end`, `r2_end`: "현재 시점 추세 정보"는 Meta가 전이 예측에 활용. HMM은 "국면 자체" 식별이 목적이므로 평균값(adx_mean, r2_mean)이 더 적합.

**페어와이즈 상관 결과 (참고):**
- 강한 상관 (|r| ≥ 0.7): cum_return ↔ slope (0.773), volatility ↔ max_drawdown (-0.759)
- 중간 상관 (0.5~0.7): adx_mean ↔ r2_mean (0.691), cum_return ↔ max_drawdown (0.621), cum_return ↔ up_candle_ratio (0.642), adx_end ↔ r2_end (0.594)

**VIF 결과 (전체 9개 기준):**
- max_drawdown: 12.09 ❌
- volatility: 6.62 ⚠️
- cum_return: 6.16 ⚠️
- 나머지 6개: 모두 < 3 ✅
- 상관 행렬 condition number: 63.2 (안전)

## 3-2. HMM Covariance Type

```python
HMM_COVARIANCE_TYPE = 'diag'
```

**선정 이유:**
- 'full'은 더 정확하지만 데이터 요구량이 크고 수치 불안정 위험
- 'diag'로 시작하고, 만족스럽지 않으면 'full'로 전환
- HMM_FEATURE_COLS의 5개 피처가 'diag'에 적합하도록 선정됨 (위 3-1)

**향후 'full'로 전환 시:**
- `config.py`의 한 줄만 수정
- HMM_FEATURE_COLS를 더 늘려도 됨 (예: max_drawdown 다시 포함)
- Phase 2 코드는 hmmlearn의 GaussianHMM에 `covariance_type=config.HMM_COVARIANCE_TYPE`을 그대로 넘기면 됨

## 3-3. 피처 추가/제거 워크플로우

**규칙:** 피처를 더하거나 빼고 싶을 때는 **`config.HMM_FEATURE_COLS` 또는 `config.META_FEATURE_COLS` 리스트만 수정**한다.

```python
# config.py에서:
HMM_FEATURE_COLS = ['cum_return', 'volatility', 'adx_mean', ...]
                                              ↑ 여기만 수정
```

코드 흐름은 자동으로 따라옴:
```python
ds = RegimeDataset(features)
X_hmm = ds.get_X(feature_cols=config.HMM_FEATURE_COLS)   # 자동 반영
```

## 3-4. 룩어헤드 바이어스 방지 규칙 (강화)

기획서 7장의 ① 항목을 더 구체화:

1. **피처 계산:** `compute_window_features`가 만든 행의 의미는 "i번째 봉 종가까지 본 정보". 이 피처는 i+1번째 봉부터 사용 가능.
2. **라벨 매칭:** Phase 2에서 HMM이 만든 라벨을 `set_labels()`로 주입한 뒤, "다음 윈도우 라벨 예측" 문제로 만들 때 `get_y(shift=-1)` 사용.
3. **자동 검증:** `tests/test_hmmfeatures.py`의 `test_no_lookahead_window_features`가 이를 자동 검증함. **Phase 2에서 새 모듈 추가 시 같은 패턴의 테스트를 작성할 것.**

## 3-5. StandardScaler 적용 여부 (Phase 2 결정 사항)

**기획서 4-2:** "다자산 적용 시 StandardScaler 권장" — 다자산 맥락에서만 명시.

**Phase 1에서 추가 관찰:**
- 시각화 결과 BTC 단일 자산이라도 시간에 따라 volatility/slope의 절대 스케일이 변함 (2020 → 2025 변동성 감소)
- HMM이 같은 "Bull 국면"인데도 시점에 따라 다른 분포로 학습할 수 있음

**Phase 2에서의 결정 사항:**
- (a) StandardScaler 적용 후 학습
- (b) 적용 안 함 (기획서 초기값 그대로)
- (c) 두 방식 모두 학습 후 비교

→ 사용자와 상의 후 결정. Phase 2 시작 시 명시적으로 물어볼 것.

## 3-6. 단위 테스트 컨벤션

- 위치: `Coin-trader-main/tests/`
- 파일명: `test_*.py` (예: `test_hmmfeatures.py`, Phase 2는 `test_hmmlabeler.py` 권장)
- 도구: `pytest`
- 합성 데이터 헬퍼는 각 테스트 파일 안에 (재사용 안 하니 추상화 불필요)

## 3-7. 검증 스크립트 컨벤션

- 위치: `strategy/HMM_strategy/scripts/`
- 백테스트 흐름과 완전 분리
- CLI 인자 지원 (`argparse`)
- 콘솔 텍스트 출력 + matplotlib 그래프
- Phase 2: `verify_hmm_labels.py` 같은 식으로 추가 권장

---

# 4. Phase 2 시작 시 알아야 할 것 (실전 가이드)

## 4-1. Phase 2의 목표 (기획서 6장 기준)

- [ ] `regime/hmm_labeler.py` 구현
  - Baum-Welch 학습 (Random Restart 30회)
  - K-means 초기화
  - BIC 기반 상태 수 선택 (2~5 중 최적)
  - Viterbi 라벨 추출
  - 상태-국면 자동 매핑 (`cum_return` 평균 기준)
- [ ] BTC 데이터로 HMM 학습 테스트
- [ ] 국면 분포 시각화 (`scripts/verify_hmm_labels.py` 신규 작성)

## 4-2. Phase 2 진입 시 권장 작업 순서

1. **환경 점검:** `pip3 show hmmlearn` — 없으면 `pip3 install hmmlearn`
2. **기존 테스트 확인:** `pytest tests/test_hmmfeatures.py` — 34개 통과해야 함 (회귀 점검)
3. **Phase 1 → Phase 2 인계 점검 코드 (이미 작동 확인됨):**
   ```python
   from strategy.HMM_strategy import config
   from strategy.HMM_strategy.features.resampler import load_and_resample
   from strategy.HMM_strategy.features.window_features import compute_window_features
   from strategy.HMM_strategy.regime.regime_dataset import RegimeDataset

   df = load_and_resample(config.DATA_PATH, timeframe=config.TIMEFRAME)
   features = compute_window_features(df, window_size=config.WINDOW_SIZE,
                                       adx_period=config.ADX_PERIOD,
                                       r2_period=config.R2_PERIOD)
   ds = RegimeDataset(features)
   X_hmm = ds.get_X(feature_cols=config.HMM_FEATURE_COLS)
   # → X_hmm.shape: (~13,000, 5)  ← Phase 2의 HMM 학습 입력
   ```
4. **HMMLabeler 클래스 설계** (사용자에게 먼저 보고 OK 받기)
5. **단위 테스트 먼저 작성** (TDD 방식 권장)
6. **시각화 스크립트로 결과 확인**

## 4-3. Phase 2에서 만들 인터페이스 권장 시그니처

```python
# strategy/HMM_strategy/regime/hmm_labeler.py
class HMMLabeler:
    def __init__(
        self,
        n_states: int = 3,                # config.N_STATES
        n_iter: int = 200,                # config.HMM_N_ITER
        n_random_restart: int = 30,       # config.HMM_RANDOM_RESTART
        covariance_type: str = 'diag',    # config.HMM_COVARIANCE_TYPE
        random_state: int = 42,
    ): ...

    def fit(self, X: np.ndarray) -> None: ...
    def predict(self, X: np.ndarray) -> np.ndarray:        # Viterbi 라벨
    def predict_proba(self, X: np.ndarray) -> np.ndarray:  # 국면별 확률
    def save(self, path: str) -> None: ...
    def load(self, path: str) -> None: ...

    # 부가 메서드 (기획서 4-2)
    def select_n_states_by_bic(self, X, candidates=range(2, 6)) -> int: ...
    def map_states_to_regimes(self, features_df, state_col_name) -> dict:
        """Bull(0) / Side(1) / Bear(2)로 자동 매핑.
        cum_return 평균 가장 높은 상태 → Bull, 가장 낮은 → Bear."""
```

## 4-4. 이 보고서에 없는 정보가 필요할 때

- 코드 동작 세부: 해당 파일을 읽어보면 됨 (모든 파일에 docstring 충실히 작성됨)
- 설계 의도: `HMM_regime_plan.md` 원본 기획서 참조
- Phase 1 진행 중 사용자와의 결정 맥락: 이 보고서가 충분 (재구성 가능)

## 4-5. 사용자 컨텍스트 (Phase 2 진행 시 참고)

- **사용자 코딩 수준:** 초보 → 코드 설명을 자세히, 비유 활용
- **언어:** 한국어
- **수정 전 확인 필수:** "코드를 수정할 예정이라면, 어떻게 수정할 지와 수정을 실제로 실행할지 말지를 항상 물어볼 것" (프로젝트 instruction)
- **컨벤션:**
  - 함수는 항상 인자로 파라미터 받기 (Pattern B)
  - config.py는 기본값 모음집
  - 모든 새 모듈에 단위 테스트 작성
  - 검증 스크립트는 `scripts/`에 분리

---

# 5. 마무리 — Phase 1 종료 선언

- ✅ 패키지 골격 + 6개 핵심 코드 파일 작성
- ✅ 34개 단위 테스트 전부 통과
- ✅ 룩어헤드 바이어스 자동 검증 통과
- ✅ 실제 BTC 데이터로 9개 피처 직관 점검 완료
- ✅ 상관계수 히트맵 + VIF 분석으로 HMM 입력 5개 피처 확정
- ✅ Phase 2 인계 가능 상태

**다음 단계:** 새 대화창에서 Phase 2 (HMM Regime Labeler) 시작.
