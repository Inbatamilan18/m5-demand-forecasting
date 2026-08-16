# ============================================================
# M5 RETAIL DEMAND FORECASTING - FASTAPI BACKEND
# No authentication: the dashboard is public.
# ============================================================

from pathlib import Path
from datetime import datetime
import json
import io

import pandas as pd

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web_data"
FRONTEND = ROOT / "frontend"

app = FastAPI(title="M5 Retail Demand Forecasting API", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODES = {"future", "validation", "evaluation"}
_CACHE: dict[str, pd.DataFrame] = {}


# ============================================================
# HELPERS
# ============================================================

def load_forecast(mode: str) -> pd.DataFrame:
    if mode not in MODES:
        raise HTTPException(400, f"Invalid mode. Choose from {sorted(MODES)}.")
    if mode in _CACHE:
        return _CACHE[mode]
    path = WEB / f"forecast_{mode}.parquet"
    if not path.exists():
        raise HTTPException(404, f"Forecast data for '{mode}' was not found.")
    df = pd.read_parquet(path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    _CACHE.clear()               # hold only one mode in memory at a time
    _CACHE[mode] = df
    return df


def clean_value(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            pass
    return v


def clean_records(df):
    return [{k: clean_value(v) for k, v in r.items()}
            for r in df.to_dict(orient="records")]


def apply_filters(df, state, store, category, department, item):
    for col, val in (("state_id", state), ("store_id", store),
                     ("cat_id", category), ("dept_id", department),
                     ("item_id", item)):
        if val and col in df.columns:
            df = df[df[col].astype(str) == str(val)]
    return df


def col_values(df, col):
    if col not in df.columns:
        return []
    return sorted({str(v) for v in df[col].dropna().unique()})


def read_meta(mode: str) -> dict:
    f = WEB / f"train_meta_{mode}.json"
    return json.loads(f.read_text()) if f.exists() else {}


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():
    return {"status": "healthy"}


# ============================================================
# OVERVIEW  (landing page)
# ============================================================

@app.get("/overview")
def overview():
    """Dataset and project facts for the first page."""
    df = load_forecast("future")

    states = col_values(df, "state_id")
    stores = col_values(df, "store_id")
    cats = col_values(df, "cat_id")
    depts = col_values(df, "dept_id")
    items = df["item_id"].nunique() if "item_id" in df.columns else 0

    stores_by_state = {}
    if {"state_id", "store_id"} <= set(df.columns):
        g = df.groupby("state_id", observed=True)["store_id"].unique()
        stores_by_state = {str(k): sorted(str(x) for x in v)
                           for k, v in g.items()}

    depts_by_cat = {}
    if {"cat_id", "dept_id"} <= set(df.columns):
        g = df.groupby("cat_id", observed=True)["dept_id"].unique()
        depts_by_cat = {str(k): sorted(str(x) for x in v)
                        for k, v in g.items()}

    cat_volume = []
    if "cat_id" in df.columns:
        g = (df.groupby("cat_id", observed=True, as_index=False)["forecast"]
               .sum().sort_values("forecast", ascending=False))
        g.columns = ["name", "forecast"]
        g["name"] = g["name"].astype(str)
        cat_volume = clean_records(g)

    metrics_file = WEB / "metrics_validation.json"
    wrmsse = None
    if metrics_file.exists():
        wrmsse = json.loads(metrics_file.read_text()).get("wrmsse")

    windows = []
    for m in ("validation", "evaluation", "future"):
        meta = read_meta(m)
        if meta:
            windows.append({
                "mode": m,
                "first_date": meta.get("first_date"),
                "last_date": meta.get("last_date"),
                "series": meta.get("n_series"),
                "scoreable": m == "validation",
            })

    return {
        "dataset": {
            "name": "Walmart M5 Forecasting - Accuracy",
            "source": "kaggle.com/competitions/m5-forecasting-accuracy",
            "series": int(df["id"].nunique()) if "id" in df.columns else 0,
            "items": int(items),
            "stores": len(stores),
            "states": len(states),
            "categories": len(cats),
            "departments": len(depts),
            "history_days": 1941,
            "history_start": "2011-01-29",
            "history_end": "2016-05-22",
            "hierarchy_levels": 12,
            "horizon_days": 28,
        },
        "states": states,
        "stores": stores,
        "categories": cats,
        "departments": depts,
        "stores_by_state": stores_by_state,
        "departments_by_category": depts_by_cat,
        "category_volume": cat_volume,
        "wrmsse": wrmsse,
        "windows": windows,
        "model": {
            "algorithm": "LightGBM (gradient boosted trees)",
            "objective": "Tweedie - handles zero-inflated intermittent demand",
            "features": 38,
            "approach": "Direct multi-horizon, bottom-up reconciliation",
        },
    }


# ============================================================
# DASHBOARD  (one aggregated payload, ~3 KB)
# ============================================================

@app.get("/dashboard")
def dashboard(
    mode: str = "future",
    state: str = "",
    store: str = "",
    category: str = "",
    department: str = "",
    item: str = "",
):
    """All KPIs and chart series, aggregated server-side.

    Returning raw rows would be ~190 MB of JSON for 853,720 records, so
    every grouping happens here and only summaries travel to the browser.
    """
    full = load_forecast(mode)
    df = apply_filters(full, state, store, category, department, item)
    meta = read_meta(mode)

    # Cascading filter lists: each dropdown only offers values that still
    # exist given the OTHER selections. The item list is scoped to the chosen
    # category/department, because 3,049 items in one dropdown is unusable.
    scope = apply_filters(full, state, store, category, department, "")
    item_pool = scope if (category or department or store or state) else full

    base = {
        "mode": mode,
        "first_date": meta.get("first_date"),
        "last_date": meta.get("last_date"),
        "filters": {
            "states": col_values(full, "state_id"),
            "stores": col_values(apply_filters(full, state, "", "", "", ""),
                                 "store_id"),
            "categories": col_values(full, "cat_id"),
            "departments": col_values(
                apply_filters(full, "", "", category, "", ""), "dept_id"),
            "items": col_values(item_pool, "item_id"),
            "item_count": int(item_pool["item_id"].nunique())
                           if "item_id" in item_pool.columns else 0,
        },
    }

    if df.empty:
        return {**base, "total_units": 0, "series": 0,
                "avg_units_per_day": 0, "peak_day_units": 0,
                "peak_date": None, "daily": [], "by_category": [],
                "by_store": [], "by_state": [], "top_items": []}

    daily = (df.groupby("date", as_index=False)["forecast"].sum()
               .sort_values("date"))
    peak = daily.loc[daily["forecast"].idxmax()]

    def group(col, n=25):
        if col not in df.columns:
            return []
        g = (df.groupby(col, observed=True, as_index=False)["forecast"].sum()
               .sort_values("forecast", ascending=False).head(n))
        g.columns = ["name", "forecast"]
        g["name"] = g["name"].astype(str)
        return clean_records(g)

    top_items = []
    if {"item_id", "store_id"} <= set(df.columns):
        g = (df.groupby(["item_id", "store_id"], observed=True,
                        as_index=False)["forecast"].sum()
               .sort_values("forecast", ascending=False).head(20))
        g["item_id"] = g["item_id"].astype(str)
        g["store_id"] = g["store_id"].astype(str)
        top_items = clean_records(g)

    return {
        **base,
        "total_units": float(df["forecast"].sum()),
        "series": int(df["id"].nunique()) if "id" in df.columns else 0,
        "avg_units_per_day": float(daily["forecast"].mean()),
        "peak_day_units": float(daily["forecast"].max()),
        "peak_date": clean_value(peak["date"]),
        "daily": clean_records(daily),
        "by_category": group("cat_id"),
        "by_store": group("store_id"),
        "by_state": group("state_id"),
        "top_items": top_items,
    }


# ============================================================
# HIERARCHY - all 12 M5 levels
# ============================================================

@app.get("/hierarchy")
def hierarchy(mode: str = "future"):
    df = load_forecast(mode)
    levels = [{"level": "L1  Total", "columns": [], "count": 1,
               "data": [{"name": "TOTAL",
                         "forecast": float(df["forecast"].sum())}]}]

    def add(name, cols):
        cols = [c for c in cols if c in df.columns]
        if not cols:
            return
        g = df.groupby(cols, observed=True, dropna=False,
                       as_index=False)["forecast"].sum()
        count = len(g)
        g = g.sort_values("forecast", ascending=False).head(15)
        rows = []
        for _, r in g.iterrows():
            rows.append({
                "name": " / ".join(str(r[c]) for c in cols),
                "forecast": float(r["forecast"]),
            })
        levels.append({"level": name, "columns": cols,
                       "count": count, "data": rows})

    add("L2  State", ["state_id"])
    add("L3  Store", ["store_id"])
    add("L4  Category", ["cat_id"])
    add("L5  Department", ["dept_id"])
    add("L6  State x Category", ["state_id", "cat_id"])
    add("L7  State x Department", ["state_id", "dept_id"])
    add("L8  Store x Category", ["store_id", "cat_id"])
    add("L9  Store x Department", ["store_id", "dept_id"])
    add("L10 Item", ["item_id"])
    add("L11 Item x State", ["item_id", "state_id"])
    add("L12 Item x Store", ["item_id", "store_id"])
    return {"mode": mode, "levels": levels}


# ============================================================
# ACCURACY
# ============================================================

@app.get("/accuracy")
def accuracy(mode: str = "validation"):
    out = {"mode": mode, "wrmsse": None, "levels": [], "features": [],
           "backtest": None,
           "message": ""}

    mf = WEB / f"metrics_{mode}.json"
    if mf.exists():
        data = json.loads(mf.read_text())
        out["wrmsse"] = data.get("wrmsse")
        out["levels"] = data.get("levels", [])
    else:
        out["message"] = (
            "This window has no ground truth, so accuracy cannot be measured "
            "directly. Switch to the validation window for scored results."
        )

    bf = WEB / "backtest_future.json"
    if bf.exists() and mode == "future":
        out["backtest"] = json.loads(bf.read_text())

    ff = WEB / f"feature_importance_{mode}.csv"
    if ff.exists():
        fi = pd.read_csv(ff).head(20)
        fi.columns = [c.lower() for c in fi.columns]
        out["features"] = clean_records(fi)

    return out


# ============================================================
# EVENTS & PRICE
# ============================================================

@app.get("/events")
def events(mode: str = "future"):
    df = load_forecast(mode)
    daily = df.groupby("date", as_index=False)["forecast"].sum()

    cal_path = WEB / "calendar.parquet"
    marked, snap_rows = [], []

    if cal_path.exists():
        cal = pd.read_parquet(cal_path)
        cal["date"] = pd.to_datetime(cal["date"])
        merged = daily.merge(cal, on="date", how="left")

        ev = merged[merged["event_name_1"].notna()]
        base = merged.loc[merged["event_name_1"].isna(), "forecast"].mean()
        for _, r in ev.iterrows():
            marked.append({
                "date": clean_value(r["date"]),
                "event": str(r["event_name_1"]),
                "type": str(r.get("event_type_1", "")),
                "forecast": float(r["forecast"]),
                "vs_normal_pct": (float(r["forecast"] / base - 1) * 100
                                  if base else None),
            })

        for st, col in (("CA", "snap_CA"), ("TX", "snap_TX"), ("WI", "snap_WI")):
            if col not in cal.columns or "state_id" not in df.columns:
                continue
            sub = (df[df["state_id"].astype(str) == st]
                   .groupby("date", as_index=False)["forecast"].sum()
                   .merge(cal[["date", col]], on="date", how="left"))
            on = sub.loc[sub[col] == 1, "forecast"].mean()
            off = sub.loc[sub[col] == 0, "forecast"].mean()
            if pd.notna(on) and pd.notna(off) and off:
                snap_rows.append({
                    "state": st,
                    "snap_day": float(on),
                    "non_snap_day": float(off),
                    "uplift_pct": float((on / off - 1) * 100),
                })

    dow = daily.copy()
    dow["day"] = dow["date"].dt.day_name()
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]
    prof = dow.groupby("day")["forecast"].mean().reindex(order)
    weekly = [{"day": d, "forecast": float(v)}
              for d, v in prof.items() if pd.notna(v)]

    price_points = []
    pp = WEB / "prices.parquet"
    if pp.exists() and {"item_id", "store_id"} <= set(df.columns):
        prices = pd.read_parquet(pp)
        top = (df.groupby(["item_id", "store_id"], observed=True,
                          as_index=False)["forecast"].sum()
                 .sort_values("forecast", ascending=False).head(300))
        m = top.merge(prices, on=["item_id", "store_id"], how="inner")
        m["item_id"] = m["item_id"].astype(str)
        m["store_id"] = m["store_id"].astype(str)
        price_points = clean_records(m.head(250))

    return {"mode": mode, "events": marked, "snap": snap_rows,
            "weekly_profile": weekly, "price_points": price_points}


# ============================================================
# SERIES EXPLORER
# ============================================================

@app.get("/series/search")
def series_search(q: str = "", mode: str = "future", limit: int = 50):
    df = load_forecast(mode)
    q = q.strip().lower()
    if not q:
        return {"matches": 0, "data": []}

    mask = pd.Series(False, index=df.index)
    for c in ("id", "item_id", "store_id", "state_id", "cat_id", "dept_id"):
        if c in df.columns:
            mask |= df[c].astype(str).str.lower().str.contains(q, regex=False)
    hits = df[mask]

    grouped = pd.DataFrame()
    if "id" in hits.columns and not hits.empty:
        grouped = hits.groupby("id", observed=True, as_index=False)["forecast"] \
                      .agg(["sum", "mean", "max"])
        grouped.columns = ["id", "total", "avg", "peak"]
        grouped = grouped.sort_values("total", ascending=False).head(limit)
        grouped["id"] = grouped["id"].astype(str)

    return {"matches": int(hits["id"].nunique()) if "id" in hits.columns else 0,
            "data": clean_records(grouped) if not grouped.empty else []}


@app.get("/series/detail")
def series_detail(series_id: str, mode: str = "future"):
    df = load_forecast(mode)
    sub = df[df["id"].astype(str) == series_id].sort_values("date")
    if sub.empty:
        raise HTTPException(404, "Series not found.")

    hist = []
    hp = WEB / "history.parquet"
    if hp.exists():
        h = pd.read_parquet(hp)
        row = h[h["id"].astype(str) == series_id]
        if not row.empty:
            cal = pd.read_parquet(WEB / "calendar.parquet")
            cal["date"] = pd.to_datetime(cal["date"])
            dmap = cal.set_index("d")["date"].to_dict()
            r = row.iloc[0]
            for c in row.columns:
                if c.startswith("d_") and c in dmap:
                    hist.append({"date": dmap[c].isoformat(),
                                 "sales": float(r[c])})
            hist = sorted(hist, key=lambda x: x["date"])[-90:]

    return {
        "id": series_id,
        "forecast": clean_records(sub[["date", "forecast"]]),
        "history": hist,
        "total": float(sub["forecast"].sum()),
        "peak": float(sub["forecast"].max()),
    }


# ============================================================
# EXPORT
# ============================================================

@app.get("/export")
def export(mode: str = "future", state: str = "", store: str = "",
           category: str = "", department: str = "", item: str = "",
           fmt: str = "long"):
    df = apply_filters(load_forecast(mode), state, store, category,
                       department, item)
    if fmt == "wide" and {"id", "horizon"} <= set(df.columns):
        df = df.pivot_table(index="id", columns="horizon",
                            values="forecast").reset_index()
        df.columns = ["id"] + [f"F{c}" for c in df.columns[1:]]
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition":
                 f'attachment; filename="m5_forecast_{mode}_{fmt}.csv"'},
    )


@app.get("/forecast")
def forecast_rows(mode: str = "future", limit: int = Query(500, le=5000),
                  offset: int = 0, state: str = "", store: str = "",
                  category: str = "", department: str = "", item: str = ""):
    df = apply_filters(load_forecast(mode), state, store, category,
                       department, item)
    return {"mode": mode, "total_rows": len(df), "offset": offset,
            "limit": limit,
            "data": clean_records(df.iloc[offset:offset + limit])}


# ============================================================
# FRONTEND  (mounted last so API routes win)
# ============================================================

if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
