from pathlib import Path
import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
import json

import pandas as pd

from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
)

from fastapi.middleware.cors import CORSMiddleware

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials,
)

from fastapi.staticfiles import StaticFiles

from fastapi.responses import FileResponse

from pydantic import BaseModel


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent.parent

WEB = ROOT / "web_data"

FRONTEND = ROOT / "frontend"

DB = ROOT / "users.db"


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="M5 Retail Demand Forecasting API",
    description=(
        "Backend API for Walmart M5 hierarchical "
        "retail demand forecasting."
    ),
    version="3.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# FRONTEND
# ============================================================

if FRONTEND.exists():

    app.mount(
        "/static",
        StaticFiles(directory=FRONTEND),
        name="static",
    )


# ============================================================
# DATABASE
# ============================================================

def get_connection():

    conn = sqlite3.connect(DB)

    conn.row_factory = sqlite3.Row

    return conn


def init_database():

    conn = get_connection()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    columns = [
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    ]

    if "salt" not in columns:

        conn.execute(
            "ALTER TABLE users ADD COLUMN salt TEXT"
        )

    conn.commit()

    conn.close()


init_database()


# ============================================================
# PASSWORD HASHING
# ============================================================

def hash_password(password: str):

    salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120_000,
    )

    return (
        salt.hex(),
        password_hash.hex(),
    )


def verify_password(
    password: str,
    stored_hash: str,
    stored_salt: str | None = None,
):

    try:

        # ----------------------------------------------------
        # New format
        # ----------------------------------------------------

        if stored_salt:

            salt = bytes.fromhex(
                stored_salt
            )

            password_hash = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt,
                120_000,
            )

            return hmac.compare_digest(
                password_hash.hex(),
                stored_hash,
            )


        # ----------------------------------------------------
        # Old compatibility format
        # ----------------------------------------------------

        if ":" in stored_hash:

            salt_hex, hash_hex = (
                stored_hash.split(
                    ":",
                    1,
                )
            )

            salt = bytes.fromhex(
                salt_hex
            )

            password_hash = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt,
                120_000,
            )

            return hmac.compare_digest(
                password_hash.hex(),
                hash_hex,
            )


        return False


    except Exception:

        return False


# ============================================================
# TOKEN SYSTEM
# ============================================================

TOKENS = {}


def create_token(username: str):

    token = secrets.token_urlsafe(32)

    TOKENS[token] = {

        "username": username,

        "expires": (
            datetime.now(timezone.utc)
            + timedelta(hours=12)
        ),
    }

    return token


security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials =
        Depends(security),
):

    token = credentials.credentials

    session = TOKENS.get(token)


    if session is None:

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )


    if (
        session["expires"]
        < datetime.now(timezone.utc)
    ):

        TOKENS.pop(
            token,
            None,
        )

        raise HTTPException(
            status_code=401,
            detail="Token expired",
        )


    return session["username"]


# ============================================================
# REQUEST MODELS
# ============================================================

class RegisterRequest(BaseModel):

    username: str

    password: str


class LoginRequest(BaseModel):

    username: str

    password: str


# ============================================================
# FRONTEND ROUTE
# ============================================================

@app.get("/")
def dashboard():

    index_file = (
        FRONTEND / "index.html"
    )

    if not index_file.exists():

        return {
            "message": (
                "M5 Retail Demand Forecasting API"
            ),
            "status": "running",
            "frontend": "not found",
        }

    return FileResponse(
        index_file
    )


# ============================================================
# FRONTEND FILE ROUTES
# ============================================================

@app.get("/app.js")
def frontend_app():

    app_file = (
        FRONTEND / "app.js"
    )

    if not app_file.exists():

        raise HTTPException(
            status_code=404,
            detail="app.js not found.",
        )

    return FileResponse(
        app_file,
        media_type="application/javascript",
    )


@app.get("/style.css")
def frontend_style():

    style_file = (
        FRONTEND / "style.css"
    )

    if not style_file.exists():

        raise HTTPException(
            status_code=404,
            detail="style.css not found.",
        )

    return FileResponse(
        style_file,
        media_type="text/css",
    )


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
    }


# ============================================================
# REGISTER
# ============================================================

@app.post("/auth/register")
def register(
    data: RegisterRequest,
):

    username = data.username.strip()


    if len(username) < 3:

        raise HTTPException(
            status_code=400,
            detail=(
                "Username must contain "
                "at least 3 characters."
            ),
        )


    if len(data.password) < 6:

        raise HTTPException(
            status_code=400,
            detail=(
                "Password must contain "
                "at least 6 characters."
            ),
        )


    conn = get_connection()


    try:

        existing = conn.execute(
            """
            SELECT id
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()


        if existing:

            raise HTTPException(
                status_code=409,
                detail="Username already exists.",
            )


        salt, password_hash = (
            hash_password(
                data.password
            )
        )


        conn.execute(
            """
            INSERT INTO users
            (
                username,
                password_hash,
                salt,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                username,
                password_hash,
                salt,
                datetime.now(
                    timezone.utc
                ).isoformat(),
            ),
        )


        conn.commit()


        return {

            "message":
                "Account created successfully.",

            "username":
                username,
        }


    finally:

        conn.close()


# ============================================================
# LOGIN
# ============================================================

@app.post("/auth/login")
def login(
    data: LoginRequest,
):

    conn = get_connection()


    try:

        user = conn.execute(
            """
            SELECT
                username,
                password_hash,
                salt
            FROM users
            WHERE username = ?
            """,
            (
                data.username.strip(),
            ),
        ).fetchone()


    finally:

        conn.close()


    if user is None:

        raise HTTPException(
            status_code=401,
            detail=(
                "Invalid username "
                "or password."
            ),
        )


    if not verify_password(
        data.password,
        user["password_hash"],
        user["salt"],
    ):

        raise HTTPException(
            status_code=401,
            detail=(
                "Invalid username "
                "or password."
            ),
        )


    token = create_token(
        user["username"]
    )


    return {

        "message":
            "Login successful.",

        "username":
            user["username"],

        "token":
            token,
    }


# ============================================================
# CURRENT USER
# ============================================================

@app.get("/auth/me")
def current_user(
    username: str =
        Depends(get_current_user),
):

    return {

        "username":
            username,
    }


# ============================================================
# LOAD FORECAST
# ============================================================

def load_forecast(
    mode: str,
):

    allowed_modes = {

        "future",

        "validation",

        "evaluation",
    }


    if mode not in allowed_modes:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid mode. "
                f"Choose from "
                f"{sorted(allowed_modes)}."
            ),
        )


    file_path = (
        WEB /
        f"forecast_{mode}.parquet"
    )


    if not file_path.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                f"Forecast data for "
                f"'{mode}' was not found."
            ),
        )


    try:

        df = pd.read_parquet(
            file_path
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to read forecast "
                f"data: {error}"
            ),
        )


    if "date" in df.columns:

        df["date"] = pd.to_datetime(
            df["date"]
        )


    return df


# ============================================================
# SAFE JSON VALUE
# ============================================================

def clean_value(value):

    if pd.isna(value):

        return None


    if isinstance(
        value,
        (
            pd.Timestamp,
            datetime,
        ),
    ):

        return value.isoformat()


    if hasattr(
        value,
        "item",
    ):

        try:

            return value.item()

        except Exception:

            pass


    return value


# ============================================================
# CLEAN RECORDS
# ============================================================

def clean_records(df):

    records = df.to_dict(
        orient="records"
    )


    cleaned = []


    for record in records:

        cleaned.append(

            {
                key:
                    clean_value(value)

                for key, value
                in record.items()
            }

        )


    return cleaned


# ============================================================
# FORECAST API
# ============================================================

@app.get("/forecast")
def forecast(

    mode: str = "future",

    username: str =
        Depends(get_current_user),
):

    df = load_forecast(
        mode
    )


    if "forecast" not in df.columns:

        raise HTTPException(
            status_code=500,
            detail=(
                "Forecast file does not "
                "contain 'forecast' column."
            ),
        )


    if "date" not in df.columns:

        raise HTTPException(
            status_code=500,
            detail=(
                "Forecast file does not "
                "contain 'date' column."
            ),
        )


    series_count = (

        int(
            df["id"].nunique()
        )

        if "id" in df.columns

        else 0
    )


    daily = (
        df.groupby("date")["forecast"]
        .sum()
    )


    return {

        "user":
            username,

        "mode":
            mode,

        "rows":
            len(df),

        "series":
            series_count,

        "total_units":
            float(
                df["forecast"].sum()
            ),

        "avg_units_per_day":
            float(
                daily.mean()
            ),

        "data":
            clean_records(df),
    }


# ============================================================
# FORECAST SUMMARY
# ============================================================

@app.get("/forecast/summary")
def forecast_summary(

    mode: str = "future",

    username: str =
        Depends(get_current_user),
):

    df = load_forecast(
        mode
    )


    if "forecast" not in df.columns:

        raise HTTPException(
            status_code=500,
            detail=(
                "Forecast column not "
                "found."
            ),
        )


    if "date" not in df.columns:

        raise HTTPException(
            status_code=500,
            detail=(
                "Date column not "
                "found."
            ),
        )


    daily = (

        df.groupby(
            "date",
            as_index=False,
        )["forecast"]

        .sum()
    )


    if daily.empty:

        return {

            "user":
                username,

            "mode":
                mode,

            "total_units":
                0,

            "series_forecast":
                0,

            "avg_units_per_day":
                0,

            "peak_day_units":
                0,

            "peak_date":
                None,

            "daily_forecast":
                [],
        }


    peak_row = daily.loc[
        daily["forecast"].idxmax()
    ]


    series_count = (

        int(
            df["id"].nunique()
        )

        if "id" in df.columns

        else 0
    )


    return {

        "user":
            username,

        "mode":
            mode,

        "total_units":
            float(
                df["forecast"].sum()
            ),

        "series_forecast":
            series_count,

        "avg_units_per_day":
            float(
                daily["forecast"].mean()
            ),

        "peak_day_units":
            float(
                daily["forecast"].max()
            ),

        "peak_date":
            clean_value(
                peak_row["date"]
            ),

        "daily_forecast":
            clean_records(
                daily
            ),
    }


# ============================================================
# METRICS
# ============================================================

@app.get("/metrics")
def metrics(

    mode: str = "validation",

    username: str =
        Depends(get_current_user),
):

    metrics_file = (
        WEB /
        f"metrics_{mode}.json"
    )


    if not metrics_file.exists():

        return {

            "user":
                username,

            "mode":
                mode,

            "message":
                (
                    "No accuracy metrics "
                    "available for this window."
                ),

            "metrics":
                {},
        }


    try:

        metrics_data = json.loads(
            metrics_file.read_text(
                encoding="utf-8"
            )
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to read metrics "
                f"file: {error}"
            ),
        )


    return {

        "user":
            username,

        "mode":
            mode,

        "metrics":
            metrics_data,
    }


# ============================================================
# UNIQUE VALUES
# ============================================================

def unique_values(
    df,
    column,
):

    if column not in df.columns:

        return []


    values = []


    for value in (
        df[column]
        .dropna()
        .unique()
    ):

        cleaned = clean_value(
            value
        )


        if cleaned is not None:

            values.append(
                cleaned
            )


    return sorted(
        values,
        key=lambda x: str(x),
    )


# ============================================================
# HIERARCHY
# ============================================================

@app.get("/hierarchy")
def hierarchy(

    username: str =
        Depends(get_current_user),
):

    df = load_forecast(
        "future"
    )


    return {

        "user":
            username,

        "states":
            unique_values(
                df,
                "state_id",
            ),

        "stores":
            unique_values(
                df,
                "store_id",
            ),

        "categories":
            unique_values(
                df,
                "cat_id",
            ),

        "departments":
            unique_values(
                df,
                "dept_id",
            ),

        "items":
            unique_values(
                df,
                "id",
            ),

        "columns":
            list(df.columns),
    }


# ============================================================
# HIERARCHY SUMMARY
#
# Standard M5 hierarchy levels:
#
# 1. Total
# 2. State
# 3. Store
# 4. Category
# 5. Department
# 6. State × Category
# 7. State × Department
# 8. Store × Category
# 9. Store × Department
# 10. Item
# 11. Item × State
# 12. Item × Store
# ============================================================

@app.get("/hierarchy/summary")
def hierarchy_summary(

    mode: str = "future",

    username: str =
        Depends(get_current_user),
):

    df = load_forecast(
        mode
    )


    if "forecast" not in df.columns:

        raise HTTPException(
            status_code=500,
            detail=(
                "Forecast column not "
                "found."
            ),
        )


    levels = []


    def add_level(
        name,
        columns,
    ):

        existing = [

            column

            for column in columns

            if column in df.columns
        ]


        if not existing:

            return


        grouped = (

            df.groupby(
                existing,
                dropna=False,
                as_index=False,
            )["forecast"]

            .sum()
        )


        grouped = (

            grouped

            .sort_values(
                "forecast",
                ascending=False,
            )

            .head(20)
        )


        levels.append(

            {

                "level":
                    name,

                "columns":
                    existing,

                "count":
                    len(grouped),

                "data":
                    clean_records(
                        grouped
                    ),
            }

        )


    # --------------------------------------------------------
    # LEVEL 1 — TOTAL
    # --------------------------------------------------------

    levels.append(

        {

            "level":
                "Total",

            "columns":
                [],

            "count":
                1,

            "data":
                [

                    {

                        "forecast":
                            float(
                                df["forecast"]
                                .sum()
                            )
                    }

                ],
        }

    )


    # --------------------------------------------------------
    # LEVEL 2 — STATE
    # --------------------------------------------------------

    add_level(
        "State",
        ["state_id"],
    )


    # --------------------------------------------------------
    # LEVEL 3 — STORE
    # --------------------------------------------------------

    add_level(
        "Store",
        ["store_id"],
    )


    # --------------------------------------------------------
    # LEVEL 4 — CATEGORY
    # --------------------------------------------------------

    add_level(
        "Category",
        ["cat_id"],
    )


    # --------------------------------------------------------
    # LEVEL 5 — DEPARTMENT
    # --------------------------------------------------------

    add_level(
        "Department",
        ["dept_id"],
    )


    # --------------------------------------------------------
    # LEVEL 6 — STATE × CATEGORY
    # --------------------------------------------------------

    add_level(
        "State × Category",
        [
            "state_id",
            "cat_id",
        ],
    )


    # --------------------------------------------------------
    # LEVEL 7 — STATE × DEPARTMENT
    # --------------------------------------------------------

    add_level(
        "State × Department",
        [
            "state_id",
            "dept_id",
        ],
    )


    # --------------------------------------------------------
    # LEVEL 8 — STORE × CATEGORY
    # --------------------------------------------------------

    add_level(
        "Store × Category",
        [
            "store_id",
            "cat_id",
        ],
    )


    # --------------------------------------------------------
    # LEVEL 9 — STORE × DEPARTMENT
    # --------------------------------------------------------

    add_level(
        "Store × Department",
        [
            "store_id",
            "dept_id",
        ],
    )


    # --------------------------------------------------------
    # LEVEL 10 — ITEM
    # --------------------------------------------------------

    add_level(
        "Item",
        ["id"],
    )


    # --------------------------------------------------------
    # LEVEL 11 — ITEM × STATE
    # --------------------------------------------------------

    add_level(
        "Item × State",
        [
            "id",
            "state_id",
        ],
    )


    # --------------------------------------------------------
    # LEVEL 12 — ITEM × STORE
    # --------------------------------------------------------

    add_level(
        "Item × Store",
        [
            "id",
            "store_id",
        ],
    )


    return {

        "user":
            username,

        "mode":
            mode,

        "levels":
            levels,
    }


# ============================================================
# DATA PROFILE
# ============================================================

@app.get("/data-profile")
def data_profile(

    username: str =
        Depends(get_current_user),
):

    df = load_forecast(
        "future"
    )


    profile = {}


    profile["rows"] = len(df)


    profile["columns"] = list(
        df.columns
    )


    profile["date_min"] = (

        clean_value(
            df["date"].min()
        )

        if "date" in df.columns

        else None
    )


    profile["date_max"] = (

        clean_value(
            df["date"].max()
        )

        if "date" in df.columns

        else None
    )


    profile["series"] = (

        int(
            df["id"].nunique()
        )

        if "id" in df.columns

        else None
    )


    profile["states"] = len(

        unique_values(
            df,
            "state_id",
        )
    )


    profile["stores"] = len(

        unique_values(
            df,
            "store_id",
        )
    )


    profile["categories"] = len(

        unique_values(
            df,
            "cat_id",
        )
    )


    profile["departments"] = len(

        unique_values(
            df,
            "dept_id",
        )
    )


    profile["items"] = len(

        unique_values(
            df,
            "id",
        )
    )


    # --------------------------------------------------------
    # EXTERNAL FEATURES
    # --------------------------------------------------------

    column_names = [

        str(column).lower()

        for column in df.columns
    ]


    profile["external_features"] = {

        "price":
            any(
                "price" in column
                for column in column_names
            ),

        "promotion":
            any(
                "promo" in column
                for column in column_names
            ),

        "holiday":
            any(
                (
                    "holiday" in column
                    or
                    "event" in column
                )

                for column in column_names
            ),
    }


    return {

        "user":
            username,

        "profile":
            profile,
    }