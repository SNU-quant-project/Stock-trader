"""
Label Shifter — HMM 라벨 전환 경계를 실제 가격 극점으로 당기는 도구.

────────────────────────────────────────────────────────────────────
배경 (RetrospectiveLabelSmoother의 후속·대체)
────────────────────────────────────────────────────────────────────
Stage 1 lag 분석(analysis/regime_lag/, results/regime_lag_report*.md)에서
HMM Viterbi 라벨이 실제 시장 전환 대비 →Bear 약 3~4거래일, →Bull 약
4~5.5거래일 늦게 전환됨을 정량화했다. 기존 smoother는 |1봉 수익률| 쇼크가
있을 때만 최대 10봉 backdate하므로 이 lag(중앙값 38~72봉)를 못 따라간다.
2026-07-04 사용자 결정으로 기존 smoother를 폐기하고 이 모듈로 대체한다
(HANDOFF §23).

두 방식:
  - 'zigzag' : 종가 x% 반전 확정 시의 국소 고점/저점(독립 기준)까지 당김.
               x=primary 매칭 우선, 실패 시 fallback, 그래도 실패면 원본 유지.
  - 'anchor' : 각 전환에서 과거 L봉 내 극점까지 당김 (비교/보수 버전).

────────────────────────────────────────────────────────────────────
룩어헤드 안전성 (중요)
────────────────────────────────────────────────────────────────────
이 도구는 **학습용 정답지(y) 전용**이다. 예측 입력(X)이나 실시간 추론
경로에 어떤 형태로도 사용 금지. zigzag 극점은 "반전이 x% 확정된 뒤"에만
알 수 있는 사후 정보다.

경계 누수: HMMStrategy.fit() 안에서 호출되면 입력이 학습 df(train window)
뿐이므로, train_end 이후 데이터로만 확정되는 극점은 애초에 생성되지 않는다
→ OOS 정보가 학습 정답지에 스밀 수 없다 (구조적 차단).

────────────────────────────────────────────────────────────────────
경계 충돌 규칙
────────────────────────────────────────────────────────────────────
전환을 시간순으로 처리하며, 당긴 시작점이 직전 전환의 (당겨진) 시작점
+ min_gap봉 이내로 파고들면 그 전환은 당기지 않는다 (직전 국면을
조각내는 것 방지).

사용 예시:
    from strategy.HMM_strategy.regime.label_shifter import shift_labels
    new_labels, events = shift_labels(labels, close_rows, mode='zigzag')
"""

import numpy as np

from strategy.HMM_strategy.regime.hmm_labeler import BULL, SIDE, BEAR

# 기본 파라미터 (Stage 1 분석 결과 기반 — results/regime_lag_report_cowork.md)
DEFAULT_ZZ_PRIMARY = 0.05     # zigzag 매칭 1순위 반전율
DEFAULT_ZZ_FALLBACK = 0.03    # 2순위 (저변동 종목 대응)
DEFAULT_ANCHOR_L = 65         # anchor lookback 봉 수 (수렴 영역)
DEFAULT_MIN_DURATION = 13     # whipsaw 필터: 최소 국면 지속 봉 수 (1거래일)
DEFAULT_MAX_MATCH_DIST = 130  # zigzag 매칭 최대 거리 (봉)
DEFAULT_MIN_GAP = 13          # 경계 충돌 최소 간격 (봉)


# ─── 세그먼트/전환 유틸 ─────────────────────────────────────────

def _segments(labels):
    """[(label, start, end_exclusive), ...] 연속 구간 분해."""
    segs = []
    start = 0
    for i in range(1, len(labels) + 1):
        if i == len(labels) or labels[i] != labels[start]:
            segs.append((int(labels[start]), start, i))
            start = i
    return segs


def whipsaw_filter(labels: np.ndarray, min_duration: int) -> np.ndarray:
    """min_duration봉 미만의 짧은 국면을 이웃 국면에 흡수 (수렴까지 반복)."""
    lab = labels.copy()
    while True:
        segs = _segments(lab)
        short = [s for s in segs if (s[2] - s[1]) < min_duration]
        if not short or len(segs) == 1:
            return lab
        s = min(short, key=lambda x: x[2] - x[1])
        seg_i = segs.index(s)
        absorb = segs[seg_i - 1][0] if seg_i > 0 else segs[seg_i + 1][0]
        lab[s[1]:s[2]] = absorb


def extract_transitions(labels: np.ndarray) -> list:
    """Bull↔Bear 전환만 추출 (Side 경유 포함 = 1회 전환).

    Returns: [(t, direction)] — t는 새 국면 첫 위치, direction='to_bull'|'to_bear'
    """
    segs = [s for s in _segments(labels) if s[0] != SIDE]
    out = []
    for prev, cur in zip(segs[:-1], segs[1:]):
        if prev[0] == cur[0]:
            continue
        out.append((cur[1], "to_bull" if cur[0] == BULL else "to_bear"))
    return out


# ─── zigzag 극점 (확정 봉 포함) ──────────────────────────────────

def zigzag_pivots_confirmed(close: np.ndarray, pct: float) -> list:
    """종가 pct 반전 확정 시의 국소 고점('H')/저점('L') 목록.

    Returns: [(pivot_idx, 'H'|'L', confirm_idx)] — confirm_idx는 반전이
    확정된 봉. 입력 배열 안에서 확정된 극점만 반환되므로, 학습 데이터만
    넘기면 미래(OOS) 확정 극점은 자동 배제된다.
    """
    pivots = []
    direction = 0
    max_i, min_i = 0, 0
    for i in range(1, len(close)):
        if close[i] > close[max_i]:
            max_i = i
        if close[i] < close[min_i]:
            min_i = i
        if direction >= 0 and close[i] <= close[max_i] * (1 - pct):
            pivots.append((max_i, "H", i))
            direction = -1
            min_i = i
        elif direction <= 0 and close[i] >= close[min_i] * (1 + pct):
            pivots.append((min_i, "L", i))
            direction = 1
            max_i = i
    return pivots


# ─── 메인 API ───────────────────────────────────────────────────

def shift_labels(
    labels: np.ndarray,
    close_rows: np.ndarray,
    mode: str = "zigzag",
    zz_primary: float = DEFAULT_ZZ_PRIMARY,
    zz_fallback: float = DEFAULT_ZZ_FALLBACK,
    anchor_lookback: int = DEFAULT_ANCHOR_L,
    min_duration: int = DEFAULT_MIN_DURATION,
    max_match_dist: int = DEFAULT_MAX_MATCH_DIST,
    min_gap: int = DEFAULT_MIN_GAP,
):
    """HMM 라벨의 Bull↔Bear 전환 경계를 가격 극점으로 당긴 새 라벨 생성.

    Args:
        labels: (n,) 정수 라벨 (0=Bull, 1=Side, 2=Bear). 학습 구간 전용!
        close_rows: (n,) labels와 같은 행 단위로 정렬된 종가
                    (윈도우 피처 행이면 close[window_end_idx]).
        mode: 'zigzag' | 'anchor'
        나머지: 모듈 상수 기본값 참조.

    Returns:
        (new_labels, events)
        events: [{'t', 'direction', 'ref', 'shift', 'source', 'skipped'}, ...]

    주의: 반환 라벨은 학습 타깃(y) 전용. X/실시간 경로 사용 금지.
    """
    if mode not in ("zigzag", "anchor"):
        raise ValueError(f"mode must be 'zigzag' or 'anchor', got {mode!r}")
    labels = np.asarray(labels, dtype=np.int64).ravel()
    close_rows = np.asarray(close_rows, dtype=np.float64).ravel()
    if len(labels) != len(close_rows):
        raise ValueError(
            f"labels/close_rows length mismatch: {len(labels)} vs {len(close_rows)}"
        )

    transitions = extract_transitions(whipsaw_filter(labels, min_duration))
    pivots_by_pct = None
    if mode == "zigzag":
        pivots_by_pct = [(p, zigzag_pivots_confirmed(close_rows, p))
                         for p in (zz_primary, zz_fallback)]

    out = labels.copy()
    events = []
    prev_start = -10 ** 9
    for t, direction in transitions:
        new_lbl = BULL if direction == "to_bull" else BEAR
        ref, source = None, None
        if mode == "zigzag":
            want = "H" if direction == "to_bear" else "L"
            for pct, pivots in pivots_by_pct:
                cand = [p for p, k, _c in pivots if k == want and p <= t]
                if cand and (t - cand[-1]) <= max_match_dist:
                    ref, source = cand[-1], f"zigzag{int(pct * 100)}%"
                    break
        else:
            lo = max(0, t - anchor_lookback)
            win = close_rows[lo:t + 1]
            off = int(np.argmax(win)) if direction == "to_bear" else int(np.argmin(win))
            ref, source = lo + off, f"anchorL{anchor_lookback}"

        if ref is None or ref >= t:          # 미매칭 — 원본 유지
            prev_start = t
            continue
        if ref <= prev_start + min_gap:      # 경계 충돌 — 원본 유지
            events.append({"t": t, "direction": direction, "ref": ref,
                           "shift": 0, "source": source, "skipped": "collision"})
            prev_start = t
            continue
        out[ref:t] = new_lbl
        events.append({"t": t, "direction": direction, "ref": ref,
                       "shift": t - ref, "source": source, "skipped": ""})
        prev_start = ref
    return out, events
