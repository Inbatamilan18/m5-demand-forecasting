# ============================================================
# M5 RETAIL DEMAND FORECASTING - FASTAPI BACKEND
# ============================================================

FROM python:3.11-slim

# Prevent Python from creating unnecessary files
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1

# ------------------------------------------------------------
# System dependencies
# ------------------------------------------------------------

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# Working directory
# ------------------------------------------------------------

WORKDIR /app

# ------------------------------------------------------------
# Install Python dependencies
# ------------------------------------------------------------

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------
# Copy backend
# ------------------------------------------------------------

COPY backend/ ./backend/

# ------------------------------------------------------------
# Copy forecasting data
# ------------------------------------------------------------

COPY web_data/ ./web_data/

# ------------------------------------------------------------
# Copy database
# ------------------------------------------------------------

COPY users.db ./users.db

# ------------------------------------------------------------
# Render provides PORT automatically
# ------------------------------------------------------------

ENV PORT=8000

EXPOSE 8000

# ------------------------------------------------------------
# Start FastAPI
# ------------------------------------------------------------

CMD uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port ${PORT}