# ============================================================
# M5 RETAIL DEMAND FORECASTING - FASTAPI + STATIC FRONTEND
# ============================================================
# Build:  docker build -t m5-dashboard .
# Run:    docker run -p 8000:8000 m5-dashboard
# ============================================================

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Runtime deps only - no lightgbm / scikit-learn / streamlit.
# Training happens on your laptop; the container only serves results.
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY backend/   ./backend/
COPY frontend/  ./frontend/
COPY web_data/  ./web_data/

# Cloud platforms inject $PORT. Default to 8000 for local runs.
ENV PORT=8000
EXPOSE 8000

CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT} --workers 1