# ============================================================
# M5 RETAIL DEMAND FORECASTING - FASTAPI BACKEND + FRONTEND
# ============================================================

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Runtime deps only - no lightgbm / scikit-learn / streamlit.
# Training happens on your laptop; the container just serves results.
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY backend/   ./backend/
COPY frontend/  ./frontend/
COPY web_data/  ./web_data/

# users.db is NOT copied; the app creates it at startup.
# Set DB_PATH=/var/data/users.db with a Render disk to make it persist.

ENV PORT=8000
EXPOSE 8000

CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT} --workers 1
