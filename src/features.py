"""Step 2: build model features.

Every lag is >= 28 days, so all 28 forecast days can be predicted in one shot
without recursion (no error compounding, much simpler to run).

Run:  python -m src.features
"""
import gc
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

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
    base = g.shift(shift).to_numpy(dtype="float32")

    # pandas' groupby(...).rolling() allocates several int64 index arrays the
    # length of the whole frame, which exhausts RAM at ~22M rows. The frame is
    # already sorted by (id, d_num), so compute each window with cumulative
    # sums over contiguous blocks instead: same numbers, a fraction of the
    # memory, and much faster.
    codes = df["id"].cat.codes.to_numpy() if isinstance(
        df["id"].dtype, pd.CategoricalDtype) else pd.factorize(df["id"])[0]
    starts = np.flatnonzero(np.r_[True, codes[1:] != codes[:-1]])
    ends = np.r_[starts[1:], len(codes)]
    # position of each row within its own series
    pos = np.arange(len(codes)) - np.repeat(starts, ends - starts)

    nan = np.isnan(base)
    vals = np.where(nan, np.float32(0), base).astype("float32")
    cnt = (~nan).astype("float32")

    def _block_cumsum(a):
        """cumsum that resets at every series boundary (in-place, float32)"""
        c = np.cumsum(a, dtype="float32")
        offset = np.empty(len(starts), dtype="float32")
        offset[0] = 0.0
        if len(starts) > 1:
            offset[1:] = c[starts[1:] - 1]
        c -= np.repeat(offset, ends - starts)
        return c

    ones = _block_cumsum(np.ones(len(base), dtype="float32"))
    csum = _block_cumsum(vals)
    ccnt = _block_cumsum(cnt)
    csq = _block_cumsum(vals * vals)
    czero = _block_cumsum(((base == 0) & ~nan).astype("float32"))

    ar = np.arange(len(base))

    def _window(cum, w):
        """Sum over the trailing w rows, clipped at the series start.

        For a row whose within-series position is p, the window covers
        positions max(p-w+1, 0)..p. cum already holds the running total from
        the series start, so subtract the total at position p-w when it
        exists.
        """
        idx = np.maximum(ar - w, 0)
        prev = np.where(pos >= w, cum[idx], 0.0)
        return cum - prev

    for w in ROLL_WINDOWS:
        n = _window(ccnt, w)
        df[f"rmean_{w}"] = np.divide(
            _window(csum, w), n, out=np.full(len(base), np.nan, dtype="float32"),
            where=n > 0).astype("float32")

    for w in [7, 28]:
        n = _window(ccnt, w)
        m = np.divide(_window(csum, w), n, out=np.full(len(base), np.nan, dtype="float32"),
                      where=n > 0)
        var = np.divide(_window(csq, w), n, out=np.full(len(base), np.nan, dtype="float32"),
                        where=n > 0) - m * m
        # sample std, matching pandas' default ddof=1
        var = np.where(n > 1, var * n / (n - 1), np.nan)
        df[f"rstd_{w}"] = np.sqrt(np.clip(var, 0, None)).astype("float32")

    # (base == 0) is False for NaN, and pandas rolls that dense boolean, so
    # the denominator is the number of ROWS in the window, not the non-null
    # count. Use the row count to match.
    rows = _window(ones, 28)
    df["zero_rate_28"] = np.divide(
        _window(czero, 28), rows, out=np.full(len(base), np.nan, dtype="float32"),
        where=rows > 0).astype("float32")

    del base, vals, cnt, csum, ccnt, csq, czero, ones, nan, g
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
    """Build features one STORE at a time.

    The full panel is ~22M rows; several float arrays that size will not fit
    on a 8-16 GB Windows box. Each store is ~1/10th of the data and is
    self-contained (all lags and rollings are within-series), so processing
    per store gives identical results at a tenth of the peak memory.
    """
    src = C.PROC / f"base_{C.MODE}.parquet"
    print(f"reading {src}")

    stores = pd.read_parquet(src, columns=["store_id"])["store_id"]
    store_list = sorted(str(x) for x in stores.dropna().unique())
    del stores
    gc.collect()
    print(f"processing {len(store_list)} stores one at a time")

    out_path = C.PROC / f"features_{C.MODE}.parquet"
    writer = None
    total = 0

    for i, store in enumerate(store_list, 1):
        part = pd.read_parquet(src, filters=[("store_id", "==", store)])
        if part.empty:
            continue
        part = add_features(part)

        train_end = data_train_end(part)
        if C.TRAIN_TAIL_DAYS:
            part = part[part["d_num"] > train_end - C.TRAIN_TAIL_DAYS]
        part = part[part["sell_price"].notna() | (part["d_num"] > train_end)]
        part = part[(part["d_num"] <= train_end) |
                    (part["d_num"] >= C.MODES[C.MODE][1])]
        part = part.reset_index(drop=True)

        table = pa.Table.from_pandas(part, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(out_path, table.schema,
                                      compression="snappy")
        writer.write_table(table)
        total += len(part)
        print(f"  [{i}/{len(store_list)}] {store}: {len(part):,} rows")

        del part, table
        gc.collect()

    if writer is not None:
        writer.close()
    print(f"wrote {out_path}  rows={total:,}")


if __name__ == "__main__":
    main()
