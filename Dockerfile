FROM python:3.12-slim AS base

WORKDIR /app

# System deps — cached independently from Python deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libzbar0 \
    && rm -rf /var/lib/apt/lists/*

# Python deps — cached unless requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code — copied last so code changes don't bust earlier layers
COPY backend/ ./backend/
COPY frontend/ ./frontend/

EXPOSE 8080

# Cloud Run injects $PORT; fall back to 8080 for local runs
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
