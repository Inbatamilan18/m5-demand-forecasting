"""Step 1: turn the 5 Kaggle CSVs into one tidy parquet table.

Run:  python -m src.prepare_data
"""
import gc
import numpy as np
import pandas as pd

from src import config as C

ID_COLS = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]


def _read_sales() -> pd.DataFrame:
    f = C.RAW / "sales_train_evaluation.csv"
    if not f.exists():
        f = C.RAW / "sales_train_validation.csv"
        if not f.exists():
            raise FileNotFoundError(
                f"Put the Kaggle CSVs in {C.RAW}. Missing sales_train_evaluation.csv"
            )
        print("! sales_train_evaluation.csv not found, using validation file "
              "(history ends d_1913).")
    print(f"reading {f.name}")
    df = pd.read_csv(f)
    df["id"] = df["id"].str.replace("_evaluation$", "", regex=True) \
                       .str.replace("_validation$", "", regex=True)
    return df


# Known US holidays/events after the calendar file ends (2016-06-19), needed
# only when MODE = "future".
_FUTURE_EVENTS = {
    "2016-06-19": ("Father's day", "Cultural"),
    "2016-07-04": ("IndependenceDay", "National"),
    "2016-07-06": ("Eid al-Fitr", "Religious"),
}


def _extend_calendar(cal: pd.DataFrame, need_day: int) -> pd.DataFrame:
    """Append deterministic calendar rows past the end of calendar.csv.

    Dates, weekdays, months and SNAP windows are all rules, not data, so they
    can be generated exactly. Event flags come from _FUTURE_EVENTS above.
    """
    last = int(cal["d_num"].max())
    if need_day <= last:
        return cal
    n = need_day - last
    print(f"! calendar.csv ends at d_{last}; generating {n} more days "
          f"(needed for MODE='future')")

    start = cal.loc[cal["d_num"] == last, "date"].iloc[0] + pd.Timedelta(days=1)
    dates = pd.date_range(start, periods=n, freq="D")
    ext = pd.DataFrame({
        "date": dates,
        "d": [f"d_{last + i + 1}" for i in range(n)],
        "d_num": np.arange(last + 1, need_day + 1, dtype="int16"),
        "weekday": dates.day_name(),
        "wday": (dates.dayofweek + 2) % 7 + 1,   # M5: Saturday = 1
        "month": dates.month,
        "year": dates.year,
    })

    # Walmart weeks run Sat-Fri and wm_yr_wk increments by 1 each week.
    last_wk = int(cal.loc[cal["d_num"] == last, "wm_yr_wk"].iloc[0])
    days_into_wk = int(cal.loc[cal["d_num"] == last, "wday"].iloc[0]) - 1
    wk_offset = (np.arange(n) + days_into_wk + 1) // 7
    ext["wm_yr_wk"] = last_wk + wk_offset
    # roll 11552 -> 11601 at the year boundary (not hit in this horizon)
    ext["wm_yr_wk"] = np.where(ext["wm_yr_wk"] % 100 > 52,
                               (ext["wm_yr_wk"] // 100 + 1) * 100 + 1,
                               ext["wm_yr_wk"])

    # object dtype, not float: these hold strings (pandas 3 rejects a str
    # assignment into a float64 column)
    for c in ["event_name_1", "event_type_1", "event_name_2", "event_type_2"]:
        ext[c] = pd.Series([None] * n, index=ext.index, dtype=object)
    for ds, (name, typ) in _FUTURE_EVENTS.items():
        m = ext["date"] == pd.Timestamp(ds)
        ext.loc[m, "event_name_1"] = name
        ext.loc[m, "event_type_1"] = typ

    # SNAP: CA days 1-10, TX 1,3,5,6,7,9,11,12,13,15, WI 2,3,5,6,8,9,11,12,14,15
    dom = dates.day
    ext["snap_CA"] = np.isin(dom, range(1, 11)).astype(int)
    ext["snap_TX"] = np.isin(dom, [1, 3, 5, 6, 7, 9, 11, 12, 13, 15]).astype(int)
    ext["snap_WI"] = np.isin(dom, [2, 3, 5, 6, 8, 9, 11, 12, 14, 15]).astype(int)

    return pd.concat([cal, ext[cal.columns]], ignore_index=True)


def main() -> None:
    sales = _read_sales()
    if C.STORES:
        sales = sales[sales["store_id"].isin(C.STORES)].reset_index(drop=True)
        print(f"filtered to stores {C.STORES}: {len(sales):,} series")

    last_day = max(int(c[2:]) for c in sales.columns if c.startswith("d_"))
    train_end, first_pred = C.MODES[C.MODE]
    train_end = min(train_end, last_day)
    gap = first_pred - last_day - 1
    if gap > 0:
        print(f"! {gap}-day gap between end of history (d_{last_day}) and the\n"
              f"  first forecast day (d_{first_pred}). Features will use\n"
              f"  lags >= {gap + C.HORIZON} days so nothing is undefined.")
    # placeholder columns: the gap days (never predicted, but needed so the
    # date axis is continuous) plus the 28 forecast days
    horizon_days = [f"d_{d}" for d in range(train_end + 1,
                                            first_pred + C.HORIZON)]
    print(f"mode={C.MODE}  history in file ends d_{last_day}  "
          f"train<=d_{train_end}  predict d_{first_pred}..d_{first_pred + C.HORIZON - 1}")

    # Drop any day after train_end (prevents leakage), then append empty
    # placeholder columns for the horizon so they become rows to predict.
    for c in [f"d_{d}" for d in range(train_end + 1, last_day + 1)]:
        if c in sales.columns:
            sales.drop(columns=c, inplace=True)
    sales = pd.concat(
        [sales, pd.DataFrame(np.nan, index=sales.index, columns=horizon_days)],
        axis=1, copy=False)
    # guard: a re-run can leave duplicate day columns, which silently
    # multiplies rows during melt
    dup = sales.columns[sales.columns.duplicated()].tolist()
    if dup:
        print(f"! dropping {len(dup)} duplicate columns: {dup[:5]} ...")
        sales = sales.loc[:, ~sales.columns.duplicated()]

    # Only keep the tail we need as rows (+400 days of runway for yearly lags).
    if C.TRAIN_TAIL_DAYS:
        keep_from = max(1, train_end - C.TRAIN_TAIL_DAYS - 400 - gap)
        drop = [f"d_{d}" for d in range(1, keep_from)
                if f"d_{d}" in sales.columns]
        sales.drop(columns=drop, inplace=True)
        print(f"keeping days d_{keep_from}..d_{first_pred + C.HORIZON - 1}")

    day_cols = sorted({c for c in sales.columns if c.startswith("d_")},
                      key=lambda c: int(c[2:]))
    print(f"melting {len(sales):,} series x {len(day_cols):,} days ...")
    df = sales.melt(id_vars=ID_COLS, value_vars=day_cols,
                    var_name="d", value_name="sales")
    del sales
    gc.collect()

    df["sales"] = df["sales"].astype("float32")
    df["d_num"] = df["d"].str.slice(2).astype("int16")
    df.drop(columns="d", inplace=True)

    # ---------------------------------------------------------------- calendar
    cal = pd.read_csv(C.RAW / "calendar.csv", parse_dates=["date"])
    cal["d_num"] = cal["d"].str.slice(2).astype("int16")
    cal = _extend_calendar(cal, first_pred + C.HORIZON - 1)
    cal = cal[["d_num", "date", "wm_yr_wk", "weekday", "month", "year",
               "event_name_1", "event_type_1", "event_name_2", "event_type_2",
               "snap_CA", "snap_TX", "snap_WI"]]
    df = df.merge(cal, on="d_num", how="left")
    del cal
    gc.collect()

    # ------------------------------------------------------------------ prices
    prices = pd.read_csv(C.RAW / "sell_prices.csv")
    df = df.merge(prices, on=["store_id", "item_id", "wm_yr_wk"], how="left")
    del prices
    gc.collect()

    # A NaN price means the item was not on sale in that store that week.
    df["sell_price"] = df["sell_price"].astype("float32")

    # sell_prices.csv also stops at the end of history. For future weeks carry
    # the last observed price forward per series (best available assumption).
    n_missing = int(df.loc[df["d_num"] > last_day, "sell_price"].isna().sum())
    if n_missing:
        print(f"! carrying last known price forward for {n_missing:,} "
              f"future rows")
        df = df.sort_values(["id", "d_num"], kind="stable")
        df["sell_price"] = (df.groupby("id", observed=True)["sell_price"]
                              .ffill().astype("float32"))
        df = df.reset_index(drop=True)

    for c in ID_COLS + ["weekday", "event_name_1", "event_type_1",
                        "event_name_2", "event_type_2"]:
        df[c] = df[c].astype("category")
    for c in ["snap_CA", "snap_TX", "snap_WI", "month"]:
        df[c] = df[c].astype("int8")
    df["year"] = df["year"].astype("int16")
    df["wm_yr_wk"] = df["wm_yr_wk"].astype("int32")

    n_days, n_ser = df["d_num"].nunique(), df["id"].nunique()
    assert len(df) == n_days * n_ser, (
        f"row count {len(df):,} != {n_ser:,} series x {n_days:,} days "
        f"-> duplicated rows")
    print(f"{n_ser:,} series x {n_days:,} days")

    out = C.PROC / f"base_{C.MODE}.parquet"
    df.to_parquet(out, index=False)
    print(f"wrote {out}  rows={len(df):,}  mem={df.memory_usage(deep=True).sum()/1e9:.2f} GB")


if __name__ == "__main__":
    main()
