"""Step 3: train LightGBM and produce 28-day forecasts.

Memory-lean: everything is cast to float32 and the source frame is released
before LightGBM builds its dataset.

Run:  python -m src.train
"""
import gc
import json
import numpy as np
import pandas as pd
import lightgbm as lgb

from src import config as C
from src.features import feature_columns, CAT_FEATURES


def to_float32(df: pd.DataFrame, feats: list[str]) -> pd.DataFrame:
    """Categoricals -> int16 codes, everything else -> float32."""
    out = {}
    for c in feats:
        s = df[c]
        if isinstance(s.dtype, pd.CategoricalDtype):
            out[c] = s.cat.codes.astype("int16")
        else:
            out[c] = pd.to_numeric(s, errors="coerce").astype("float32")
    return pd.DataFrame(out, index=df.index, copy=False)


def main() -> None:
    src = C.PROC / f"features_{C.MODE}.parquet"
    print(f"reading {src}")
    df = pd.read_parquet(src)

    cfg_train_end, first_pred = C.MODES[C.MODE]
    train_end = min(cfg_train_end,
                    int(df.loc[df["sales"].notna(), "d_num"].max()))
    feats = feature_columns(df)

    # Align categorical dictionaries across the whole frame, then encode once
    # so train/valid/test share identical integer codes.
    for c in CAT_FEATURES:
        if c in df.columns and not isinstance(df[c].dtype, pd.CategoricalDtype):
            df[c] = df[c].astype("category")

    # Hold out the last 28 days of history as the validation fold. When the
    # real task has a gap (MODE="future"), the fold must sit the same distance
    # from its training data, otherwise early stopping optimises the wrong
    # problem and stops at iteration 1.
    gap = max(0, first_pred - train_end - 1)
    val_start = train_end - C.HORIZON + 1
    d = df["d_num"].to_numpy()
    m_tr = d < val_start - gap
    m_va = (d >= val_start) & (d <= train_end)
    m_te = ((df["d_num"].to_numpy() >= first_pred) &
            (df["d_num"].to_numpy() < first_pred + C.HORIZON))
    print(f"train={m_tr.sum():,}  valid={m_va.sum():,}  predict={m_te.sum():,}")
    if m_te.sum() == 0:
        raise SystemExit("no rows to predict - check MODE and the horizon days")

    y = df["sales"].to_numpy(dtype="float32")
    X = to_float32(df, feats)
    keep = df[["id", "item_id", "dept_id", "cat_id", "store_id", "state_id",
               "d_num", "date"]][m_te].copy()
    del df
    gc.collect()
    print(f"feature matrix {X.shape} "
          f"{X.memory_usage(deep=True).sum() / 1e9:.2f} GB")

    cat_idx = [feats.index(c) for c in CAT_FEATURES if c in feats]

    # Build LightGBM's internal binned dataset, then drop the raw copies.
    # Holding both at once is what triggers "bad allocation" on 8-16 GB boxes.
    Xtr = X[m_tr].to_numpy(dtype="float32", copy=False)
    dtr = lgb.Dataset(Xtr, y[m_tr], categorical_feature=cat_idx,
                      feature_name=feats, free_raw_data=True,
                      params={"max_bin": C.LGB_PARAMS.get("max_bin", 127)})
    dtr.construct()
    del Xtr
    gc.collect()

    Xva = X[m_va].to_numpy(dtype="float32", copy=False)
    dva = lgb.Dataset(Xva, y[m_va], categorical_feature=cat_idx,
                      feature_name=feats, reference=dtr, free_raw_data=True)
    dva.construct()
    del Xva
    gc.collect()

    # only the prediction slice is still needed as a frame
    Xte = X[m_te].copy()
    del X
    gc.collect()
    print(f"datasets built, raw frame released "
          f"(predict slice {Xte.memory_usage(deep=True).sum() / 1e9:.2f} GB)")

    print("training ...")
    model = lgb.train(
        C.LGB_PARAMS, dtr, num_boost_round=C.NUM_BOOST_ROUND,
        valid_sets=[dva], valid_names=["valid"],
        callbacks=[lgb.early_stopping(C.EARLY_STOPPING, verbose=True),
                   lgb.log_evaluation(100)],
    )
    model.save_model(str(C.OUT / f"model_{C.MODE}.txt"))
    del dtr, dva
    gc.collect()

    imp = pd.DataFrame({"feature": model.feature_name(),
                        "gain": model.feature_importance("gain")}) \
            .sort_values("gain", ascending=False)
    imp.to_csv(C.OUT / f"feature_importance_{C.MODE}.csv", index=False)
    print("\ntop 15 features:\n", imp.head(15).to_string(index=False))

    print("\npredicting ...")
    chunks = []
    for i in range(0, len(Xte), 2_000_000):
        chunks.append(model.predict(Xte.iloc[i:i + 2_000_000],
                                    num_iteration=model.best_iteration))
    pred = np.concatenate(chunks) if chunks else np.array([])

    out = keep
    out["forecast"] = np.clip(pred, 0, None).astype("float32")
    out["horizon"] = (out["d_num"] - first_pred + 1).astype("int8")
    out.to_parquet(C.OUT / f"forecast_{C.MODE}.parquet", index=False)

    wide = out.pivot(index="id", columns="horizon", values="forecast")
    wide.columns = [f"F{c}" for c in wide.columns]
    wide.reset_index().to_csv(C.OUT / f"submission_{C.MODE}.csv", index=False)

    meta = {"mode": C.MODE, "best_iteration": int(model.best_iteration),
            "valid_rmse": float(model.best_score["valid"]["rmse"]),
            "n_series": int(out["id"].nunique()),
            "first_date": str(out["date"].min().date()),
            "last_date": str(out["date"].max().date())}
    (C.OUT / f"train_meta_{C.MODE}.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    print(f"wrote {C.OUT / f'forecast_{C.MODE}.parquet'}")


if __name__ == "__main__":
    main()
