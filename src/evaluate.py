"""Step 4: Evaluate 28-day forecasts.

Calculates:
- MAE
- RMSE
- WAPE
- Aggregate Forecast Error
- WRMSSE across all 12 M5 hierarchy levels
- RMSSE / MAE / Bias for each hierarchy level
- Bottom-up hierarchy forecast table

Run:
    python -m src.evaluate
"""

import json
import numpy as np
import pandas as pd

from src import config as C
from src.features import to_str


# -------------------------------------------------------------------------
# M5 hierarchy
# -------------------------------------------------------------------------
LEVELS = [
    ("L1  Total",                  []),
    ("L2  State",                  ["state_id"]),
    ("L3  Store",                  ["store_id"]),
    ("L4  Category",               ["cat_id"]),
    ("L5  Department",             ["dept_id"]),
    ("L6  State-Category",         ["state_id", "cat_id"]),
    ("L7  State-Department",       ["state_id", "dept_id"]),
    ("L8  Store-Category",         ["store_id", "cat_id"]),
    ("L9  Store-Department",        ["store_id", "dept_id"]),
    ("L10 Item",                   ["item_id"]),
    ("L11 Item-State",             ["item_id", "state_id"]),
    ("L12 Item-Store",             ["item_id", "store_id"]),
]


# -------------------------------------------------------------------------
# Load actual sales
# -------------------------------------------------------------------------
def _load_actuals(ids: pd.Index, days: list[int]) -> pd.DataFrame:
    """Load actual sales for the requested item-store series and days."""

    f = C.RAW / "sales_train_evaluation.csv"

    if not f.exists():
        f = C.RAW / "sales_train_validation.csv"

    if not f.exists():
        raise FileNotFoundError(
            "Could not find sales_train_evaluation.csv "
            "or sales_train_validation.csv in data/raw."
        )

    df = pd.read_csv(f)

    # Remove suffixes if present.
    df["id"] = (
        df["id"]
        .str.replace("_evaluation$", "", regex=True)
        .str.replace("_validation$", "", regex=True)
    )

    df = df.set_index("id")

    cols = [
        f"d_{d}"
        for d in days
        if f"d_{d}" in df.columns
    ]

    if not cols:
        return pd.DataFrame(index=df.index.intersection(ids))

    return df.loc[
        df.index.intersection(ids),
        cols
    ]


# -------------------------------------------------------------------------
# Overall bottom-level metrics
# -------------------------------------------------------------------------
def calculate_overall_metrics(
    actual: pd.DataFrame,
    predicted: pd.DataFrame,
) -> dict:
    """
    Calculate metrics across all bottom-level item-store-day predictions.

    MAE:
        Mean Absolute Error

    RMSE:
        Root Mean Squared Error

    WAPE:
        Sum absolute error / sum actual * 100

    Aggregate Forecast Error:
        Absolute difference between total forecast and total actual,
        divided by total actual.
    """

    # Force identical order of IDs and dates.
    common_ids = actual.index.intersection(predicted.index)
    common_days = actual.columns.intersection(predicted.columns)

    actual = actual.loc[
        common_ids,
        common_days
    ]

    predicted = predicted.loc[
        common_ids,
        common_days
    ]

    if actual.empty or len(common_days) == 0:
        raise ValueError(
            "No overlapping actual and predicted values were found."
        )

    y_true = actual.to_numpy(dtype="float64")
    y_pred = predicted.to_numpy(dtype="float64")

    error = y_pred - y_true
    abs_error = np.abs(error)

    mae = float(abs_error.mean())

    rmse = float(
        np.sqrt(
            np.mean(error ** 2)
        )
    )

    actual_total = float(y_true.sum())

    absolute_error_total = float(
        abs_error.sum()
    )

    if actual_total > 0:
        wape = (
            absolute_error_total
            / actual_total
            * 100
        )

        aggregate_error = (
            abs(float(y_pred.sum()) - actual_total)
            / actual_total
            * 100
        )
    else:
        wape = np.nan
        aggregate_error = np.nan

    forecast_total = float(y_pred.sum())

    bias_pct = (
        (forecast_total / actual_total - 1)
        * 100
        if actual_total > 0
        else np.nan
    )

    return {
        "mae": mae,
        "rmse": rmse,
        "wape_pct": float(wape),
        "aggregate_forecast_error_pct": float(
            aggregate_error
        ),
        "bias_pct": float(bias_pct),
        "actual_total_units": actual_total,
        "forecast_total_units": forecast_total,
        "n_series": int(len(common_ids)),
        "n_days": int(len(common_days)),
        "n_predictions": int(
            len(common_ids) * len(common_days)
        ),
    }


# -------------------------------------------------------------------------
# Main evaluation
# -------------------------------------------------------------------------
def main() -> None:

    print("=" * 70)
    print("M5 FORECAST EVALUATION")
    print("=" * 70)

    # ---------------------------------------------------------------------
    # Load forecast
    # ---------------------------------------------------------------------
    forecast_file = (
        C.OUT / f"forecast_{C.MODE}.parquet"
    )

    if not forecast_file.exists():
        raise FileNotFoundError(
            f"Forecast file not found:\n{forecast_file}\n\n"
            "Run the training pipeline first."
        )

    fc = pd.read_parquet(
        forecast_file
    )

    train_end, first_pred = C.MODES[C.MODE]

    pred_days = list(
        range(
            first_pred,
            first_pred + C.HORIZON
        )
    )

    print(f"\nMode: {C.MODE}")
    print(f"Training end: d_{train_end}")
    print(f"First prediction: d_{first_pred}")
    print(f"Forecast horizon: {C.HORIZON} days")

    # ---------------------------------------------------------------------
    # Load actual history and ground truth
    # ---------------------------------------------------------------------
    ids = pd.Index(
        fc["id"].unique()
    )

    hist = _load_actuals(
        ids,
        list(range(1, train_end + 1))
    )

    truth = _load_actuals(
        ids,
        pred_days
    )

    print(
        f"\nActual history columns: {hist.shape[1]}"
    )

    print(
        f"Ground-truth columns: {truth.shape[1]}/{C.HORIZON}"
    )

    have_truth = (
        truth.shape[1] == C.HORIZON
    )

    if not have_truth:
        print(
            f"\nWARNING: Ground truth is not available "
            f"for the complete {C.MODE} window."
        )

        print(
            "MAE / RMSE / WAPE / WRMSSE cannot be calculated "
            "for this window."
        )

    # ---------------------------------------------------------------------
    # Convert forecast from long format to wide format
    # ---------------------------------------------------------------------
    pred = fc.pivot(
        index="id",
        columns="d_num",
        values="forecast"
    )

    # Convert d_num columns to the same naming convention
    # as the actual dataframe: d_1914, d_1915, ...
    pred.columns = [
        f"d_{int(c)}"
        for c in pred.columns
    ]

    # ---------------------------------------------------------------------
    # Overall metrics
    # ---------------------------------------------------------------------
    overall = None

    if have_truth:

        overall = calculate_overall_metrics(
            truth,
            pred
        )

        print("\n")
        print("=" * 70)
        print("OVERALL BOTTOM-LEVEL METRICS")
        print("=" * 70)

        print(
            f"MAE:                       "
            f"{overall['mae']:.4f}"
        )

        print(
            f"RMSE:                      "
            f"{overall['rmse']:.4f}"
        )

        print(
            f"WAPE:                      "
            f"{overall['wape_pct']:.2f}%"
        )

        print(
            f"Aggregate forecast error:  "
            f"{overall['aggregate_forecast_error_pct']:.2f}%"
        )

        print(
            f"Bias:                      "
            f"{overall['bias_pct']:.2f}%"
        )

        print(
            f"Actual total:               "
            f"{overall['actual_total_units']:,.0f}"
        )

        print(
            f"Forecast total:             "
            f"{overall['forecast_total_units']:,.0f}"
        )

    # ---------------------------------------------------------------------
    # Metadata
    # ---------------------------------------------------------------------
    meta = (
        fc.drop_duplicates("id")
        .set_index("id")
        [
            [
                "item_id",
                "dept_id",
                "cat_id",
                "store_id",
                "state_id",
            ]
        ]
        .reindex(hist.index)
    )

    # ---------------------------------------------------------------------
    # Price weights for WRMSSE
    # ---------------------------------------------------------------------
    prices = pd.read_csv(
        C.RAW / "sell_prices.csv"
    )

    cal = pd.read_csv(
        C.RAW / "calendar.csv"
    )

    cal["d_num"] = (
        cal["d"]
        .str.slice(2)
        .astype(int)
    )

    wk = (
        cal
        .set_index("d_num")["wm_yr_wk"]
    )

    # Last 28 training days.
    last28 = [
        d
        for d in range(
            train_end - 27,
            train_end + 1
        )
        if f"d_{d}" in hist.columns
    ]

    # Revenue weights.
    rev = pd.Series(
        0.0,
        index=hist.index
    )

    pmap = (
        prices
        .set_index(
            [
                "store_id",
                "item_id",
                "wm_yr_wk",
            ]
        )["sell_price"]
    )

    key = pd.MultiIndex.from_arrays(
        [
            meta["store_id"],
            meta["item_id"],
        ]
    )

    for d in last28:

        price_key = pd.MultiIndex.from_arrays(
            [
                key.get_level_values(0),
                key.get_level_values(1),
                np.full(
                    len(key),
                    wk[d]
                ),
            ]
        )

        p = (
            pmap
            .reindex(price_key)
            .to_numpy()
        )

        sales = (
            hist[f"d_{d}"]
            .to_numpy()
        )

        rev += np.nan_to_num(
            sales * p
        )

    # ---------------------------------------------------------------------
    # WRMSSE hierarchy evaluation
    # ---------------------------------------------------------------------
    rows = []

    for name, keys in LEVELS:

        if keys:

            grp = (
                pd.concat(
                    [
                        to_str(meta[k])
                        for k in keys
                    ],
                    axis=1,
                )
                .agg(
                    "--".join,
                    axis=1
                )
            )

        else:

            grp = pd.Series(
                "TOTAL",
                index=meta.index
            )

        # Historical sales aggregated to this hierarchy.
        h = hist.groupby(
            grp
        ).sum()

        # Predictions aggregated to this hierarchy.
        p = pred.groupby(
            grp
        ).sum()

        # Revenue weights.
        w = rev.groupby(
            grp
        ).sum()

        if w.sum() > 0:
            w = w / w.sum()

        # -------------------------------------------------------------
        # M5 scale
        # -------------------------------------------------------------
        hv = h.to_numpy(
            dtype="float64"
        )

        if hv.shape[1] > 1:

            diff = (
                np.diff(
                    hv,
                    axis=1
                ) ** 2
            )

            # First non-zero sale.
            nz = np.argmax(
                hv > 0,
                axis=1
            )

            scale = np.array(
                [
                    (
                        diff[i, nz[i]:].mean()
                        if diff[i, nz[i]:].size
                        else np.nan
                    )
                    for i in range(len(hv))
                ]
            )

        else:

            scale = np.full(
                len(hv),
                np.nan
            )

        row = {
            "level": name,
            "n_series": len(h),
        }

        # -------------------------------------------------------------
        # Accuracy for hierarchy
        # -------------------------------------------------------------
        if have_truth:

            t = truth.groupby(
                grp
            ).sum()

            # Make sure the prediction and truth series
            # have identical ordering.
            t = t.reindex(
                index=p.index,
                columns=pred.columns
            )

            p_arr = p.to_numpy(
                dtype="float64"
            )

            t_arr = t.to_numpy(
                dtype="float64"
            )

            hierarchy_error = (
                t_arr - p_arr
            )

            hierarchy_abs_error = np.abs(
                hierarchy_error
            )

            hierarchy_mae = (
                hierarchy_abs_error
                .mean(axis=1)
            )

            mse = (
                hierarchy_error ** 2
            ).mean(axis=1)

            rmsse = np.sqrt(
                mse / scale
            )

            ok = (
                np.isfinite(rmsse)
                & np.isfinite(
                    w.to_numpy()
                )
            )

            if ok.any():

                rmsse_weighted = float(
                    np.average(
                        rmsse[ok],
                        weights=w.to_numpy()[ok]
                    )
                )

            else:

                rmsse_weighted = np.nan

            row["rmsse"] = (
                rmsse_weighted
            )

            row["mae"] = float(
                hierarchy_abs_error.mean()
            )

            actual_sum = float(
                t_arr.sum()
            )

            forecast_sum = float(
                p_arr.sum()
            )

            if actual_sum > 0:

                row["bias_pct"] = (
                    (
                        forecast_sum
                        / actual_sum
                    ) - 1
                ) * 100

            else:

                row["bias_pct"] = np.nan

        rows.append(row)

    # ---------------------------------------------------------------------
    # Results table
    # ---------------------------------------------------------------------
    res = pd.DataFrame(
        rows
    )

    wrmsse = None

    if have_truth:

        wrmsse = float(
            res["rmsse"].mean()
        )

        print("\n")
        print("=" * 70)
        print("WRMSSE BY HIERARCHY LEVEL")
        print("=" * 70)

        print(
            res.to_string(
                index=False
            )
        )

        print(
            f"\nWRMSSE "
            f"(mean over 12 levels) = "
            f"{wrmsse:.4f}"
        )

    # ---------------------------------------------------------------------
    # Save metrics CSV
    # ---------------------------------------------------------------------
    if have_truth:

        metrics_csv = (
            C.OUT /
            f"metrics_{C.MODE}.csv"
        )

        res.to_csv(
            metrics_csv,
            index=False
        )

        print(
            f"\nSaved hierarchy metrics:"
            f"\n{metrics_csv}"
        )

    # ---------------------------------------------------------------------
    # Save complete metrics JSON
    # ---------------------------------------------------------------------
    if have_truth:

        metrics_json = (
            C.OUT /
            f"metrics_{C.MODE}.json"
        )

        complete_metrics = {
            "mode": C.MODE,

            "overall": overall,

            "wrmsse": wrmsse,

            "hierarchy_levels":
                res.to_dict(
                    orient="records"
                ),
        }

        metrics_json.write_text(
            json.dumps(
                complete_metrics,
                indent=2
            )
        )

        print(
            f"Saved complete metrics:"
            f"\n{metrics_json}"
        )

    # ---------------------------------------------------------------------
    # Hierarchy table for dashboard
    # ---------------------------------------------------------------------
    agg = []

    for name, keys in LEVELS:

        group_cols = (
            keys + ["date"]
        )

        g = (
            fc.groupby(
                group_cols,
                observed=True
            )["forecast"]
            .sum()
            .reset_index()
        )

        g["level"] = name

        if keys:

            g["node"] = (
                pd.concat(
                    [
                        to_str(g[k])
                        for k in keys
                    ],
                    axis=1,
                )
                .agg(
                    "--".join,
                    axis=1
                )
            )

        else:

            g["node"] = "TOTAL"

        agg.append(
            g[
                [
                    "level",
                    "node",
                    "date",
                    "forecast",
                ]
            ]
        )

    hierarchy = pd.concat(
        agg,
        ignore_index=True
    )

    hierarchy_file = (
        C.OUT /
        f"hierarchy_{C.MODE}.parquet"
    )

    hierarchy.to_parquet(
        hierarchy_file,
        index=False
    )

    print(
        f"\nWrote hierarchy file:"
        f"\n{hierarchy_file}"
    )

    print("\n")
    print("=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()