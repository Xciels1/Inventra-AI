# ─────────────────────────────────────────────────────────────
# Inventra AI — Dockerfile (Backend FastAPI)
# Build: docker build -t inventra-ai-backend .
# Run:   docker run -p 8000:8000 inventra-ai-backend
# ─────────────────────────────────────────────────────────────

FROM python:3.11-slim

# Metadata
LABEL maintainer="Inventra AI Team"
LABEL description="Intelligent Inventory Decision Engine — Backend API"
LABEL version="1.0.0"

# Set working directory
WORKDIR /app

# Install system dependencies (untuk scikit-learn build)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy dan install Python dependencies terlebih dahulu
# (memanfaatkan Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY engine/    ./engine/
COPY api/       ./api/
COPY integrations/ ./integrations/

# Buat direktori untuk data dan logs
RUN mkdir -p /app/data /app/logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

# Environment variables default
ENV APP_ENV=production
ENV APP_PORT=8000
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Jalankan server dengan uvicorn
CMD ["uvicorn", "api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info", \
     "--access-log"]
