# HMM 기반 국면 분류 알파 기획서

**작성일:** 2026-04-23  
**최종 수정:** 2026-04-23 (탭2 피드백 반영)  
**프로젝트:** SNU Quant — HMM 기반 확률적 국면 분류 알파  
**대상 시장:** BTC/USDT (추후 ETH/SOL/XRP 확장 예정)  
**기준 타임프레임:** 4시간봉

---

## 1. 프로젝트 개요

### 1-1. 핵심 아이디어

기존 알파(Donchian + ADX/R²)는 국면을 **이진 판단(Bull or Bear)**으로 처리했다. 새 알파는 이를 확률로 대체한다.

> "다음 10일이 Bull일 확률 70%, Bear일 확률 20%, Side일 확률 10%"  
> → 포지션 비중을 이 확률에 비례해서 배분

### 1-2. 기대 효과

- 국면 전환 경계에서 포지션을 부드럽게 조정 → 급격한 방향 전환으로 인한 손실 감소
- Hard signal 대비 변동성(MDD) 감소 기대
- 여러 분류기의 판단을 통합해 단일 분류기보다 강건한 신호 생성

### 1-3. 전략 운영 방식 (2가지 방향 모두 지원)

**방향 I — 국면분류기 + Donchian 분리 방식 (권장)**

국면분류기(HMM + Meta Model)가 현재 국면을 판단하고, 실제 매매 신호는 기존 Donchian 알고리즘이 담당하는 방식이다.

- Bull 판단 → Donchian 롱 신호만 허용 (상승 추세 추종)
- Bear 판단 → Donchian 숏 신호만 허용 (하락 추세 추종)
- Side 판단 → 반대매매(counter-trend) 로직 작동

이 방식은 기존 `Portfolio.py`를 수정 없이 그대로 사용 가능하다. 포지션 변환도 Donchian 브레이크아웃 시점에만 발생하므로 수수료 문제가 제한적이다.

**방향 II — 확률 비중 직접 포지셔닝 (추후 고려)**

국면 확률(P(Bull), P(Bear))을 직접 포지션 비중으로 변환하는 방식. `Portfolio.py`가 현재 정수(0/1/-1)만 지원하므로 구현 전 포트폴리오 모듈 수정이 필요하다.

### 1-4. 포지션 사이징 방식 (방향 II 선택 시)

**방식 A — 순 포지션 (Net Position, 기본값)**
```
순 포지션 = P(Bull) - P(Bear)
예: P(Bull)=0.7, P(Bear)=0.2 → 순 포지션 = +0.5 (50% 롱)
예: P(Bull)=0.2, P(Bear)=0.6 → 순 포지션 = -0.4 (40% 숏)
```
한 방향 포지션만 보유 → 수수료 절감, 단순한 관리

**방식 B — 분리 포지션 (Dual Position, 선택)**
```
롱 비중 = P(Bull), 숏 비중 = P(Bear)
예: P(Bull)=0.7, P(Bear)=0.2 → 롱 70% + 숏 20% 동시 보유
```
각 방향에 독립적으로 베팅 → 수수료 증가, 정교한 헤징 가능

---

## 2. 전체 아키텍처

```
[Raw Data]
    │  BTC/ETH/SOL/XRP 4시간봉 OHLCV + 펀딩비
    ▼
[Feature Engineering Module]  ──────────────────────────────┐
    │  롤링 윈도우(W개 캔들) 단위 요약 피처 계산              │
    │  ex) 누적수익률, 변동성, ADX, R², MDD, 기울기 등       │
    ▼                                                        │
[HMM Regime Labeler]                                         │
    │  Baum-Welch 학습 → Viterbi 국면 라벨 추출              │
    │  출력: 각 윈도우 → Bull(0) / Side(1) / Bear(2)         │
    ▼                                                        │
[Base Classifiers]  ◄────────────────────────────────────────┘
    │  ADX 분류기, R² 분류기, (향후 추가 가능)
    │  각 윈도우에 대한 국면 판단 출력
    ▼
[Meta Model]
    │  Base Classifier 출력 + 윈도우 피처 → P(Bull/Side/Bear)
    │  초기: 로지스틱 회귀 → 추후: XGBoost / 신경망
    ▼
[Position Sizer]
    │  확률 → 포지션 비중 변환 (방식 A or B 선택)
    ▼
[Signal Generator]  ──→  generate_signals() 반환
    │  기존 BaseStrategy 인터페이스 호환
    ▼
[Backtester]
    │  기존 Engine / Portfolio / Report 그대로 사용
    ▼
[Performance Report]
```

---

## 3. 파일 및 폴더 구조

```
Coin-trader-main/
│
├── backtester/
│   ├── engine.py                        # 기존 (수정 없음)
│   ├── portfolio.py                     # 기존 (수정 없음)
│   ├── portfolio_continuous.py          # ★ 신규: float 포지션 비중 지원
│   └── backtester_hmm.py               # ★ 신규: HMM 전략 전용 백테스터
│
└── strategy/
    ├── base.py                          # 기존 (수정 없음)
    ├── donchian_breakout.py             # 기존 (수정 없음)
    ├── donchian_adx_r2.py               # 기존 (수정 없음)
    │
    └── HMM_strategy/                   # ★ 새로 추가되는 패키지
        ├── __init__.py
        ├── strategy.py                  # HMMStrategy (메인 진입점)
        │
        ├── features/
        │   ├── __init__.py
        │   └── window_features.py       # 롤링 윈도우 피처 계산
        │
        ├── regime/
        │   ├── __init__.py
        │   ├── hmm_labeler.py           # HMM 학습 + Viterbi 라벨링
        │   └── regime_dataset.py        # 윈도우-라벨 데이터셋 생성
        │
        ├── classifiers/
        │   ├── __init__.py
        │   ├── base_classifier.py       # 분류기 추상 베이스 클래스
        │   ├── adx_classifier.py        # ADX 기반 분류기 (기존 로직 래핑)
        │   ├── r2_classifier.py         # R² 기반 분류기 (기존 로직 래핑)
        │   └── (추후 추가 가능)
        │
        ├── meta_model/
        │   ├── __init__.py
        │   ├── base_meta_model.py       # 메타 모델 추상 베이스 클래스
        │   ├── logistic_meta_model.py   # 로지스틱 회귀 메타 모델
        │   ├── xgboost_meta_model.py    # XGBoost 메타 모델 (추후)
        │   └── nn_meta_model.py         # 신경망 메타 모델 (추후)
        │
        └── position/
            ├── __init__.py
            └── sizer.py                 # 확률 → 포지션 비중 변환
```

---

## 4. 모듈별 상세 설계

### 4-1. Feature Engineering (`window_features.py`)

**입력:** 4시간봉 OHLCV DataFrame  
**출력:** 윈도우 단위 피처 DataFrame (각 행 = 윈도우 하나)

| 피처명 | 계산 방법 | 채택 이유 및 알파 영향 |
|--------|-----------|----------------------|
| `cum_return` | 윈도우 내 누적 수익률 | **국면의 방향을 직접 반영**. Bull에서 양수, Bear에서 음수. HMM 상태 해석(Bull↔Bear 매핑)의 1차 기준이 됨. |
| `volatility` | 수익률 표준편차 | **Bear/전환 구간에서 급등**. 공포 장에서 급등락이 많아 변동성이 1.5~2배 상승. VIX와 동일한 역할. |
| `adx_mean` | 윈도우 내 ADX 평균 | **추세 강도 측정**. ADX 25 이상 = 추세 존재, 이하 = 횡보. Bull/Bear는 ADX 높고 Side는 낮음. 기존 분석에서 유효성 검증됨. |
| `r2_mean` | 윈도우 내 R² 평균 | **가격 움직임의 선형성**. 추세장(Bull/Bear)에서 높고 횡보장(Side)에서 낮음. ADX와 상보적으로 작동. |
| `adx_end` | 윈도우 끝 시점 ADX | **현재 시점의 추세 강도** (mean은 과거 평균). 두 값을 함께 쓰면 추세가 지속 중인지 약해지는 중인지 구분 가능. |
| `r2_end` | 윈도우 끝 시점 R² | **현재 시점의 선형성**. `adx_end`와 마찬가지로 최근 상태를 포착. |
| `slope` | 선형 회귀 기울기 | **방향 + 속도 동시 포착**. cum_return이 "얼마나 벌었나"라면, slope는 "얼마나 일정한 속도로 오르는가". 추세 지속성 판단에 유용. |
| `max_drawdown` | 최대 낙폭 | **하락 강도의 직접 지표**. Bear 구간에서 크고 깊은 낙폭, Side에서는 얕은 낙폭, Bull에서는 낙폭 거의 없음. |
| `up_candle_ratio` | 상승 캔들 비율 | **단순하지만 노이즈에 강함**. Bull에서 약 60%+ 양봉, Bear에서 40%- 양봉. 다른 피처가 불안정할 때 보완 역할. |

**파라미터:**
```python
WINDOW_SIZE  = 60   # 판단 기준 윈도우 크기 (캔들 수, 4시간봉 기준 10일)
PREDICT_SIZE = 60   # 예측 대상 윈도우 크기 (캔들 수)
STEP_SIZE    = 1    # 롤링 스텝 (1 = 1캔들씩 이동)
```

---

### 4-2. HMM Regime Labeler (`hmm_labeler.py`)

**역할:** 과거 데이터의 각 윈도우에 국면 라벨(Bull/Side/Bear) 자동 부착

**학습 방식:**
- 입력: 윈도우 피처 행렬 (n_windows × n_features)
- 알고리즘: Gaussian HMM (hmmlearn 라이브러리)
- 학습: Baum-Welch (n_iter=200, Random Restart 30회)
- 초기화: K-means 결과를 초기 평균으로 사용 + 도메인 지식 (아래 초기값 참조)
- 상태 수: `n_states=3` (BIC로 2~5 중 최적 선택)
- 라벨 추출: Viterbi 알고리즘

**권장 초기값 및 근거:**

#### 전이 행렬 (Transition Matrix)

```
         → Bull   → Side   → Bear
Bull   [  0.85,   0.12,   0.03  ]
Side   [  0.08,   0.84,   0.08  ]
Bear   [  0.03,   0.12,   0.85  ]
```

각 행의 값을 이렇게 설정한 이론적 근거는 다음과 같다.

**대각선 값 (0.84~0.85) — 국면 지속성(Regime Persistence):** 금융시장 국면은 한번 진입하면 상당 기간 유지되는 경향이 강하다. 이는 트렌드 추종자들이 가격을 기존 방향으로 밀어붙이고, 변화에는 정보 처리 지연이 생기기 때문이다. Ang & Bekaert(2002), Hamilton(1989)의 MS-VAR 연구에서 이 패턴이 일관되게 확인된다. 대각선 값 0.84~0.85는 "평균적으로 6~7봉 이상 국면이 지속"됨을 의미한다 (기댓값 = 1 / (1 - 0.85) ≈ 6.7봉 = BTC 4시간봉 기준 약 27시간).

**Bull/Bear의 직접 전환 확률 (0.03) — 완충 역할의 Side 구간:** Bull에서 Bear로, 또는 Bear에서 Bull로의 직접 전환은 실제로 매우 드물다. 대부분의 전환은 횡보(Side)를 거쳐 이루어지며, 이는 시장이 방향을 잃었다가 새로운 방향을 찾는 패턴이다. ADX/R² 비교 분석 리포트에서도 이 구조가 관찰된다.

**Side 행의 대칭성 (0.08 / 0.08) — 횡보의 방향 중립성:** 횡보 국면에서 다음에 Bull로 갈 확률과 Bear로 갈 확률이 같다고 설정했다. 횡보는 본질적으로 방향성이 없으므로 대칭 설정이 적절하다.

#### 방출 분포 초기 평균값 (Emission Means)

| 상태 | cum_return | volatility | adx_mean | r2_mean | slope | max_drawdown | up_candle_ratio |
|------|-----------|-----------|---------|--------|-------|-------------|----------------|
| **Bull** | +0.035 | 0.012 | 35 | 0.65 | +0.0005 | -0.02 | 0.58 |
| **Side** | 0.000 | 0.009 | 20 | 0.35 | 0.000 | -0.015 | 0.50 |
| **Bear** | -0.035 | 0.018 | 32 | 0.60 | -0.0005 | -0.05 | 0.42 |

각 값의 근거:

**cum_return (±0.035):** 60봉(10일) 윈도우에서 Bull/Bear 구간의 대표적인 누적 수익률. 3.5%는 10일 동안 강한 추세가 지속될 때의 최솟값 수준으로 설정.

**volatility (Bull: 0.012, Side: 0.009, Bear: 0.018):** Side 변동성을 기준(1.0)으로 Bull은 1.33배, Bear는 2.0배로 설정. 이 비율은 BTC 데이터에서 도출됐지만, 실제로는 자산 종류에 관계없이 Bear 구간에서 변동성이 상승하는 패턴은 보편적이다(공포지수 VIX와 시장 하락의 음의 상관관계). **다만 절댓값(0.009, 0.012, 0.018)은 BTC에 특화된 수치**로, 주식이나 다른 코인에 적용할 때는 해당 자산의 역사적 변동성 평균에 맞춰 조정 필요.

**adx_mean (Bull: 35, Side: 20, Bear: 32):** ADX 25 기준으로 추세/횡보 구분. Bear도 강한 추세이므로 Bull과 유사한 ADX 수준으로 설정. 기존 ADX 분석 리포트에서 실증 확인됨.

**max_drawdown (Bull: -0.02, Side: -0.015, Bear: -0.05):** Bear에서 낙폭이 2~3배 커지는 패턴. 이 비율은 자산 종류에 관계없이 범용적으로 적용 가능한 상대적 관계다.

#### 다자산 적용 시 초기값 범용성에 대한 주의사항

**"초기값이 큰 의미가 없는가?"에 대한 답변:**

결론부터 말하면 **초기값의 영향은 제한적이며, 특히 Random Restart 30회를 사용하면 거의 무시 가능**하다.

이유는 다음과 같다.
- Baum-Welch는 EM 알고리즘으로, 초기값에 관계없이 국소 최적해(local optimum)로 수렴한다
- Random Restart 30회를 통해 여러 초기값에서 시작해 최고 로그 가능도를 선택하므로, 특정 초기값이 나빠도 다른 시작점이 좋은 해를 찾아준다
- K-means 초기화가 이미 데이터 기반으로 합리적인 시작점을 제공한다

**그럼에도 불구하고 도메인 지식 초기값을 쓰는 이유:**
- 30회 중 일부 런이 좋은 초기점에서 시작하게 되면 전체 수렴 속도가 빨라지고, 로그 가능도가 더 높은 해를 찾을 확률이 높아진다
- 완전 랜덤 초기화보다 "합리적인 영역"에서 시작하는 게 낫다

**주식/다른 코인 적용 시 실용적 권고사항:**
- 전이 행렬 초기값 → 그대로 사용 가능 (비율 기반, 자산 중립적)
- cum_return, slope, up_candle_ratio, max_drawdown의 비율 관계 → 그대로 사용 가능
- **volatility, adx 절댓값 → 해당 자산의 역사적 평균으로 스케일링 필요**
- 또는 처음부터 피처를 정규화(StandardScaler)한 뒤 초기값도 정규화 공간에서 제시 → 이 방법이 다자산에 가장 범용적

**상태 해석 자동화:**
- 학습 후 각 상태의 `cum_return` 평균값 기준으로 자동 매핑
- `cum_return` 가장 높은 상태 → Bull
- `cum_return` 가장 낮은 상태 → Bear
- 나머지 → Side

**주요 메서드:**
```python
class HMMLabeler:
    def fit(self, X: np.ndarray) -> None
    def predict(self, X: np.ndarray) -> np.ndarray        # Viterbi 라벨
    def predict_proba(self, X: np.ndarray) -> np.ndarray  # 국면별 확률
    def save(self, path: str) -> None
    def load(self, path: str) -> None
```

---

### 4-3. Base Classifiers (`classifiers/`)

**역할:** 기존 ADX/R² 분류기를 윈도우 단위 판단으로 래핑

**추상 베이스 클래스:**
```python
class BaseClassifier(ABC):
    @abstractmethod
    def predict(self, window_df: pd.DataFrame) -> int:
        # 반환: 1(Bull), 0(Side), -1(Bear)
        pass

    @abstractmethod
    def predict_proba(self, window_df: pd.DataFrame) -> np.ndarray:
        # 반환: [P(Bull), P(Side), P(Bear)]
        pass
```

**확장 방법:** `BaseClassifier`를 상속해서 새 분류기 추가

---

### 4-4. Meta Model (`meta_model/`)

**역할:** Base Classifier들의 출력 + 윈도우 피처 → 최종 국면 확률

**입력 피처 (X):**
```
[ADX 분류기 판단, R² 분류기 판단,          ← Base Classifier 출력
 adx_mean, r2_mean, cum_return, volatility, ← 윈도우 요약 피처
 HMM P(Bull), HMM P(Side), HMM P(Bear),    ← HMM 사후 확률
 마르코프 전이 후 P(Bull), P(Side), P(Bear)] ← 전이 행렬 기반 예측
```

**정답 라벨 (y):**
- 다음 윈도우의 HMM 라벨 (shift(-1) 적용 → 예측 문제로 변환)

**추상 베이스 클래스:**
```python
class BaseMetaModel(ABC):
    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> None

    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> np.ndarray
    # 반환: shape (n_samples, 3) → [P(Bull), P(Side), P(Bear)]

    @abstractmethod
    def save(self, path: str) -> None

    @abstractmethod
    def load(self, path: str) -> None
```

**학습/검증:**
- TimeSeriesSplit(n_splits=5, gap=WINDOW_SIZE)
- 훈련: 2020~2024년 / 검증: 2025년~

---

### 4-5. Position Sizer (`sizer.py`)

**역할:** 메타 모델 확률 출력 → 최종 포지션 비중

```python
class PositionSizer:
    def __init__(self, mode: str = 'net'):
        # mode: 'net' | 'dual'

    def compute(self, proba: np.ndarray) -> dict:
        """
        입력: [P(Bull), P(Side), P(Bear)]
        출력:
          net  모드: {'net': float}         ex) {'net': 0.5}  → 50% 롱
          dual 모드: {'long': float, 'short': float}
        """
```

**방식 A (net):**
```
net = P(Bull) - P(Bear)
범위: -1.0 (100% 숏) ~ +1.0 (100% 롱)
```

**방식 B (dual):**
```
long  = P(Bull)
short = P(Bear)
```

**임계값 필터 (선택적):**
```python
MIN_POSITION_THRESHOLD = 0.1   # |net| < 0.1 이면 포지션 0으로 처리 (노이즈 제거)
REBALANCE_THRESHOLD    = 0.15  # 이전 포지션 대비 변화량 < 0.15 이면 리밸런싱 스킵 (수수료 절감)
```

**리밸런싱 임계값 필터 구현 방식:**
```python
def compute_with_filter(self, proba, prev_position):
    new_position = proba[0] - proba[2]  # P(Bull) - P(Bear)
    if abs(new_position - prev_position) < self.rebalance_threshold:
        return prev_position  # 변화 미미 → 현상 유지
    return new_position
```
> 참고: 방향 I(국면분류기 + Donchian 분리 방식) 채택 시 이 필터의 필요성이 크게 감소함. 포지션 변환이 Donchian 브레이크아웃 시점에만 발생하기 때문.

---

### 4-6. HMM Strategy (`strategy.py`)

기존 `BaseStrategy`를 상속해서 기존 백테스터와 완전 호환.

```python
class HMMStrategy(BaseStrategy):
    def __init__(
        self,
        window_size: int = 60,
        predict_size: int = 60,
        n_states: int = 3,
        meta_model_type: str = 'logistic',  # 'logistic' | 'xgboost' | 'nn'
        position_mode: str = 'net',          # 'net' | 'dual'
        min_threshold: float = 0.1,
        rebalance_threshold: float = 0.05,   # 포지션 변화 임계값 (수수료 절감)
        classifiers: list = None,            # BaseClassifier 인스턴스 목록
    )

    def fit(self, df: pd.DataFrame) -> None:
        # 전체 학습 파이프라인 실행

    def generate_signals(self, df: pd.DataFrame) -> np.ndarray:
        # float 배열(-1.0 ~ +1.0) 반환 → EngineHMM에서 처리
        # 방향 I (국면분류기+Donchian 분리): int8 배열 반환 → 기존 Engine과 호환
        # 방향 II (확률 비중): float 배열 반환 → EngineHMM + PortfolioContinuous 사용
```

---

## 5. 데이터 흐름 상세

```
[원본 4시간봉 데이터]
        ↓
[윈도우 피처 계산]
  window_1: [cum_ret=+3.2%, vol=1.1%, adx=34.2, r2=0.71, ...]
  window_2: [cum_ret=+2.8%, vol=1.0%, adx=35.1, r2=0.73, ...]
  ...
        ↓
[HMM 학습 + Viterbi 라벨링]
  window_1: Bull (0)
  window_2: Bull (0)
  window_3: Side (1)
  ...
        ↓
[라벨 1 스텝 시프트 → 예측 문제로 변환]
  X = window_1 피처  →  y = window_2 라벨
  X = window_2 피처  →  y = window_3 라벨
  ...
        ↓
[Base Classifier 출력 추가]
  X += [ADX 판단, R² 판단, HMM 확률, ...]
        ↓
[메타 모델 학습 (TimeSeriesSplit)]
        ↓
[추론: 현재 윈도우 → P(Bull), P(Side), P(Bear)]
        ↓
[Position Sizer → 포지션 비중]
        ↓
[generate_signals() → 기존 Engine 실행]
```

---

## 6. 구현 단계별 로드맵

### Phase 1 — 기반 인프라 (1주차)
- [ ] `HMM_strategy/` 패키지 구조 생성
- [ ] `window_features.py` 구현 및 단위 테스트
- [ ] `regime_dataset.py` 구현 (윈도우-라벨 데이터셋 생성)

### Phase 2 — HMM 모듈 (2주차)
- [ ] `hmm_labeler.py` 구현
  - Baum-Welch 학습 (Random Restart)
  - K-means 초기화
  - BIC 기반 상태 수 선택
  - Viterbi 라벨 추출
  - 상태-국면 자동 매핑
- [ ] BTC 데이터로 HMM 학습 테스트
- [ ] 국면 분포 시각화 (기존 visualizer 활용)

### Phase 3 — 분류기 + 메타 모델 (3주차)
- [ ] `base_classifier.py` 추상 클래스 구현
- [ ] `adx_classifier.py`, `r2_classifier.py` 구현 (기존 코드 래핑)
- [ ] `base_meta_model.py` 추상 클래스 구현
- [ ] `logistic_meta_model.py` 구현
  - TimeSeriesSplit 학습/검증
  - 계수 시각화 (어떤 분류기가 중요한지)

### Phase 4 — 포지션 사이징 + 전략 통합 (4주차)
- [ ] `sizer.py` 구현 (net / dual 모드)
- [ ] `strategy.py` 통합 구현
- [ ] 기존 Engine으로 백테스트 실행
- [ ] 기존 Donchian 전략과 성능 비교

### Phase 5 — 고도화 (추후)
- [ ] XGBoost 메타 모델 추가
- [ ] 신경망 메타 모델 추가
- [ ] ETH/SOL/XRP 적용
- [ ] 롤링 리트레이닝 (주기적 재학습)
- [ ] 실시간 추론 모듈

---

## 7. 핵심 설계 원칙

**① 룩어헤드 바이어스 철저 방지**
- 모든 피처 계산: `shift(1)` 적용
- 라벨: 항상 다음 윈도우 라벨을 y로 사용
- 학습/검증: TimeSeriesSplit + gap=WINDOW_SIZE

**② 기존 인프라와의 완전 호환**
- `BaseStrategy` 상속 → 기존 `Engine`, `Portfolio`, `Report` 수정 없이 사용
- 기존 ADX/R² 필터 로직은 수정 없이 래핑해서 재사용
- `Portfolio.py`는 현재 정수 포지션(0/1/-1)만 지원. 방향 I(국면분류기+Donchian 분리 방식) 채택 시 수정 불필요. 방향 II(확률 비중 직접 포지셔닝) 채택 시 `Portfolio.py` 수정 필요.

**③ 확장성 최우선**
- 모든 핵심 컴포넌트가 추상 베이스 클래스 기반
- 새 분류기: `BaseClassifier` 상속 후 2개 메서드만 구현
- 새 메타 모델: `BaseMetaModel` 상속 후 3개 메서드만 구현
- 포지션 모드: `sizer.py`의 `mode` 파라미터 하나로 전환

**④ 모듈 단위 테스트 가능 구조**
- 각 모듈이 독립적으로 입출력 검증 가능
- 피처 계산 → HMM 라벨링 → 메타 모델 → 포지션 순서로 단계별 검증

---

## 8. 주요 라이브러리

| 라이브러리 | 용도 | 설치 |
|-----------|------|------|
| `hmmlearn` | HMM 학습 및 추론 | `pip install hmmlearn` |
| `scikit-learn` | 로지스틱 회귀, K-means, TimeSeriesSplit | 이미 설치됨 |
| `xgboost` | XGBoost 메타 모델 (Phase 5) | `pip install xgboost` |
| `numpy`, `pandas` | 데이터 처리 | 이미 설치됨 |

---

## 9. 성능 평가 지표

기존 백테스터의 Report 모듈 활용:

| 지표 | 설명 |
|------|------|
| CAGR | 연평균 수익률 |
| Sharpe Ratio | 위험 대비 수익 |
| Max Drawdown | 최대 낙폭 |
| Win Rate | 승률 |
| 기존 Donchian 대비 개선율 | 핵심 비교 기준 |

**비교 기준선 전략 목록:**

| 전략 | 구현 상태 | 특징 | 비교 목적 |
|------|----------|------|----------|
| **BTC Buy & Hold** | ✅ 구현됨 | 매수 후 보유 | 가장 기본적인 기준선. 여기를 못 이기면 전략 의미 없음 |
| **DonchianADXR2Strategy** | ✅ 구현됨 | 현재 알파 | 직접적 비교 대상 |
| **이동평균 크로스 (20/60봉)** | 🔲 추가 예정 | 단순 추세추종 | 가장 단순한 추세추종 대표 전략 |

---

*이 기획서는 코드 작성 진행에 따라 수정/보완될 수 있음.*
