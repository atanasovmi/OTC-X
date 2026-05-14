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
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# System packages: curl for healthcheck, tini for proper PID-1 signal handling
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl tini \
    && rm -rf /var/lib/apt/lists/*

# Create the unprivileged runtime user upfront so subsequent COPYs can chown directly
RUN useradd --create-home --shell /bin/bash app

WORKDIR /app

# Runtime dependencies installed as root — site-packages owned by root,
# readable by 'app' but not writable (defence-in-depth: the running app
# cannot tamper with its own dependencies).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application source and pre-built data artefacts
COPY --chown=app:app backend/ ./backend/
COPY --chown=app:app frontend/ ./frontend/

# Drop privileges before exposing the service
USER app

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# tini owns PID 1 so SIGTERM/SIGINT are forwarded cleanly to Streamlit on
# `docker stop`, avoiding a SIGKILL after the 10-second grace period.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["streamlit", "run", "frontend/app.py"]
