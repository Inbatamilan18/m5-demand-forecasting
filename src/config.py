"""Central configuration. Edit values here, nothing else."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"          # put the 5 Kaggle CSVs here
PROC = ROOT / "data" / "processed"   # generated parquet files
OUT = ROOT / "outputs"               # models, forecasts, metrics

for _p in (RAW, PROC, OUT):
    _p.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- M5 constants
HORIZON = 28
D_TRAIN_END = 1913    # sales_train_validation.csv ends here (2016-04-24)
D_VALID_END = 1941    # validation window end          (2016-05-22)
D_EVAL_END = 1969     # sales_train_evaluation.csv ends (2016-06-19)

MODES = {
    # mode:        (last day used for training, first day predicted)
    "validation": (D_TRAIN_END, D_TRAIN_END + 1),   # d_1914-1941, scoreable
    "evaluation": (D_VALID_END, D_VALID_END + 1),   # d_1942-1969, scoreable
    "future":     (D_EVAL_END, D_EVAL_END + 1),     # d_1970-1997 = 2016-06-20 -> 2016-07-17
}

MODE = "validation"

# ------------------------------------------------------------------- resources
# Keep only the last N days of history as training ROWS (features still look
# back 1 year). 730 keeps memory ~4 GB. Use None for everything (needs ~16 GB).
TRAIN_TAIL_DAYS = 730

# Restrict to a few stores while you test the pipeline, e.g. ["CA_1", "CA_2"].
# Set to None to use all 10 stores.
STORES = None

SEED = 42

LGB_PARAMS = {
    "objective": "tweedie",
    "tweedie_variance_power": 1.1,
    "metric": "rmse",
    "learning_rate": 0.05,
    "num_leaves": 128,
    "min_data_in_leaf": 100,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 0.1,
    "max_bin": 127,
    "num_threads": 4,
    "force_row_wise": True,
    "verbosity": -1,
    "seed": SEED,
}
NUM_BOOST_ROUND = 1200
EARLY_STOPPING = 100
