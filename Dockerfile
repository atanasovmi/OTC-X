# syntax=docker/dockerfile:1.6
#
# OTC-X Liquiditäts-Radar — production container image.
# Build:  docker build -t ghcr.io/atanasovmi/otc-x:dev .
# Run:    docker run -p 8501:8501 ghcr.io/atanasovmi/otc-x:dev
#

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# System packages needed for the healthcheck and a few wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, so the layer caches across source changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application source and pre-built data artefacts.
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Drop root.
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "frontend/app.py"]
