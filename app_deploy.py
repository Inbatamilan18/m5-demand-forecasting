"""Retail Demand Forecasting dashboard.

Run:  streamlit run app.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import config as C

# ------------------------------------------------------------- data source
# This is the DEPLOYMENT copy of the dashboard. It reads a small precomputed
# bundle (built by src/export_web.py) instead of the 450 MB Kaggle CSVs, so
# the container stays light. app.py is the local version and is unchanged.
WEB = C.ROOT / "web_data"

st.set_page_config(page_title="Retail Demand Forecasting | M5",
                   page_icon="📦", layout="wide")

CSS = """
<style>
  .block-container {padding-top: 2rem;}
  div[data-testid="stMetricValue"] {font-size: 1.6rem;}
  .hdr {font-size:2rem;font-weight:700;margin-bottom:0;}
  .sub {color:#6b7280;margin-top:0;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load(mode: str):
    fc_p = WEB / f"forecast_{mode}.parquet"
    if not fc_p.exists():
        return None
    fc = pd.read_parquet(fc_p)
    hier = pd.read_parquet(WEB / f"hierarchy_{mode}.parquet") \
        if (WEB / f"hierarchy_{mode}.parquet").exists() else None
    mets = json.loads((WEB / f"metrics_{mode}.json").read_text()) \
        if (WEB / f"metrics_{mode}.json").exists() else None
    meta = json.loads((WEB / f"train_meta_{mode}.json").read_text()) \
        if (WEB / f"train_meta_{mode}.json").exists() else {}
    imp_p = WEB / f"feature_importance_{mode}.csv"
    imp = pd.read_csv(imp_p) if imp_p.exists() else None
    return fc, hier, mets, meta, imp


@st.cache_data(show_spinner=False)
def load_calendar():
    """Calendar with event and SNAP flags, from the bundle."""
    f = WEB / "calendar.parquet"
    if not f.exists():
        return None
    cal = pd.read_parquet(f)
    cal["date"] = pd.to_datetime(cal["date"])
    keep = ["date", "event_name_1", "event_type_1", "event_name_2",
            "snap_CA", "snap_TX", "snap_WI"]
    return cal[[c for c in keep if c in cal.columns]]


@st.cache_data(show_spinner=False)
def load_prices_for(items: tuple[str, ...], stores: tuple[str, ...]):
    """Latest sell_price per item x store, from the bundle."""
    f = WEB / "prices.parquet"
    if not f.exists():
        return None
    pr = pd.read_parquet(f)
    return pr[pr["item_id"].isin(items) & pr["store_id"].isin(stores)]


@st.cache_data(show_spinner=False)
def load_history(ids: tuple[str, ...], n_days: int = 120):
    f = WEB / "history.parquet"
    if not f.exists():
        return None
    df = pd.read_parquet(f)
    df = df[df["id"].isin(ids)].set_index("id")
    cal = pd.read_parquet(WEB / "calendar.parquet")
    cal["date"] = pd.to_datetime(cal["date"])
    cal = cal.set_index("d")["date"]
    day = [c for c in df.columns if c.startswith("d_")]
    df = df[day[-n_days:]]
    out = df.T
    out.index = cal.reindex(out.index).values
    return out


# ---------------------------------------------------------------- sidebar
st.sidebar.title("📦 Demand Forecasting")
mode = st.sidebar.selectbox(
    "Forecast window", list(C.MODES.keys()),
    index=list(C.MODES.keys()).index(C.MODE),
    help="validation/evaluation have ground truth. future = 20-Jun to 17-Jul 2016.",
)

data = load(mode)
if data is None:
    st.warning(f"No forecast data bundled for **{mode}**. "
               f"Run `python -m src.export_web` locally and redeploy.")
    st.stop()

fc, hier, mets, meta, imp = data

st.sidebar.markdown("### Filters")
states = st.sidebar.multiselect("State", sorted(fc["state_id"].unique()))
f = fc[fc["state_id"].isin(states)] if states else fc
stores = st.sidebar.multiselect("Store", sorted(f["store_id"].unique()))
f = f[f["store_id"].isin(stores)] if stores else f
cats = st.sidebar.multiselect("Category", sorted(f["cat_id"].unique()))
f = f[f["cat_id"].isin(cats)] if cats else f
depts = st.sidebar.multiselect("Department", sorted(f["dept_id"].unique()))
f = f[f["dept_id"].isin(depts)] if depts else f

st.markdown('<p class="hdr">Retail Demand Forecasting</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub">Walmart M5 · 28-day ahead · '
            f'{meta.get("first_date","?")} → {meta.get("last_date","?")} · '
            f'mode <b>{mode}</b></p>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Series forecast", f"{f['id'].nunique():,}")
c2.metric("Total units (28d)", f"{f['forecast'].sum():,.0f}")
c3.metric("Avg units/day", f"{f.groupby('date')['forecast'].sum().mean():,.0f}")
c4.metric("WRMSSE", f"{mets['wrmsse']:.4f}" if mets else "n/a",
          help="Weighted RMSSE averaged over the 12 M5 hierarchy levels. Lower is better.")

tabs = st.tabs(["📈 Forecast", "🏬 Hierarchy", "🎯 Accuracy",
                "🎄 Events & Price", "🔎 Series explorer", "⬇️ Export"])

# ------------------------------------------------------------- forecast tab
with tabs[0]:
    daily = f.groupby("date", as_index=False)["forecast"].sum()
    fig = go.Figure(go.Scatter(x=daily["date"], y=daily["forecast"],
                               mode="lines+markers", name="Forecast",
                               line=dict(width=3, color="#2563eb")))
    fig.update_layout(height=380, margin=dict(t=30, b=10),
                      title="Total daily demand — next 28 days",
                      yaxis_title="units", template="plotly_white")
    st.plotly_chart(fig, width="stretch")

    a, b = st.columns(2)
    with a:
        by = f.groupby("cat_id", observed=True, as_index=False)["forecast"].sum()
        st.plotly_chart(
            go.Figure(go.Bar(x=by["cat_id"], y=by["forecast"],
                             marker_color="#0ea5e9"))
            .update_layout(title="By category", height=320,
                           template="plotly_white", margin=dict(t=40)),
            width="stretch")
    with b:
        by = f.groupby("store_id", observed=True, as_index=False)["forecast"].sum() \
              .sort_values("forecast", ascending=False)
        st.plotly_chart(
            go.Figure(go.Bar(x=by["store_id"], y=by["forecast"],
                             marker_color="#6366f1"))
            .update_layout(title="By store", height=320,
                           template="plotly_white", margin=dict(t=40)),
            width="stretch")

    st.markdown("#### Top 20 items by forecast volume")
    top = (f.groupby(["item_id", "store_id"], observed=True, as_index=False)
             ["forecast"].sum().sort_values("forecast", ascending=False).head(20))
    top["forecast"] = top["forecast"].round(1)
    st.dataframe(top, width="stretch", hide_index=True)

# ------------------------------------------------------------ hierarchy tab
with tabs[1]:
    if hier is None:
        st.info("Run `python -m src.evaluate` to build hierarchy aggregates.")
    else:
        lvl = st.selectbox("Aggregation level", sorted(hier["level"].unique()))
        h = hier[hier["level"] == lvl]
        tot = (h.groupby("node", as_index=False)["forecast"].sum()
                .sort_values("forecast", ascending=False))
        pick = st.multiselect("Nodes", tot["node"].tolist(),
                              default=tot["node"].head(6).tolist())
        fig = go.Figure()
        for n in pick:
            s = h[h["node"] == n]
            fig.add_scatter(x=s["date"], y=s["forecast"], mode="lines", name=n)
        fig.update_layout(height=420, template="plotly_white",
                          title=f"{lvl} — 28-day forecast", yaxis_title="units")
        st.plotly_chart(fig, width="stretch")
        st.caption("Forecasts are produced at item×store level and summed "
                   "upward (bottom-up reconciliation), so every level is "
                   "coherent by construction.")
        st.dataframe(tot.head(50), width="stretch", hide_index=True)

# ------------------------------------------------------------- accuracy tab
with tabs[2]:
    if mets is None:
        st.info("This window has no ground truth, so accuracy cannot be "
                "measured. Switch to *validation* or *evaluation*.")
    else:
        m = pd.DataFrame(mets["levels"])
        st.metric("Overall WRMSSE", f"{mets['wrmsse']:.4f}")
        st.plotly_chart(
            go.Figure(go.Bar(x=m["level"], y=m["rmsse"], marker_color="#10b981"))
            .update_layout(title="RMSSE by hierarchy level", height=380,
                           template="plotly_white", xaxis_tickangle=-40),
            width="stretch")
        st.dataframe(m.round(4), width="stretch", hide_index=True)
    if imp is not None:
        st.markdown("#### Feature importance (gain)")
        t = imp.head(20).iloc[::-1]
        st.plotly_chart(
            go.Figure(go.Bar(x=t["gain"], y=t["feature"], orientation="h",
                             marker_color="#f59e0b"))
            .update_layout(height=500, template="plotly_white",
                           margin=dict(l=140, t=20)),
            width="stretch")

# --------------------------------------------------------- events tab
with tabs[3]:
    st.markdown("#### How external covariates drive the forecast")
    st.caption("The brief asks the model to use price, promotion and holiday "
               "signals. These charts show those effects in the output, not "
               "just in the feature list.")

    cal = load_calendar()
    daily = f.groupby("date", as_index=False)["forecast"].sum()

    if cal is not None:
        d = daily.merge(cal, on="date", how="left")
        ev = d[d["event_name_1"].notna()]

        fig = go.Figure()
        fig.add_scatter(x=d["date"], y=d["forecast"], mode="lines",
                        name="Forecast", line=dict(color="#2563eb", width=3))
        for _, r in ev.iterrows():
            fig.add_vline(x=r["date"], line_dash="dot", line_color="#ef4444")
            fig.add_annotation(x=r["date"], y=d["forecast"].max(),
                               text=r["event_name_1"], showarrow=False,
                               textangle=-90, xshift=-8, font=dict(size=10,
                               color="#ef4444"), yanchor="top")
        fig.update_layout(height=400, template="plotly_white",
                          title="Forecast with calendar events marked",
                          yaxis_title="units", margin=dict(t=50))
        st.plotly_chart(fig, width="stretch")

        if len(ev):
            st.markdown("**Events inside this forecast window**")
            tbl = ev[["date", "event_name_1", "event_type_1", "forecast"]].copy()
            base = d.loc[d["event_name_1"].isna(), "forecast"].mean()
            tbl["vs non-event avg"] = ((tbl["forecast"] / base - 1) * 100) \
                .map(lambda v: f"{v:+.1f}%")
            tbl["date"] = tbl["date"].dt.date
            tbl["forecast"] = tbl["forecast"].round(0)
            st.dataframe(tbl, width="stretch", hide_index=True)
        else:
            st.info("No calendar events fall inside this window.")

        # ---- SNAP effect
        state_col = {"CA": "snap_CA", "TX": "snap_TX", "WI": "snap_WI"}
        rows = []
        for stt, col in state_col.items():
            if col not in d.columns:
                continue
            sub = f[f["state_id"] == stt].groupby("date", as_index=False)["forecast"].sum()
            sub = sub.merge(cal[["date", col]], on="date", how="left")
            on = sub.loc[sub[col] == 1, "forecast"].mean()
            off = sub.loc[sub[col] == 0, "forecast"].mean()
            if pd.notna(on) and pd.notna(off) and off:
                rows.append({"state": stt, "SNAP day": round(on),
                             "non-SNAP day": round(off),
                             "uplift": f"{(on / off - 1) * 100:+.1f}%"})
        if rows:
            st.markdown("**SNAP benefit-day effect** "
                        "(food-stamp disbursement days drive grocery demand)")
            st.dataframe(pd.DataFrame(rows), width="stretch",
                         hide_index=True)

    # ---- day-of-week profile
    st.markdown("#### Weekly seasonality learned by the model")
    dow = f.copy()
    dow["day"] = dow["date"].dt.day_name()
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]
    prof = (dow.groupby(["day", "date"], observed=True)["forecast"].sum()
              .groupby("day").mean().reindex(order))
    st.plotly_chart(
        go.Figure(go.Bar(x=prof.index, y=prof.values, marker_color="#8b5cf6"))
        .update_layout(height=320, template="plotly_white",
                       yaxis_title="avg units/day", margin=dict(t=20)),
        width="stretch")

    # ---- price vs demand
    st.markdown("#### Price sensitivity")
    top_items = (f.groupby(["item_id", "store_id"], observed=True)["forecast"]
                   .sum().sort_values(ascending=False).head(200).reset_index())
    pr = load_prices_for(tuple(top_items["item_id"].unique()[:40]),
                         tuple(top_items["store_id"].unique()))
    if pr is not None and len(pr):
        # prices.parquet is intentionally exported as the latest price
        # per item x store, so it does not contain a "date" column.
        # Do not sort by date here.
        last = pr[["item_id", "store_id", "sell_price"]].drop_duplicates(
            ["item_id", "store_id"]
        )
        m = top_items.merge(last, on=["item_id", "store_id"], how="inner")
        if len(m) > 5:
            st.plotly_chart(
                go.Figure(go.Scatter(
                    x=m["sell_price"], y=m["forecast"], mode="markers",
                    marker=dict(size=7, color="#0ea5e9", opacity=0.6),
                    text=m["item_id"] + " @ " + m["store_id"],
                    hovertemplate="%{text}<br>$%{x:.2f}<br>%{y:.0f} units"))
                .update_layout(height=360, template="plotly_white",
                               xaxis_title="sell price ($)",
                               yaxis_title="28-day forecast (units)",
                               title="Higher-priced items forecast lower volume",
                               margin=dict(t=50)),
                width="stretch")
    st.caption("Price enters the model as three features: absolute price, "
               "price relative to the item's own average (promotion signal), "
               "and price relative to the department average.")


# ------------------------------------------------------- series explorer tab
with tabs[4]:
    ids = sorted(f["id"].unique())
    sel = st.selectbox(f"Pick a series ({len(ids):,} available)", ids)
    s = fc[fc["id"] == sel].sort_values("date")
    hist = load_history((sel,))
    fig = go.Figure()
    if hist is not None and not hist.empty:
        fig.add_scatter(x=hist.index, y=hist[sel], mode="lines",
                        name="History", line=dict(color="#94a3b8"))
    fig.add_scatter(x=s["date"], y=s["forecast"], mode="lines+markers",
                    name="Forecast", line=dict(color="#2563eb", width=3))
    fig.update_layout(height=420, template="plotly_white",
                      title=sel, yaxis_title="units sold")
    st.plotly_chart(fig, width="stretch")
    k1, k2, k3 = st.columns(3)
    k1.metric("28-day total", f"{s['forecast'].sum():,.1f}")
    k2.metric("Peak day", f"{s['forecast'].max():,.1f}")
    if hist is not None and not hist.empty:
        base = hist[sel].tail(28).sum()
        k3.metric("vs last 28 days", f"{s['forecast'].sum():,.0f}",
                  f"{(s['forecast'].sum()/base - 1)*100:+.1f}%" if base else "n/a")

# --------------------------------------------------------------- export tab
with tabs[5]:
    st.markdown("#### Download forecasts")
    wide = f.pivot_table(index="id", columns="horizon", values="forecast")
    wide.columns = [f"F{c}" for c in wide.columns]
    st.download_button("⬇️ Wide format (Kaggle submission style)",
                       wide.reset_index().to_csv(index=False),
                       f"submission_{mode}.csv", "text/csv")
    st.download_button("⬇️ Long format (id, date, forecast)",
                       f[["id", "item_id", "store_id", "date", "forecast"]]
                       .to_csv(index=False),
                       f"forecast_long_{mode}.csv", "text/csv")
    st.dataframe(wide.head(50).round(2), width="stretch")