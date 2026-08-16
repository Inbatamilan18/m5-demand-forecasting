"""Retail Demand Forecasting dashboard.

Run:
    streamlit run app_deploy.py
"""

import json
import hashlib
import secrets
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import config as C


# =============================================================
# PAGE CONFIG
# =============================================================

st.set_page_config(
    page_title="Retail Demand Forecasting | M5",
    page_icon="📦",
    layout="wide",
)

WEB = C.ROOT / "web_data"
DB_PATH = C.ROOT / "users.db"


# =============================================================
# CSS
# =============================================================

CSS = """
<style>

.stApp {
    background: #0b1120;
    color: #e5e7eb;
}

.block-container {
    max-width: 1400px;
    padding-top: 4rem !important;
    padding-bottom: 3rem;
}

#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

h1, h2, h3 {
    color: #f8fafc !important;
}

.hdr {
    font-size: 2.4rem;
    font-weight: 800;
    color: #f8fafc;
    margin-bottom: 4px;
}

.sub {
    color: #94a3b8;
    font-size: 1rem;
    margin-top: 0;
}

section[data-testid="stSidebar"] {
    background: #111827;
    border-right: 1px solid #1f2937;
}

section[data-testid="stSidebar"] * {
    color: #e5e7eb;
}

div[data-testid="stMetric"] {
    background: #111827 !important;
    border: 1px solid #263244 !important;
    border-radius: 14px !important;
    padding: 12px 20px !important;
    min-height: 90px !important;
}

div[data-testid="stMetricLabel"] {
    color: #e2e8f0 !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
}

div[data-testid="stMetricValue"] {
    color: #ffffff !important;
    font-size: 1.7rem !important;
    font-weight: 800 !important;
}

.stButton > button {
    width: 100%;
    border-radius: 10px;
    border: 1px solid #2563eb;
    background: #2563eb;
    color: white;
    font-weight: 700;
    padding: 0.65rem 1rem;
}

.stButton > button:hover {
    background: #1d4ed8;
}

.info-card {
    background: linear-gradient(145deg, #111827, #172033);
    border: 1px solid #263244;
    border-radius: 16px;
    padding: 24px;
    min-height: 145px;
    margin-bottom: 18px;
}

.hero {
    background: linear-gradient(135deg, #111827, #0f172a);
    border: 1px solid #263244;
    border-radius: 22px;
    padding: 42px;
    margin-bottom: 28px;
}

</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


# =============================================================
# USER DATABASE / AUTHENTICATION
# =============================================================

def get_db():
    """Create/open the local SQLite user database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    return conn


def hash_password(password: str, salt: bytes) -> str:
    """Secure password hashing using PBKDF2-HMAC-SHA256."""
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        200_000,
    )
    return hashed.hex()


def create_user(username: str, password: str) -> bool:
    username = username.strip()

    salt = secrets.token_bytes(16)
    password_hash = hash_password(password, salt)

    conn = get_db()

    try:
        conn.execute(
            """
            INSERT INTO users (username, salt, password_hash)
            VALUES (?, ?, ?)
            """,
            (
                username,
                salt.hex(),
                password_hash,
            ),
        )
        conn.commit()
        return True

    except sqlite3.IntegrityError:
        return False

    finally:
        conn.close()


def check_login(username: str, password: str) -> bool:
    username = username.strip()

    conn = get_db()

    row = conn.execute(
        """
        SELECT salt, password_hash
        FROM users
        WHERE username = ?
        """,
        (username,),
    ).fetchone()

    conn.close()

    if row is None:
        return False

    salt = bytes.fromhex(row[0])
    stored_hash = row[1]

    calculated_hash = hash_password(password, salt)

    return secrets.compare_digest(
        calculated_hash,
        stored_hash,
    )


# =============================================================
# SESSION STATE
# =============================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "show_dashboard" not in st.session_state:
    st.session_state.show_dashboard = False

if "username" not in st.session_state:
    st.session_state.username = ""


# =============================================================
# LOGIN / SIGN-UP PAGE
# =============================================================

if not st.session_state.logged_in:

    st.markdown(
        """
        <div style="
            max-width:600px;
            margin:55px auto 25px auto;
            text-align:center;
        ">
            <div style="font-size:3rem;">📦</div>
            <h1 style="font-size:2.3rem;">
                M5 Retail Demand Forecasting
            </h1>
            <p style="
                color:#94a3b8;
                font-size:1.05rem;
            ">
                Walmart Retail Demand Forecasting Dashboard
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:

        login_tab, signup_tab = st.tabs(
            ["🔐 Login", "📝 Create Account"]
        )

        # -----------------------------------------------------
        # LOGIN
        # -----------------------------------------------------

        with login_tab:

            st.markdown("### Welcome back")

            login_username = st.text_input(
                "Username",
                key="login_username",
                placeholder="Enter your username",
            )

            login_password = st.text_input(
                "Password",
                type="password",
                key="login_password",
                placeholder="Enter your password",
            )

            if st.button(
                "Login",
                key="login_button",
                use_container_width=True,
                type="primary",
            ):

                if not login_username or not login_password:
                    st.warning(
                        "Please enter both username and password."
                    )

                elif check_login(
                    login_username,
                    login_password,
                ):

                    st.session_state.logged_in = True
                    st.session_state.username = (
                        login_username.strip()
                    )
                    st.session_state.show_dashboard = False

                    st.rerun()

                else:
                    st.error(
                        "❌ Invalid username or password."
                    )

        # -----------------------------------------------------
        # SIGN UP
        # -----------------------------------------------------

        with signup_tab:

            st.markdown("### Create your account")

            new_username = st.text_input(
                "Username",
                key="signup_username",
                placeholder="Choose a username",
            )

            new_password = st.text_input(
                "Password",
                type="password",
                key="signup_password",
                placeholder="Create a password",
            )

            confirm_password = st.text_input(
                "Confirm password",
                type="password",
                key="signup_confirm_password",
                placeholder="Re-enter your password",
            )

            if st.button(
                "Create Account",
                key="signup_button",
                use_container_width=True,
                type="primary",
            ):

                clean_username = new_username.strip()

                if not clean_username or not new_password:
                    st.warning(
                        "Please fill in all fields."
                    )

                elif len(clean_username) < 3:
                    st.warning(
                        "Username must contain at least 3 characters."
                    )

                elif len(new_password) < 6:
                    st.warning(
                        "Password must contain at least 6 characters."
                    )

                elif new_password != confirm_password:
                    st.error(
                        "❌ Passwords do not match."
                    )

                elif create_user(
                    clean_username,
                    new_password,
                ):
                    st.success(
                        "✅ Account created successfully! "
                        "Go to the Login tab and sign in."
                    )

                else:
                    st.error(
                        "❌ That username already exists."
                    )

    st.stop()


# =============================================================
# M5 INFORMATION PAGE
# =============================================================

if not st.session_state.show_dashboard:

    st.markdown(
        """
        <div class="hdr">
            🏪 Walmart M5 Retail Demand Forecasting
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <p class="sub">
        Demand forecasting using historical sales, calendar events,
        prices and machine learning.
        </p>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    st.markdown("## 📊 About the M5 Dataset")

    st.write(
        """
        The Walmart M5 forecasting problem focuses on predicting
        future product demand across Walmart stores.

        The dataset combines historical sales information with
        calendar events and product pricing information to generate
        a 28-day demand forecast.
        """
    )

    st.markdown("## 🏪 Dataset Overview")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("States", "3")
    c2.metric("Stores", "10")
    c3.metric("Categories", "3")
    c4.metric("Departments", "7")

    c5, c6, c7 = st.columns(3)

    c5.metric("Items", "3,049")
    c6.metric("Item × Store Series", "30,490")
    c7.metric("Forecast Horizon", "28 Days")

    st.markdown("---")

    st.markdown("## 🇺🇸 Walmart Locations")

    st.write(
        "The dataset contains stores from three states:"
    )

    states_info = pd.DataFrame(
        {
            "State Code": ["CA", "TX", "WI"],
            "State": [
                "California",
                "Texas",
                "Wisconsin",
            ],
        }
    )

    st.dataframe(
        states_info,
        width="stretch",
        hide_index=True,
    )

    st.markdown("## 🔄 Forecasting Pipeline")

    pipeline = [
        "1. Data Ingestion",
        "2. Data Validation",
        "3. Data Cleaning",
        "4. Sales + Calendar + Price Data Merging",
        "5. Exploratory Data Analysis",
        "6. Feature Engineering",
        "7. Time-Based Train / Validation Split",
        "8. LightGBM Forecasting Model",
        "9. WRMSSE Evaluation",
        "10. 28-Day Demand Forecast",
    ]

    for step in pipeline:
        st.write("✅ " + step)

    st.markdown("---")

    st.markdown("## 🧠 Model Features")

    features_info = pd.DataFrame(
        {
            "Feature Group": [
                "Historical Demand",
                "Rolling Statistics",
                "Calendar",
                "Events",
                "Price",
                "Store / Item Information",
            ],
            "Examples": [
                "Lag 28, Lag 56, Lag 364",
                "7, 14, 28, 60, 180-day means",
                "Day of week, week of year",
                "Holiday / event information",
                "Price and relative price",
                "Item, department, category, store, state",
            ],
        }
    )

    st.dataframe(
        features_info,
        width="stretch",
        hide_index=True,
    )

    st.markdown("---")

    if st.button(
        "🚀 Open Forecasting Dashboard",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.show_dashboard = True
        st.rerun()

    st.stop()


# =============================================================
# DATA LOADING
# =============================================================

@st.cache_data(show_spinner=False)
def load(mode: str):

    fc_p = WEB / f"forecast_{mode}.parquet"

    if not fc_p.exists():
        return None

    fc = pd.read_parquet(fc_p)

    mets = (
        json.loads(
            (WEB / f"metrics_{mode}.json").read_text()
        )
        if (WEB / f"metrics_{mode}.json").exists()
        else None
    )

    meta = (
        json.loads(
            (WEB / f"train_meta_{mode}.json").read_text()
        )
        if (WEB / f"train_meta_{mode}.json").exists()
        else {}
    )

    imp_p = WEB / f"feature_importance_{mode}.csv"

    imp = (
        pd.read_csv(imp_p)
        if imp_p.exists()
        else None
    )

    return fc, mets, meta, imp


@st.cache_data(show_spinner=False)
def load_hierarchy(mode: str):

    f = WEB / f"hierarchy_{mode}.parquet"

    if not f.exists():
        return None

    return pd.read_parquet(f)


@st.cache_data(show_spinner=False)
def load_calendar():

    f = WEB / "calendar.parquet"

    if not f.exists():
        return None

    cal = pd.read_parquet(f)
    cal["date"] = pd.to_datetime(cal["date"])

    keep = [
        "date",
        "event_name_1",
        "event_type_1",
        "event_name_2",
        "snap_CA",
        "snap_TX",
        "snap_WI",
    ]

    return cal[
        [c for c in keep if c in cal.columns]
    ]


@st.cache_data(show_spinner=False)
def load_prices_for(
    items: tuple[str, ...],
    stores: tuple[str, ...],
):

    f = WEB / "prices.parquet"

    if not f.exists() or not items or not stores:
        return None

    try:

        return pd.read_parquet(
            f,
            columns=[
                "item_id",
                "store_id",
                "sell_price",
            ],
            filters=[
                ("item_id", "in", list(items)),
                ("store_id", "in", list(stores)),
            ],
        )

    except Exception:

        pr = pd.read_parquet(
            f,
            columns=[
                "item_id",
                "store_id",
                "sell_price",
            ],
        )

        return pr[
            pr["item_id"].isin(items)
            & pr["store_id"].isin(stores)
        ]


@st.cache_data(show_spinner=False)
def load_history(
    ids: tuple[str, ...],
    n_days: int = 120,
):

    f = WEB / "history.parquet"

    if not f.exists() or not ids:
        return None

    try:

        import pyarrow.parquet as pq

        columns = pq.ParquetFile(
            f
        ).schema.names

    except Exception:

        columns = list(
            pd.read_parquet(
                f,
                columns=["id"],
            ).columns
        )

    day = [
        c
        for c in columns
        if c.startswith("d_")
    ][-n_days:]

    read_cols = ["id"] + day

    try:

        df = pd.read_parquet(
            f,
            columns=read_cols,
            filters=[
                ("id", "in", list(ids)),
            ],
        )

    except Exception:

        df = pd.read_parquet(
            f,
            columns=read_cols,
        )

        df = df[
            df["id"].isin(ids)
        ]

    if df.empty:
        return None

    df = df.set_index("id")

    cal = pd.read_parquet(
        WEB / "calendar.parquet",
        columns=["d", "date"],
    )

    cal["date"] = pd.to_datetime(
        cal["date"]
    )

    cal = cal.set_index("d")["date"]

    out = df.T
    out.index = cal.reindex(
        out.index
    ).values

    return out


# =============================================================
# SIDEBAR
# =============================================================

st.sidebar.title("📦 Demand Forecasting")

st.sidebar.caption(
    f"Logged in as: {st.session_state.username}"
)

if st.sidebar.button(
    "🚪 Logout",
    use_container_width=True,
):

    st.session_state.logged_in = False
    st.session_state.show_dashboard = False
    st.session_state.username = ""

    st.rerun()


mode = st.sidebar.selectbox(
    "Forecast window",
    list(C.MODES.keys()),
    index=list(C.MODES.keys()).index(C.MODE),
    help=(
        "validation/evaluation have ground truth. "
        "future = 20-Jun to 17-Jul 2016."
    ),
)

data = load(mode)

if data is None:

    st.warning(
        f"No forecast data bundled for **{mode}**. "
        "Run `python -m src.export_web` locally and redeploy."
    )

    st.stop()

fc, mets, meta, imp = data


# =============================================================
# FILTERS
# =============================================================

st.sidebar.markdown("### Filters")

states = st.sidebar.multiselect(
    "State",
    sorted(fc["state_id"].unique()),
)

f = (
    fc[
        fc["state_id"].isin(states)
    ]
    if states
    else fc
)

stores = st.sidebar.multiselect(
    "Store",
    sorted(f["store_id"].unique()),
)

f = (
    f[
        f["store_id"].isin(stores)
    ]
    if stores
    else f
)

cats = st.sidebar.multiselect(
    "Category",
    sorted(f["cat_id"].unique()),
)

f = (
    f[
        f["cat_id"].isin(cats)
    ]
    if cats
    else f
)

depts = st.sidebar.multiselect(
    "Department",
    sorted(f["dept_id"].unique()),
)

f = (
    f[
        f["dept_id"].isin(depts)
    ]
    if depts
    else f
)

items = st.sidebar.multiselect(
    "Item ID",
    sorted(f["item_id"].unique()),
)

f = (
    f[
        f["item_id"].isin(items)
    ]
    if items
    else f
)


# =============================================================
# HEADER
# =============================================================

st.markdown(
    '<p class="hdr">Retail Demand Forecasting</p>',
    unsafe_allow_html=True,
)

st.markdown(
    f'<p class="sub">Walmart M5 · 28-day ahead · '
    f'{meta.get("first_date", "?")} → '
    f'{meta.get("last_date", "?")} · '
    f'mode <b>{mode}</b></p>',
    unsafe_allow_html=True,
)


# =============================================================
# TOP METRICS
# =============================================================

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Series forecast",
    f"{f['id'].nunique():,}",
)

c2.metric(
    "Total units (28d)",
    f"{f['forecast'].sum():,.0f}",
)

c3.metric(
    "Avg units/day",
    f"{f.groupby('date')['forecast'].sum().mean():,.0f}",
)

c4.metric(
    "WRMSSE",
    f"{mets['wrmsse']:.4f}" if mets else "n/a",
    help=(
        "Weighted RMSSE averaged over the "
        "12 M5 hierarchy levels. Lower is better."
    ),
)


# =============================================================
# TABS
# =============================================================

tabs = st.tabs(
    [
        "📈 Forecast",
        "🏬 Hierarchy",
        "🎯 Accuracy",
        "🎄 Events & Price",
        "🔎 Series explorer",
        "⬇️ Export",
    ]
)


# =============================================================
# FORECAST TAB
# =============================================================

with tabs[0]:

    daily = (
        f.groupby(
            "date",
            as_index=False,
        )["forecast"]
        .sum()
    )

    fig = go.Figure(
        go.Scatter(
            x=daily["date"],
            y=daily["forecast"],
            mode="lines+markers",
            name="Forecast",
            line=dict(
                width=3,
                color="#2563eb",
            ),
        )
    )

    fig.update_layout(
        height=380,
        margin=dict(t=30, b=10),
        title="Total daily demand — next 28 days",
        yaxis_title="units",
        template="plotly_white",
    )

    st.plotly_chart(
        fig,
        width="stretch",
    )

    a, b = st.columns(2)

    with a:

        by = (
            f.groupby(
                "cat_id",
                observed=True,
                as_index=False,
            )["forecast"]
            .sum()
        )

        st.plotly_chart(
            go.Figure(
                go.Bar(
                    x=by["cat_id"],
                    y=by["forecast"],
                    marker_color="#0ea5e9",
                )
            ).update_layout(
                title="By category",
                height=320,
                template="plotly_white",
                margin=dict(t=40),
            ),
            width="stretch",
        )

    with b:

        by = (
            f.groupby(
                "store_id",
                observed=True,
                as_index=False,
            )["forecast"]
            .sum()
            .sort_values(
                "forecast",
                ascending=False,
            )
        )

        st.plotly_chart(
            go.Figure(
                go.Bar(
                    x=by["store_id"],
                    y=by["forecast"],
                    marker_color="#6366f1",
                )
            ).update_layout(
                title="By store",
                height=320,
                template="plotly_white",
                margin=dict(t=40),
            ),
            width="stretch",
        )

    st.markdown(
        "#### Top 20 items by forecast volume"
    )

    top = (
        f.groupby(
            ["item_id", "store_id"],
            observed=True,
            as_index=False,
        )["forecast"]
        .sum()
        .sort_values(
            "forecast",
            ascending=False,
        )
        .head(20)
    )

    top["forecast"] = top[
        "forecast"
    ].round(1)

    st.dataframe(
        top,
        width="stretch",
        hide_index=True,
    )


# =============================================================
# HIERARCHY TAB
# =============================================================

with tabs[1]:

    hier = load_hierarchy(mode)

    if hier is None:

        st.info(
            "Run `python -m src.evaluate` "
            "to build hierarchy aggregates."
        )

    else:

        lvl = st.selectbox(
            "Aggregation level",
            sorted(
                hier["level"].unique()
            ),
        )

        h = hier[
            hier["level"] == lvl
        ]

        tot = (
            h.groupby(
                "node",
                as_index=False,
            )["forecast"]
            .sum()
            .sort_values(
                "forecast",
                ascending=False,
            )
        )

        pick = st.multiselect(
            "Nodes",
            tot["node"].tolist(),
            default=tot[
                "node"
            ].head(6).tolist(),
        )

        fig = go.Figure()

        for n in pick:

            s = h[
                h["node"] == n
            ]

            fig.add_scatter(
                x=s["date"],
                y=s["forecast"],
                mode="lines",
                name=n,
            )

        fig.update_layout(
            height=420,
            template="plotly_white",
            title=f"{lvl} — 28-day forecast",
            yaxis_title="units",
        )

        st.plotly_chart(
            fig,
            width="stretch",
        )

        st.caption(
            "Forecasts are produced at item×store level "
            "and summed upward (bottom-up reconciliation), "
            "so every level is coherent by construction."
        )

        st.dataframe(
            tot.head(50),
            width="stretch",
            hide_index=True,
        )


# =============================================================
# ACCURACY TAB
# =============================================================

with tabs[2]:

    if mets is None:

        st.info(
            "This window has no ground truth, so accuracy "
            "cannot be measured. Switch to validation or evaluation."
        )

    else:

        m = pd.DataFrame(
            mets["levels"]
        )

        st.metric(
            "Overall WRMSSE",
            f"{mets['wrmsse']:.4f}",
        )

        st.plotly_chart(
            go.Figure(
                go.Bar(
                    x=m["level"],
                    y=m["rmsse"],
                    marker_color="#10b981",
                )
            ).update_layout(
                title="RMSSE by hierarchy level",
                height=380,
                template="plotly_white",
                xaxis_tickangle=-40,
            ),
            width="stretch",
        )

        st.dataframe(
            m.round(4),
            width="stretch",
            hide_index=True,
        )

    if imp is not None:

        st.markdown(
            "#### Feature importance (gain)"
        )

        t = imp.head(20).iloc[::-1]

        st.plotly_chart(
            go.Figure(
                go.Bar(
                    x=t["gain"],
                    y=t["feature"],
                    orientation="h",
                    marker_color="#f59e0b",
                )
            ).update_layout(
                height=500,
                template="plotly_white",
                margin=dict(l=140, t=20),
            ),
            width="stretch",
        )


# =============================================================
# EVENTS & PRICE TAB
# =============================================================

with tabs[3]:

    st.markdown(
        "#### How external covariates drive the forecast"
    )

    st.caption(
        "Price, promotion, holiday, event and SNAP signals "
        "are used by the forecasting pipeline."
    )

    cal = load_calendar()

    daily = (
        f.groupby(
            "date",
            as_index=False,
        )["forecast"]
        .sum()
    )

    if cal is not None:

        d = daily.merge(
            cal,
            on="date",
            how="left",
        )

        ev = d[
            d["event_name_1"].notna()
        ]

        fig = go.Figure()

        fig.add_scatter(
            x=d["date"],
            y=d["forecast"],
            mode="lines",
            name="Forecast",
            line=dict(
                color="#2563eb",
                width=3,
            ),
        )

        for _, r in ev.iterrows():

            fig.add_vline(
                x=r["date"],
                line_dash="dot",
                line_color="#ef4444",
            )

            fig.add_annotation(
                x=r["date"],
                y=d["forecast"].max(),
                text=r["event_name_1"],
                showarrow=False,
                textangle=-90,
                xshift=-8,
                font=dict(
                    size=10,
                    color="#ef4444",
                ),
                yanchor="top",
            )

        fig.update_layout(
            height=400,
            template="plotly_white",
            title="Forecast with calendar events marked",
            yaxis_title="units",
            margin=dict(t=50),
        )

        st.plotly_chart(
            fig,
            width="stretch",
        )

        if len(ev):

            st.markdown(
                "**Events inside this forecast window**"
            )

            tbl = ev[
                [
                    "date",
                    "event_name_1",
                    "event_type_1",
                    "forecast",
                ]
            ].copy()

            base = d.loc[
                d["event_name_1"].isna(),
                "forecast",
            ].mean()

            tbl["vs non-event avg"] = (
                (tbl["forecast"] / base - 1) * 100
            ).map(
                lambda v: f"{v:+.1f}%"
            )

            tbl["date"] = tbl[
                "date"
            ].dt.date

            tbl["forecast"] = tbl[
                "forecast"
            ].round(0)

            st.dataframe(
                tbl,
                width="stretch",
                hide_index=True,
            )

        else:

            st.info(
                "No calendar events fall inside this window."
            )

        state_col = {
            "CA": "snap_CA",
            "TX": "snap_TX",
            "WI": "snap_WI",
        }

        rows = []

        for stt, col in state_col.items():

            if col not in d.columns:
                continue

            sub = (
                f[
                    f["state_id"] == stt
                ]
                .groupby(
                    "date",
                    as_index=False,
                )["forecast"]
                .sum()
            )

            sub = sub.merge(
                cal[
                    ["date", col]
                ],
                on="date",
                how="left",
            )

            on = sub.loc[
                sub[col] == 1,
                "forecast",
            ].mean()

            off = sub.loc[
                sub[col] == 0,
                "forecast",
            ].mean()

            if (
                pd.notna(on)
                and pd.notna(off)
                and off
            ):

                rows.append(
                    {
                        "state": stt,
                        "SNAP day": round(on),
                        "non-SNAP day": round(off),
                        "uplift": (
                            f"{(on / off - 1) * 100:+.1f}%"
                        ),
                    }
                )

        if rows:

            st.markdown(
                "**SNAP benefit-day effect**"
            )

            st.dataframe(
                pd.DataFrame(rows),
                width="stretch",
                hide_index=True,
            )

    st.markdown(
        "#### Weekly seasonality learned by the model"
    )

    dow = f.copy()

    dow["day"] = dow[
        "date"
    ].dt.day_name()

    order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]

    prof = (
        dow.groupby(
            ["day", "date"],
            observed=True,
        )["forecast"]
        .sum()
        .groupby("day")
        .mean()
        .reindex(order)
    )

    st.plotly_chart(
        go.Figure(
            go.Bar(
                x=prof.index,
                y=prof.values,
                marker_color="#8b5cf6",
            )
        ).update_layout(
            height=320,
            template="plotly_white",
            yaxis_title="avg units/day",
            margin=dict(t=20),
        ),
        width="stretch",
    )

    st.markdown(
        "#### Price sensitivity"
    )

    top_items = (
        f.groupby(
            ["item_id", "store_id"],
            observed=True,
        )["forecast"]
        .sum()
        .sort_values(
            ascending=False,
        )
        .head(200)
        .reset_index()
    )

    pr = load_prices_for(
        tuple(
            top_items[
                "item_id"
            ].unique()[:40]
        ),
        tuple(
            top_items[
                "store_id"
            ].unique()
        ),
    )

    if pr is not None and len(pr):

        last = (
            pr[
                [
                    "item_id",
                    "store_id",
                    "sell_price",
                ]
            ]
            .drop_duplicates(
                [
                    "item_id",
                    "store_id",
                ]
            )
        )

        m = top_items.merge(
            last,
            on=[
                "item_id",
                "store_id",
            ],
            how="inner",
        )

        if len(m) > 5:

            st.plotly_chart(
                go.Figure(
                    go.Scatter(
                        x=m["sell_price"],
                        y=m["forecast"],
                        mode="markers",
                        marker=dict(
                            size=7,
                            color="#0ea5e9",
                            opacity=0.6,
                        ),
                        text=(
                            m["item_id"]
                            + " @ "
                            + m["store_id"]
                        ),
                        hovertemplate=(
                            "%{text}<br>"
                            "$%{x:.2f}<br>"
                            "%{y:.0f} units"
                        ),
                    )
                ).update_layout(
                    height=360,
                    template="plotly_white",
                    xaxis_title="sell price ($)",
                    yaxis_title="28-day forecast (units)",
                    title=(
                        "Higher-priced items forecast "
                        "lower volume"
                    ),
                    margin=dict(t=50),
                ),
                width="stretch",
            )

    st.caption(
        "Price enters the model as absolute price, "
        "item-relative price and department-relative price."
    )


# =============================================================
# SERIES EXPLORER
# =============================================================

with tabs[4]:

    ids = sorted(
        f["id"].unique()
    )

    if not ids:

        st.warning(
            "No series available for the selected filters."
        )

    else:

        sel = st.selectbox(
            f"Pick a series ({len(ids):,} available)",
            ids,
        )

        s = (
            fc[
                fc["id"] == sel
            ]
            .sort_values("date")
        )

        hist = load_history(
            (sel,)
        )

        fig = go.Figure()

        if hist is not None and not hist.empty:

            fig.add_scatter(
                x=hist.index,
                y=hist[sel],
                mode="lines",
                name="History",
                line=dict(
                    color="#94a3b8",
                ),
            )

        fig.add_scatter(
            x=s["date"],
            y=s["forecast"],
            mode="lines+markers",
            name="Forecast",
            line=dict(
                color="#2563eb",
                width=3,
            ),
        )

        fig.update_layout(
            height=420,
            template="plotly_white",
            title=sel,
            yaxis_title="units sold",
        )

        st.plotly_chart(
            fig,
            width="stretch",
        )

        k1, k2, k3 = st.columns(3)

        k1.metric(
            "28-day total",
            f"{s['forecast'].sum():,.1f}",
        )

        k2.metric(
            "Peak day",
            f"{s['forecast'].max():,.1f}",
        )

        if hist is not None and not hist.empty:

            base = hist[
                sel
            ].tail(28).sum()

            k3.metric(
                "vs last 28 days",
                f"{s['forecast'].sum():,.0f}",
                (
                    f"{(s['forecast'].sum()/base - 1)*100:+.1f}%"
                    if base
                    else "n/a"
                ),
            )


# =============================================================
# EXPORT TAB
# =============================================================

with tabs[5]:

    st.markdown(
        "#### Download forecasts"
    )

    wide = f.pivot_table(
        index="id",
        columns="horizon",
        values="forecast",
    )

    wide.columns = [
        f"F{c}"
        for c in wide.columns
    ]

    st.download_button(
        "⬇️ Wide format (Kaggle submission style)",
        wide.reset_index().to_csv(index=False),
        f"submission_{mode}.csv",
        "text/csv",
    )

    st.download_button(
        "⬇️ Long format (id, date, forecast)",
        f[
            [
                "id",
                "item_id",
                "store_id",
                "date",
                "forecast",
            ]
        ].to_csv(index=False),
        f"forecast_long_{mode}.csv",
        "text/csv",
    )

    st.dataframe(
        wide.head(50).round(2),
        width="stretch",
    )