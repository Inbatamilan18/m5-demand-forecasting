"""Step 2: build model features.

Every lag is >= 28 days, so all 28 forecast days can be predicted in one shot
without recursion (no error compounding, much simpler to run).

Run:  python -m src.features
"""
import gc
import numpy as np
import pandas as pd

from src import config as C

def to_str(s: pd.Series) -> pd.Series:
    """Series -> plain numpy object/str series.

    Handles pandas categoricals whose *categories* are Arrow-backed strings,
    which raise `ArrowException: Wrapping X failed` on a naive .astype(str).
    """
    if isinstance(s.dtype, pd.CategoricalDtype):
        cats = np.asarray(s.cat.categories.to_numpy(dtype=object), dtype=object)
        codes = s.cat.codes.to_numpy()
        out = np.where(codes >= 0, cats[codes.clip(0)], None)
        return pd.Series(out, index=s.index, dtype=object)
    return pd.Series(np.asarray(s.to_numpy(), dtype=object), index=s.index)


# Minimum usable lag = distance from the last day of history to the first
# forecast day. For "validation"/"evaluation" that is 1 (lags start at 28).
# For "future" the gap is 28 days, so every lag must be >= 56.
def min_lag(train_end: int) -> int:
    """Smallest lag that is knowable at prediction time.

    `train_end` is the last day with real sales *in the data* (which can be
    earlier than the config value if the Kaggle file is the shorter release).
    """
    first_pred = C.MODES[C.MODE][1]
    return max(C.HORIZON, first_pred - train_end - 1 + C.HORIZON)


def lag_set(train_end: int) -> list[int]:
    m = min_lag(train_end)
    base = [0, 1, 2, 7, 14, 28]
    return [m + b for b in base] + [364]


def data_train_end(df: pd.DataFrame) -> int:
    """Last day that actually carries a sales value."""
    return int(df.loc[df["sales"].notna(), "d_num"].max())


ROLL_WINDOWS = [7, 14, 28, 60, 180]
CAT_FEATURES = ["item_id", "dept_id", "cat_id", "store_id", "state_id",
                "weekday", "event_name_1", "event_type_1",
                "event_name_2", "event_type_2"]


def add_features(df: pd.DataFrame, shift: int | None = None) -> pd.DataFrame:
    """Add lag/rolling/price/calendar features.

    `shift` overrides the automatic lag distance (used by src.backtest, which
    simulates its own gap rather than reading C.MODE).
    """
    df = df.sort_values(["id", "d_num"], kind="stable").reset_index(drop=True)
    g = df.groupby("id", observed=True)["sales"]

    if shift is None:
        train_end = data_train_end(df)
        shift = min_lag(train_end)
        lags = lag_set(train_end)
    else:
        lags = [shift + b for b in [0, 1, 2, 7, 14, 28]] + [364]
    print(f"  lags {lags} (shift={shift}) ...")
    for lag in lags:
        df[f"lag_{lag}"] = g.shift(lag).astype("float32")

    print("  rolling stats ...")
    base = g.shift(shift)
    for w in ROLL_WINDOWS:
        r = base.groupby(df["id"], observed=True).rolling(w, min_periods=1)
        df[f"rmean_{w}"] = r.mean().reset_index(level=0, drop=True).astype("float32")
    for w in [7, 28]:
        r = base.groupby(df["id"], observed=True).rolling(w, min_periods=1)
        df[f"rstd_{w}"] = r.std().reset_index(level=0, drop=True).astype("float32")

    # intermittency: share of zero-sales days recently
    zero = (base == 0).astype("float32")
    df["zero_rate_28"] = (zero.groupby(df["id"], observed=True)
                          .rolling(28, min_periods=1).mean()
                          .reset_index(level=0, drop=True).astype("float32"))
    del base, zero, g
    gc.collect()

    print("  price features ...")
    pg = df.groupby("id", observed=True)["sell_price"]
    df["price_change_w"] = (df["sell_price"] / pg.shift(7) - 1).astype("float32")
    df["price_rel_item"] = (df["sell_price"] /
                            df.groupby("id", observed=True)["sell_price"]
                              .transform("mean")).astype("float32")
    df["price_rel_dept"] = (df["sell_price"] /
                            df.groupby(["dept_id", "d_num"], observed=True)["sell_price"]
                              .transform("mean")).astype("float32")
    del pg
    gc.collect()

    print("  calendar features ...")
    df["dayofweek"] = df["date"].dt.dayofweek.astype("int8")
    df["dayofmonth"] = df["date"].dt.day.astype("int8")
    df["weekofyear"] = df["date"].dt.isocalendar().week.astype("int8")
    df["is_weekend"] = (df["dayofweek"] >= 5).astype("int8")
    df["is_event"] = df["event_name_1"].notna().astype("int8")
    # SNAP flag for the state the store is in
    state = to_str(df["state_id"])
    df["snap"] = np.select(
        [state == "CA", state == "TX", state == "WI"],
        [df["snap_CA"], df["snap_TX"], df["snap_WI"]], default=0
    ).astype("int8")
    df.drop(columns=["snap_CA", "snap_TX", "snap_WI"], inplace=True)

    # days since the item first had a price (proxy for "released yet?")
    first = df.loc[df["sell_price"].notna()].groupby("id", observed=True)["d_num"].min()
    df["days_since_release"] = (df["d_num"] - df["id"].map(first)).astype("float32")
    return df


def feature_columns(df: pd.DataFrame) -> list[str]:
    drop = {"id", "sales", "date", "wm_yr_wk", "d_num"}
    return [c for c in df.columns if c not in drop]


def main() -> None:
    src = C.PROC / f"base_{C.MODE}.parquet"
    print(f"reading {src}")
    df = pd.read_parquet(src)
    df = add_features(df)

    train_end = data_train_end(df)
    if C.TRAIN_TAIL_DAYS:
        df = df[df["d_num"] > train_end - C.TRAIN_TAIL_DAYS].reset_index(drop=True)
    # rows before an item was ever priced carry no information
    df = df[df["sell_price"].notna() | (df["d_num"] > train_end)].reset_index(drop=True)
    df = df[(df["d_num"] <= train_end) |
            (df["d_num"] >= C.MODES[C.MODE][1])].reset_index(drop=True)

    out = C.PROC / f"features_{C.MODE}.parquet"
    df.to_parquet(out, index=False)
    print(f"wrote {out}  rows={len(df):,}  cols={len(df.columns)}")


if __name__ == "__main__":
    main()
