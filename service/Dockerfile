# TTCC sheet service — FastAPI + headless Chromium, wrapping the Python engine.
# Build from the repo root:  docker build -f service/Dockerfile -t ttcc-sheet-service .
# Run:  docker run -e TTCC_SERVICE_TOKEN=... -p 8000:8000 ttcc-sheet-service
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers

WORKDIR /app

# Install Python deps and the Chromium build Playwright drives. --with-deps
# pulls the OS libraries headless Chromium needs.
COPY service/requirements.txt /app/service/requirements.txt
RUN pip install -r service/requirements.txt \
    && playwright install --with-deps chromium

# Engine is copied unchanged; the service imports it directly.
COPY engine/ /app/engine/
COPY service/ /app/service/

EXPOSE 8000

# Healthcheck hits /healthz (no auth required there).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"

CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000"]
