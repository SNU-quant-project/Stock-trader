# Phase 2 작업 보고서 — HMM Regime Labeler

**작성일:** 2026-05-03
**대상 Phase:** Phase 2 (HMM 모듈)
**연결 문서:** `SNU Quant/HMM_regime_plan.md`, `SNU Quant/phase1_work_report.md`

---

## 📌 이 문서의 목적과 사용법

Phase 3 작업을 새 대화창에서 시작하기 위한 인계 자료. Phase 3 진행 시 다음 세 문서를 함께 읽음:

1. `HMM_regime_plan.md` — 전체 프로젝트 큰 그림
2. `phase1_work_report.md` — 피처 엔지니어링 인계
3. `phase2_work_report.md` (이 문서) — HMM 라벨러 인계 + Phase 2 결정사항

**문서 간 충돌 시 이 보고서가 우선** (가장 최신).

---

# 1. Phase 2에서 완료된 내용

## 1-1. 새로 추가된 파일 트리

```
Coin-trader-main/
│
├── strategy/HMM_strategy/
│   ├── config.py                          ★ 수정 (rolling scaler 변수 추가)
│   ├── features/
│   │   └── scaling.py                     ★ 신규 — RollingStandardScaler
│   ├── regime/
│   │   └── hmm_labeler.py                 ★ 신규 — HMMLabeler 클래스
│   └── scripts/
│       └── verify_hmm_labels.py           ★ 신규 — 3-모드 비교 검증
│
└── tests/
    └── test_hmmlabeler.py                 ★ 신규 — 23개 단위 테스트
```

★ = Phase 2에서 새로 만들어진/수정된 파일.

## 1-2. 각 파일의 역할

### `regime/hmm_labeler.py` — 핵심 클래스

```python
from strategy.HMM_strategy.regime.hmm_labeler import (
    HMMLabeler, BULL, SIDE, BEAR, REGIME_NAMES,
)

labeler = HMMLabeler(
    n_states=3,
    n_iter=200,
    n_random_restart=30,
    covariance_type='diag',
    random_state=42,
)
labeler.fit(X, cum_return)        # 학습 + 자동 매핑까지 한 번에
labels = labeler.predict(X)        # 0=Bull, 1=Side, 2=Bear
proba  = labeler.predict_proba(X)  # shape (n, 3), 컬럼 순서 [Bull, Side, Bear]
labeler.save("hmm.joblib")
labeler.load("hmm.joblib")

# 부가 — BIC로 n_states 선택
best_n, bic_dict = labeler.select_n_states_by_bic(X, candidates=[2,3,4,5])
```

내부 동작:
1. K-means로 means 초기화 (각 restart마다 다른 시드)
2. Random Restart 30회 → 수렴한 모델 중 best score 채택
3. fit 안에서 cum_return 평균 기준으로 상태→Bull/Side/Bear 자동 매핑
4. predict()는 매핑된 0/1/2 직접 반환

**중요 — 스케일링은 호출자 책임**: HMMLabeler 자체는 정규화 안 함. 호출자가 `none` / `global` / `rolling` 중 선택해서 X를 미리 처리하고 전달해야 함.

### `features/scaling.py` — RollingStandardScaler

```python
from strategy.HMM_strategy.features.scaling import RollingStandardScaler

scaler = RollingStandardScaler(window=2200)  # 4h 기준 1년
X_scaled = scaler.fit_transform(features[HMM_FEATURE_COLS])
# 처음 (window-1)행은 NaN — 호출자가 dropna
```

각 시점 t의 정규화에 `[t-window+1, t]` 구간만 사용 → 룩어헤드 안전, 시간 드리프트 해결.

### `scripts/verify_hmm_labels.py` — 3-모드 비교

```bash
# 기본 (3-way 비교, 기본 30 restart)
python -m strategy.HMM_strategy.scripts.verify_hmm_labels

# 빠른 검증
python -m strategy.HMM_strategy.scripts.verify_hmm_labels --n-restart 5

# 헤드리스 + PNG 저장
python -m strategy.HMM_strategy.scripts.verify_hmm_labels --no-show \
    --save-overlay overlay.png --save-stats stats.png

# 특정 모드만
python -m strategy.HMM_strategy.scripts.verify_hmm_labels --modes rolling
```

### `config.py` 추가 변수

```python
SCALER_MODE = 'rolling'           # 'none' | 'global' | 'rolling'
ROLLING_SCALER_WINDOW = 2200      # 4h 기준 약 1년
```

## 1-3. 단위 테스트 현황

**총 57개 테스트 전부 통과** (`pytest tests/test_hmmfeatures.py tests/test_hmmlabeler.py`)

| 그룹 | 수 | 검증 내용 |
|---|---|---|
| Phase 1 (test_hmmfeatures.py) | 34 | 회귀 — 변경 없음 |
| TestRollingStandardScaler | 7 | 윈도우 NaN, 평균/표준편차, 룩어헤드 안전성, 상수 피처 |
| TestHMMLabelerBasic | 4 | fit/predict, 확률 합=1, 매핑 일관성, 합성 데이터 70%+ 일치 |
| TestHMMLabelerErrors | 6 | NaN/길이/n_states 검증, fit 전 호출 등 예외 |
| TestHMMLabelerSaveLoad | 2 | joblib 라운드트립, config 복원 |
| TestHMMLabelerBIC | 2 | BIC 선택 동작, 부수효과 없음 |
| TestHMMLabelerHistory | 2 | fit_history 무결성 |

## 1-4. 실데이터(BTC 4h) 검증 결과

학습 가능 행 수: **13,590** (15,789 - rolling cold start 2,199)

| 모드 | 학습 시간 | best log-likelihood | Bull% | Side% | Bear% |
|---|---|---|---|---|---|
| none | 2.4초 | 63,093 | 18.6% | 44.6% | 36.8% |
| global | 1.5초 | -74,629 | 22.1% | 47.3% | 30.6% |
| rolling | 1.4초 | -77,131 | 24.6% | 48.2% | 27.1% |

> 시간은 sandbox 환경, 3 restart 기준. 30 restart에서는 약 10배.

**모드 간 일치율 (가장 중요한 발견):**

| | none | global | rolling |
|---|---|---|---|
| none | 1.00 | 0.27 | 0.26 |
| global | 0.27 | 1.00 | 0.87 |
| rolling | 0.26 | 0.87 | 1.00 |

→ **none 모드는 global/rolling과 27%만 일치** = 정규화 없으면 HMM이 스케일 큰 피처(adx_mean 등)에 끌려가 완전히 다르게 학습. **Phase 1 시점 우려가 데이터로 확인됨.**

→ **global vs rolling 87%** = 매우 유사하지만 13% 차이. 이게 시간 드리프트로 인한 차이로 추정.

---

# 2. 진행 과정에서 변경된 사항

기획서/Phase 1 보고서와 다른 결정. **Phase 3 이후는 모두 이 변경을 따른다.**

## 2-1. 스케일러 모드 결정 — 3-way 비교 채택

**Phase 1 보고서 3-5:** "(c) 두 방식 비교" — none vs global StandardScaler

**Phase 2에서 변경:** **3-way 비교**로 확장 (none / global / rolling)

**이유:** 사용자 통찰 — 글로벌 StandardScaler는 과거의 다른 스케일(2018년 BTC 3,000불 vs 2024년 70,000불)이 정규화에 섞여 들어가는 문제가 있음. Rolling 윈도우 기반 정규화가 시간 드리프트를 진짜로 해결함.

**3개 모드의 차이 — 데이터로 확인됨 (1-4 참조).**

## 2-2. Rolling 윈도우 기본값

```python
ROLLING_SCALER_WINDOW = 2200    # 4h 기준 약 1년
```

**선정 근거:** 6개월보다 길어야 장기 Bear 시장(예: 2018년 1년 내내 하락)이 정규화로 흡수되지 않음. 2년은 시간 드리프트 추적 효과 감소.

**튜닝 필요시:** config.py 한 줄만 변경. 학습 가능 행수는 비례해서 변동:
- 6개월 → 약 14,700행
- 1년 → 약 13,500행
- 2년 → 약 11,400행

## 2-3. 모드 비교의 공정성 — 동일 데이터 길이

**결정:** 세 모드 모두 rolling cold start(첫 ~2,200행) 이후 데이터로만 학습/평가.

**이유:** none/global도 자기 최대 데이터(15,789행) 쓰면 불공정 비교가 됨. `verify_hmm_labels.py`의 `prepare_X_for_modes()`가 모든 모드에 동일한 `valid_range = slice(cold_start, n_full)` 적용.

## 2-4. 상태→국면 자동 매핑 — fit 안에서 처리

**기획서 4-3 시그니처:** `map_states_to_regimes(features_df, state_col_name)` 별도 메서드

**Phase 2 변경:** fit() 안에서 자동 매핑까지 끝냄. 사용자는 fit(X, cum_return) 한 번만 호출하면 됨. 매핑 잊을 위험 제거.

**API 차이:** fit이 X 외에 cum_return 1D 배열을 추가로 받음 (X 안의 cum_return 컬럼이 정규화돼 있을 수 있어 별도로 받음).

## 2-5. Random Restart 수렴 실패 처리

**규칙:** 수렴 안 한 모델은 best 후보에서 제외. 30개 모두 실패 시 RuntimeError.

`labeler.fit_history_`에 (idx, score, converged) 기록 보존 — 수렴률 사후 분석 가능.

## 2-6. 검증 스크립트 — Agg 백엔드 자동 전환

`--no-show` 인자가 있으면 matplotlib을 자동으로 Agg 백엔드로 강제. 헤드리스(서버, sandbox) 환경에서 GUI 백엔드 초기화 멈춤 방지.

---

# 3. Phase 3 시작 시 알아야 할 것

## 3-1. Phase 3의 목표 (기획서 6장 기준)

- [ ] `classifiers/base_classifier.py` 추상 클래스 — predict + predict_proba 인터페이스
- [ ] `classifiers/adx_classifier.py` — 기존 ADX 로직을 윈도우 단위 판단으로 래핑
- [ ] `classifiers/r2_classifier.py` — R² 분류기 동일
- [ ] `meta_model/base_meta_model.py` 추상 클래스
- [ ] `meta_model/logistic_meta_model.py` — 로지스틱 회귀
  - 입력: Base Classifier 출력 + 윈도우 피처 + HMM 사후확률 + 마르코프 전이 예측
  - 정답: 다음 윈도우의 HMM 라벨 (shift(-1))
  - 학습: TimeSeriesSplit(n_splits=5, gap=WINDOW_SIZE)
- [ ] 계수 시각화 (어떤 분류기/피처가 메타에 중요한지)
- [ ] 새 검증 스크립트: `scripts/verify_meta_model.py`

## 3-2. Phase 3 진입 시 권장 작업 순서

1. 환경 점검: `pytest tests/test_hmmfeatures.py tests/test_hmmlabeler.py` — 57개 통과해야 함
2. **모드 선택 결정**: 사용자와 상의해 Phase 3에서 사용할 단일 모드 선택
   - 추천: `rolling` (시간 드리프트 해결 + global과 유사한 결과)
   - 또는 `global`만 일단 진행, rolling은 추후
3. HMMLabeler로 BTC 라벨 생성 (선택된 모드로):
   ```python
   labeler = HMMLabeler(...)
   labeler.fit(X, cum_return)
   labels = labeler.predict(X)
   labeler.save("models/hmm_btc.joblib")
   ```
4. Base Classifier 설계 → 사용자 confirm → 구현 → 테스트
5. Meta Model 설계 → 사용자 confirm → 구현 → 테스트
6. 검증 스크립트로 메타 모델 출력 확인

## 3-3. Phase 3에서 만들 인터페이스 권장 시그니처 (기획서 4-3, 4-4 기반)

```python
# strategy/HMM_strategy/classifiers/base_classifier.py
class BaseClassifier(ABC):
    @abstractmethod
    def predict(self, window_df: pd.DataFrame) -> int:
        """반환: 1(Bull), 0(Side), -1(Bear)"""

    @abstractmethod
    def predict_proba(self, window_df: pd.DataFrame) -> np.ndarray:
        """반환: [P(Bull), P(Side), P(Bear)]"""

# strategy/HMM_strategy/meta_model/base_meta_model.py
class BaseMetaModel(ABC):
    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> None: ...

    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """반환: shape (n_samples, 3) → [P(Bull), P(Side), P(Bear)]"""

    @abstractmethod
    def save(self, path: str) -> None: ...

    @abstractmethod
    def load(self, path: str) -> None: ...
```

## 3-4. 룩어헤드 바이어스 방지 — Phase 3에서도 강화

1. Meta 학습 라벨은 **다음 윈도우의 HMM 라벨**: `ds.get_y(shift=-1)` 사용
2. TimeSeriesSplit + gap=WINDOW_SIZE 필수
3. 새 모듈 작성 시 Phase 1 보고서 3-4 룩어헤드 규칙 자동 검증 테스트 같이 작성

## 3-5. 사용자 컨텍스트 (변동 없음 — Phase 1 4-5 참조)

- 코딩 초보 → 자세한 설명, 비유 활용
- 한국어
- **수정 전 확인 필수** — "어떻게 수정할 지" + "실행해도 될지" 항상 물어볼 것
- 컨벤션:
  - Pattern B (config는 기본값 모음, 함수는 인자로 받음)
  - 모든 새 모듈에 단위 테스트
  - 검증 스크립트는 `scripts/`

---

# 4. 마무리 — Phase 2 종료 선언

- ✅ HMMLabeler 클래스 완성 (K-means init, 30 restart, BIC 선택, 자동 매핑, save/load)
- ✅ RollingStandardScaler 완성 (룩어헤드 안전, 상수 피처 처리)
- ✅ 검증 스크립트 — 3-모드 비교, BTC 데이터로 동작 확인
- ✅ 단위 테스트 23개 추가 (Phase 1 + Phase 2 = 57개 전부 통과)
- ✅ 모드 간 일치율 비교로 정규화 효과 실증 (none vs global/rolling = 27%)
- ✅ Phase 3 인계 가능 상태

**다음 단계:** 새 대화창에서 Phase 3 (Base Classifier + Meta Model) 시작.
