"""특정 날짜 시점의 S&P 500 멤버십을 재구성하는 모듈."""

import pandas as pd


def load_data(data_dir="data"):
    current = pd.read_csv(f"{data_dir}/sp500_current.csv")
    current_symbols = set(current["Symbol"].tolist())

    changes = pd.read_csv(f"{data_dir}/sp500_changes.csv", header=[0, 1])
    changes.columns = [
        "_".join(col).strip() if col[0] != col[1] else col[0]
        for col in changes.columns
    ]
    changes["Effective Date"] = pd.to_datetime(changes["Effective Date"])

    return current_symbols, changes


def get_sp500_members_at(date, current_symbols, changes):
    target_date = pd.to_datetime(date)
    members = current_symbols.copy()

    future_changes = changes[changes["Effective Date"] > target_date]

    for _, row in future_changes.iterrows():
        added = row["Added_Ticker"]
        removed = row["Removed_Ticker"]

        if pd.notna(added) and added in members:
            members.discard(added)
        if pd.notna(removed):
            members.add(removed)

    return members


def build_membership_mask(dates, symbols, current_symbols, changes):
    """각 거래일에 그 종목이 S&P 500 멤버였는지를 나타내는 (date × symbol) bool DataFrame.

    백테스트에서 비멤버 구간의 데이터를 가려(편입 전 = 미보유, 방출 후 = 청산)
    point-in-time 유니버스를 재현하는 데 사용한다.

    효율: 멤버십은 변경일 사이에서만 바뀌므로 거래일마다 재계산하지 않고
    각 변경일에서 한 번만 멤버 집합을 갱신한 뒤 구간별로 채운다.
    """
    dates = pd.DatetimeIndex(dates)
    symbols = list(symbols)
    sym_index = {s: i for i, s in enumerate(symbols)}

    # 가장 이른 거래일 시점의 멤버 집합에서 출발, 변경일을 시간순으로 적용
    if len(dates):
        members = get_sp500_members_at(dates.min(), current_symbols, changes)
    else:
        members = current_symbols.copy()

    ch = changes.copy()
    ch = ch.sort_values("Effective Date")

    import numpy as np
    n_dates, n_syms = len(dates), len(symbols)
    arr = np.zeros((n_dates, n_syms), dtype=bool)

    # 변경일 → 그 날부터 적용. 거래일을 순회하며 지나친 변경을 반영.
    change_rows = list(ch.itertuples(index=False))
    ci = 0
    n_changes = len(change_rows)
    # changes 의 컬럼명: Added_Ticker / Removed_Ticker / Effective Date
    eff_col = "Effective Date"
    add_col = "Added_Ticker"
    rem_col = "Removed_Ticker"
    eff_idx = list(ch.columns).index(eff_col)
    add_idx = list(ch.columns).index(add_col)
    rem_idx = list(ch.columns).index(rem_col)

    def _apply_change(row):
        added = row[add_idx]
        removed = row[rem_idx]
        if pd.notna(added):
            members.add(added)        # 편입일 이후 멤버
        if pd.notna(removed):
            members.discard(removed)   # 방출일 이후 비멤버

    for di, d in enumerate(dates):
        while ci < n_changes and change_rows[ci][eff_idx] <= d:
            _apply_change(change_rows[ci])
            ci += 1
        for s in members:
            j = sym_index.get(s)
            if j is not None:
                arr[di, j] = True

    return pd.DataFrame(arr, index=dates, columns=symbols)
