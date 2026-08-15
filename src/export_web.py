"""Build a compact data bundle for the deployed web app.

The dashboard normally reads the raw Kaggle CSVs (~450 MB) for sales history,
calendar events and prices. That is far too heavy to ship in a container, so
this script precomputes only what the UI actually renders:

    web_data/history.parquet   last 180 days of sales per series
    web_data/calendar.parquet  dates, events, SNAP flags
    web_data/prices.parquet    latest price per item x store
    web_data/*                 copies of the forecast/metric outputs

Result is a few MB. Run this once after training, before building the image.

Run:  python -m src.export_web
"""
import shutil
import pandas as pd

from src import config as C

WEB = C.ROOT / "web_data"
HISTORY_DAYS = 180


def main() -> None:
    WEB.mkdir(exist_ok=True)

    # ---------------------------------------------------------------- history
    f = C.RAW / "sales_train_evaluation.csv"
    if not f.exists():
        f = C.RAW / "sales_train_validation.csv"
    if not f.exists():
        raise SystemExit(f"No sales CSV in {C.RAW}")

    print(f"reading {f.name} ...")
    sales = pd.read_csv(f)
    sales["id"] = sales["id"].str.replace("_evaluation$", "", regex=True) \
                             .str.replace("_validation$", "", regex=True)
    day_cols = sorted([c for c in sales.columns if c.startswith("d_")],
                      key=lambda c: int(c[2:]))
    keep = day_cols[-HISTORY_DAYS:]
    hist = sales[["id"] + keep].copy()
    for c in keep:
        hist[c] = hist[c].astype("int16")
    hist.to_parquet(WEB / "history.parquet", index=False)
    print(f"  history.parquet  {len(hist):,} series x {len(keep)} days")

    # --------------------------------------------------------------- calendar
    cal = pd.read_csv(C.RAW / "calendar.csv", parse_dates=["date"])
    cols = ["date", "d", "wm_yr_wk", "event_name_1", "event_type_1",
            "event_name_2", "snap_CA", "snap_TX", "snap_WI"]
    cal[[c for c in cols if c in cal.columns]] \
        .to_parquet(WEB / "calendar.parquet", index=False)
    print(f"  calendar.parquet {len(cal):,} rows")

    # ----------------------------------------------------------------- prices
    # only the most recent price per item x store - that is all the UI plots
    prices = pd.read_csv(C.RAW / "sell_prices.csv")
    last_wk = prices["wm_yr_wk"].max()
    recent = (prices[prices["wm_yr_wk"] > last_wk - 60]
              .sort_values("wm_yr_wk")
              .groupby(["store_id", "item_id"], as_index=False)
              .tail(1)[["store_id", "item_id", "sell_price"]])
    recent.to_parquet(WEB / "prices.parquet", index=False)
    print(f"  prices.parquet   {len(recent):,} item x store pairs")

    # ---------------------------------------------------------------- outputs
    n = 0
    for p in C.OUT.iterdir():
        if p.suffix in {".parquet", ".json", ".csv"} and "model" not in p.name:
            shutil.copy2(p, WEB / p.name)
            n += 1
    print(f"  copied {n} output files")

    total = sum(p.stat().st_size for p in WEB.iterdir()) / 1e6
    print(f"\nbundle ready: {WEB}  ({total:.1f} MB)")


if __name__ == "__main__":
    main()
