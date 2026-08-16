# ============================================================
# M5 RETAIL DEMAND FORECASTING - FASTAPI BACKEND
# ============================================================

from pathlib import Path
import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
import json

import pandas as pd

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web_data"
FRONTEND = ROOT / "frontend"

# DB_PATH lets you point at a Render persistent disk (/var/data/users.db).
DB = Path(os.getenv("DB_PATH", ROOT / "users.db"))
DB.parent.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="M5 Retail Demand Forecasting API", version="3.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "salt" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN salt TEXT")
    conn.commit()
    conn.close()


init_database()


def hash_password(password: str):
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return salt.hex(), h.hex()


def verify_password(password, stored_hash, stored_salt=None):
    try:
        if stored_salt:
            salt = bytes.fromhex(stored_salt)
            h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
            return hmac.compare_digest(h.hex(), stored_hash)
        if ":" in stored_hash:
            salt_hex, hash_hex = stored_hash.split(":", 1)
            h = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                    bytes.fromhex(salt_hex), 120_000)
            return hmac.compare_digest(h.hex(), hash_hex)
        return False
    except Exception:
        return False


def seed_users():
    """Create demo accounts listed in SEED_USERS (user:pass,user:pass)."""
    spec = os.getenv("SEED_USERS", "").strip()
    if not spec:
        return
    conn = get_connection()
    try:
        for pair in spec.split(","):
            if ":" not in pair:
                continue
            u, p = pair.split(":", 1)
            u, p = u.strip(), p.strip()
            if not u or not p:
                continue
            if conn.execute("SELECT 1 FROM users WHERE username=?", (u,)).fetchone():
                continue
            salt, h = hash_password(p)
            conn.execute(
                "INSERT INTO users (username,password_hash,salt,created_at)"
                " VALUES (?,?,?,?)",
                (u, h, salt, datetime.now(timezone.utc).isoformat()),
            )
            print(f"[seed] created user '{u}'")
        conn.commit()
    finally:
        conn.close()


seed_users()


# ============================================================
# TOKENS
# ============================================================
# Signed, stateless tokens: they survive a container restart, unlike a
# module-level dict.

SECRET = os.getenv("SECRET_KEY", secrets.token_hex(32))


def create_token(username: str) -> str:
    exp = int((datetime.now(timezone.utc) + timedelta(hours=12)).timestamp())
    payload = f"{username}|{exp}"
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"


security = HTTPBearer()


def get_current_user(cred: HTTPAuthorizationCredentials = Depends(security)):
    try:
        username, exp, sig = cred.credentials.rsplit("|", 2)
    except ValueError:
        raise HTTPException(401, "Invalid token")
    expected = hmac.new(SECRET.encode(), f"{username}|{exp}".encode(),
                        hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(401, "Invalid token")
    if int(exp) < datetime.now(timezone.utc).timestamp():
        raise HTTPException(401, "Token expired")
    return username


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


# ============================================================
# AUTH ROUTES
# ============================================================

@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/auth/register")
def register(data: RegisterRequest):
    username = data.username.strip()
    if len(username) < 3:
        raise HTTPException(400, "Username must contain at least 3 characters.")
    if len(data.password) < 6:
        raise HTTPException(400, "Password must contain at least 6 characters.")
    conn = get_connection()
    try:
        if conn.execute("SELECT id FROM users WHERE username=?",
                        (username,)).fetchone():
            raise HTTPException(409, "Username already exists.")
        salt, h = hash_password(data.password)
        conn.execute(
            "INSERT INTO users (username,password_hash,salt,created_at)"
            " VALUES (?,?,?,?)",
            (username, h, salt, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return {"message": "Account created successfully.", "username": username}
    finally:
        conn.close()


@app.post("/auth/login")
def login(data: LoginRequest):
    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT username,password_hash,salt FROM users WHERE username=?",
            (data.username.strip(),),
        ).fetchone()
    finally:
        conn.close()
    if user is None or not verify_password(data.password, user["password_hash"],
                                           user["salt"]):
        raise HTTPException(401, "Invalid username or password.")
    return {"message": "Login successful.", "username": user["username"],
            "token": create_token(user["username"])}


@app.get("/auth/me")
def current_user(username: str = Depends(get_current_user)):
    return {"username": username}


# ============================================================
# DATA
# ============================================================

_CACHE: dict[str, pd.DataFrame] = {}
MODES = {"future", "validation", "evaluation"}


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
    _CACHE.clear()          # only ever hold one mode in memory
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
                     ("id", item)):
        if val and col in df.columns:
            df = df[df[col].astype(str) == str(val)]
    return df


def col_values(df, col):
    if col not in df.columns:
        return []
    return sorted({str(v) for v in df[col].dropna().unique()})


# ============================================================
# DASHBOARD  (one small payload - replaces the 190 MB /forecast)
# ============================================================

@app.get("/dashboard")
def dashboard(
    mode: str = "future",
    state: str = "",
    store: str = "",
    category: str = "",
    department: str = "",
    item: str = "",
    username: str = Depends(get_current_user),
):
    """Everything the UI renders, aggregated server-side.

    Returning the raw 853,720 rows would be ~190 MB of JSON and will OOM a
    small container, so all grouping happens here and only summaries travel.
    """
    full = load_forecast(mode)
    df = apply_filters(full, state, store, category, department, item)

    if df.empty:
        return {"user": username, "mode": mode, "total_units": 0,
                "series": 0, "avg_units_per_day": 0, "peak_day_units": 0,
                "peak_date": None, "daily": [], "by_category": [],
                "by_store": [], "top_items": [],
                "filters": {"states": [], "stores": [], "categories": [],
                            "departments": []}}

    daily = df.groupby("date", as_index=False)["forecast"].sum() \
              .sort_values("date")
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
    if "id" in df.columns:
        g = (df.groupby("id", observed=True, as_index=False)["forecast"].sum()
               .sort_values("forecast", ascending=False).head(20))
        g["id"] = g["id"].astype(str)
        top_items = clean_records(g)

    return {
        "user": username,
        "mode": mode,
        "total_units": float(df["forecast"].sum()),
        "series": int(df["id"].nunique()) if "id" in df.columns else 0,
        "avg_units_per_day": float(daily["forecast"].mean()),
        "peak_day_units": float(daily["forecast"].max()),
        "peak_date": clean_value(peak["date"]),
        "daily": clean_records(daily),
        "by_category": group("cat_id"),
        "by_store": group("store_id"),
        "top_items": top_items,
        "filters": {
            "states": col_values(full, "state_id"),
            "stores": col_values(full, "store_id"),
            "categories": col_values(full, "cat_id"),
            "departments": col_values(full, "dept_id"),
        },
    }


@app.get("/forecast")
def forecast(
    mode: str = "future",
    limit: int = Query(1000, le=5000),
    offset: int = 0,
    state: str = "", store: str = "", category: str = "",
    department: str = "", item: str = "",
    username: str = Depends(get_current_user),
):
    """Paginated raw rows. Hard-capped so the response can never blow up."""
    df = apply_filters(load_forecast(mode), state, store, category,
                       department, item)
    total = len(df)
    page = df.iloc[offset:offset + limit]
    return {"user": username, "mode": mode, "total_rows": total,
            "returned": len(page), "offset": offset, "limit": limit,
            "data": clean_records(page)}


@app.get("/series/search")
def series_search(q: str = "", mode: str = "future", limit: int = 100,
                  username: str = Depends(get_current_user)):
    df = load_forecast(mode)
    q = q.strip().lower()
    if q and "id" in df.columns:
        mask = df["id"].astype(str).str.lower().str.contains(q, regex=False)
        for c in ("store_id", "state_id", "cat_id"):
            if c in df.columns:
                mask |= df[c].astype(str).str.lower().str.contains(q, regex=False)
        df = df[mask]
    cols = [c for c in ("id", "store_id", "date", "forecast") if c in df.columns]
    return {"user": username, "matches": int(len(df)),
            "data": clean_records(df[cols].head(limit))}


@app.get("/export")
def export(mode: str = "future", state: str = "", store: str = "",
           category: str = "", department: str = "", item: str = "",
           username: str = Depends(get_current_user)):
    """CSV download streamed from the parquet - never held as JSON."""
    from fastapi.responses import StreamingResponse
    import io
    df = apply_filters(load_forecast(mode), state, store, category,
                       department, item)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition":
                 f'attachment; filename="m5_forecast_{mode}.csv"'},
    )


@app.get("/metrics")
def metrics(mode: str = "validation", username: str = Depends(get_current_user)):
    f = WEB / f"metrics_{mode}.json"
    if not f.exists():
        return {"user": username, "mode": mode, "metrics": {},
                "message": "No accuracy metrics available for this window."}
    return {"user": username, "mode": mode, "metrics": json.loads(f.read_text())}


@app.get("/hierarchy")
def hierarchy(mode: str = "future", username: str = Depends(get_current_user)):
    df = load_forecast(mode)
    return {"user": username,
            "states": col_values(df, "state_id"),
            "stores": col_values(df, "store_id"),
            "categories": col_values(df, "cat_id"),
            "departments": col_values(df, "dept_id"),
            "items": col_values(df, "item_id")[:500],
            "columns": list(df.columns)}


@app.get("/hierarchy/summary")
def hierarchy_summary(mode: str = "future",
                      username: str = Depends(get_current_user)):
    df = load_forecast(mode)
    levels = [{"level": "Total", "columns": [], "count": 1,
               "data": [{"forecast": float(df["forecast"].sum())}]}]

    def add(name, cols):
        cols = [c for c in cols if c in df.columns]
        if not cols:
            return
        g = df.groupby(cols, observed=True, dropna=False,
                       as_index=False)["forecast"].sum()
        n = len(g)
        g = g.sort_values("forecast", ascending=False).head(20)
        for c in cols:
            g[c] = g[c].astype(str)
        levels.append({"level": name, "columns": cols, "count": n,
                       "data": clean_records(g)})

    add("State", ["state_id"])
    add("Store", ["store_id"])
    add("Category", ["cat_id"])
    add("Department", ["dept_id"])
    add("State x Category", ["state_id", "cat_id"])
    add("State x Department", ["state_id", "dept_id"])
    add("Store x Category", ["store_id", "cat_id"])
    add("Store x Department", ["store_id", "dept_id"])
    add("Item", ["item_id"])
    add("Item x State", ["item_id", "state_id"])
    add("Item x Store", ["item_id", "store_id"])
    return {"user": username, "mode": mode, "levels": levels}


@app.get("/data-profile")
def data_profile(mode: str = "future",
                 username: str = Depends(get_current_user)):
    df = load_forecast(mode)
    names = [str(c).lower() for c in df.columns]
    return {"user": username, "profile": {
        "rows": len(df),
        "columns": list(df.columns),
        "date_min": clean_value(df["date"].min()) if "date" in df else None,
        "date_max": clean_value(df["date"].max()) if "date" in df else None,
        "series": int(df["id"].nunique()) if "id" in df else None,
        "states": len(col_values(df, "state_id")),
        "stores": len(col_values(df, "store_id")),
        "categories": len(col_values(df, "cat_id")),
        "departments": len(col_values(df, "dept_id")),
        "items": len(col_values(df, "item_id")),
        "external_features": {
            "price": any("price" in c for c in names),
            "promotion": any("promo" in c for c in names),
            "holiday": any("holiday" in c or "event" in c for c in names),
        },
    }}


# ============================================================
# FRONTEND  (mounted last so /auth, /dashboard etc. win)
# ============================================================

if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
else:
    @app.get("/")
    def no_frontend():
        return {"message": "M5 API running", "frontend": "not found"}
