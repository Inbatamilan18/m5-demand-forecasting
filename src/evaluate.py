"""Step 4: WRMSSE across all 12 hierarchy levels + bottom-up reconciliation.

Run:  python -m src.evaluate
"""
import json
import numpy as np
import pandas as pd

from src import config as C
from src.features import to_str

# The 12 aggregation levels defined by the M5 competition.
LEVELS = [
    ("L1  Total",                  []),
    ("L2  State",                  ["state_id"]),
    ("L3  Store",                  ["store_id"]),
    ("L4  Category",               ["cat_id"]),
    ("L5  Department",             ["dept_id"]),
    ("L6  State-Category",         ["state_id", "cat_id"]),
    ("L7  State-Department",       ["state_id", "dept_id"]),
    ("L8  Store-Category",         ["store_id", "cat_id"]),
    ("L9  Store-Department",       ["store_id", "dept_id"]),
    ("L10 Item",                   ["item_id"]),
    ("L11 Item-State",             ["item_id", "state_id"]),
    ("L12 Item-Store",             ["item_id", "store_id"]),
]


def _load_actuals(ids: pd.Index, days: list[int]) -> pd.DataFrame:
    """Wide history matrix (id x d_num) from the raw sales file."""
    f = C.RAW / "sales_train_evaluation.csv"
    if not f.exists():
        f = C.RAW / "sales_train_validation.csv"
    df = pd.read_csv(f)
    df["id"] = df["id"].str.replace("_evaluation$", "", regex=True) \
                       .str.replace("_validation$", "", regex=True)
    df = df.set_index("id")
    cols = [f"d_{d}" for d in days if f"d_{d}" in df.columns]
    return df.loc[df.index.intersection(ids), cols]


def main() -> None:
    fc = pd.read_parquet(C.OUT / f"forecast_{C.MODE}.parquet")
    train_end, first_pred = C.MODES[C.MODE]
    pred_days = list(range(first_pred, first_pred + C.HORIZON))

    ids = fc["id"].unique()
    hist = _load_actuals(pd.Index(ids), list(range(1, train_end + 1)))
    truth = _load_actuals(pd.Index(ids), pred_days)
    have_truth = truth.shape[1] == C.HORIZON
    if not have_truth:
        print(f"! no ground truth for {C.MODE} window "
              f"(got {truth.shape[1]}/{C.HORIZON} days) -> skipping WRMSSE")

    pred = fc.pivot(index="id", columns="d_num", values="forecast")
    pred = pred.reindex(hist.index)

    meta = (fc.drop_duplicates("id")
              .set_index("id")[["item_id", "dept_id", "cat_id",
                                "store_id", "state_id"]]
              .reindex(hist.index))

    # dollar weights: last 28 days of training revenue
    prices = pd.read_csv(C.RAW / "sell_prices.csv")
    cal = pd.read_csv(C.RAW / "calendar.csv")
    cal["d_num"] = cal["d"].str.slice(2).astype(int)
    wk = cal.set_index("d_num")["wm_yr_wk"]
    last28 = [d for d in range(train_end - 27, train_end + 1)
              if f"d_{d}" in hist.columns]
    rev = pd.Series(0.0, index=hist.index)
    pmap = prices.set_index(["store_id", "item_id", "wm_yr_wk"])["sell_price"]
    key = pd.MultiIndex.from_arrays([meta["store_id"], meta["item_id"]])
    for d in last28:
        p = pmap.reindex(pd.MultiIndex.from_arrays(
            [key.get_level_values(0), key.get_level_values(1),
             np.full(len(key), wk[d])])).to_numpy()
        rev += np.nan_to_num(hist[f"d_{d}"].to_numpy() * p)

    rows = []
    for name, keys in LEVELS:
        if keys:
            grp = pd.concat([to_str(meta[k]) for k in keys], axis=1)\
                    .agg("--".join, axis=1)
        else:
            grp = pd.Series("TOTAL", index=meta.index)

        h = hist.groupby(grp).sum()
        p = pred.groupby(grp).sum()
        w = rev.groupby(grp).sum()
        w = w / w.sum()

        # scale = mean squared 1-step naive error over the training history,
        # counting only from each series' first non-zero sale
        hv = h.to_numpy(dtype=float)
        diff = np.diff(hv, axis=1) ** 2
        nz = np.argmax(hv > 0, axis=1)
        scale = np.array([diff[i, nz[i]:].mean() if diff[i, nz[i]:].size else np.nan
                          for i in range(len(hv))])

        row = {"level": name, "n_series": len(h)}
        if have_truth:
            t = truth.groupby(grp).sum()
            err = ((t.to_numpy(dtype=float) - p.to_numpy(dtype=float)) ** 2).mean(axis=1)
            rmsse = np.sqrt(err / scale)
            ok = np.isfinite(rmsse)
            row["rmsse"] = float(np.average(rmsse[ok], weights=w.to_numpy()[ok]))
            row["mae"] = float(np.abs(t.to_numpy(dtype=float)
                                      - p.to_numpy(dtype=float)).mean())
            row["bias_pct"] = float(
                100 * (p.to_numpy(dtype=float).sum() / t.to_numpy(dtype=float).sum() - 1))
        rows.append(row)

    res = pd.DataFrame(rows)
    if have_truth:
        wrmsse = res["rmsse"].mean()
        print(res.to_string(index=False))
        print(f"\nWRMSSE (mean over 12 levels) = {wrmsse:.4f}")
        res.to_csv(C.OUT / f"metrics_{C.MODE}.csv", index=False)
        (C.OUT / f"metrics_{C.MODE}.json").write_text(
            json.dumps({"wrmsse": float(wrmsse),
                        "levels": res.to_dict("records")}, indent=2))
    else:
        print(res.to_string(index=False))

    # ---- hierarchy table for the dashboard (aggregated forecasts, bottom-up)
    agg = []
    for name, keys in LEVELS:
        g = fc.groupby((keys or []) + ["date"], observed=True)["forecast"].sum() \
              .reset_index()
        g["level"] = name
        g["node"] = (pd.concat([to_str(g[k]) for k in keys], axis=1)
                     .agg("--".join, axis=1) if keys else "TOTAL")
        agg.append(g[["level", "node", "date", "forecast"]])
    pd.concat(agg).to_parquet(C.OUT / f"hierarchy_{C.MODE}.parquet", index=False)
    print(f"wrote {C.OUT/f'hierarchy_{C.MODE}.parquet'}")


if __name__ == "__main__":
    main()
