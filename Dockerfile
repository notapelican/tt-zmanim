# TTCC sheet service — FastAPI + headless Chromium, wrapping the Python engine.
# Lives at the repo root (its build context is the whole repo: it copies engine/
# and service/). Root placement lets `gcloud run deploy --source .` auto-detect it.
# Build:  docker build -t ttcc-sheet-service .
# Run:    docker run -e TTCC_SERVICE_TOKEN=... -p 8000:8000 ttcc-sheet-service
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

# Healthcheck hits /healthz (no auth required there). Honors $PORT so it stays
# correct on hosts that inject one; Cloud Run uses its own probes and ignores this.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python3 -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/healthz').status==200 else 1)"

# Shell form so ${PORT} expands. Cloud Run injects PORT (default 8080); falls
# back to 8000 for local/VPS runs. The same image runs unchanged everywhere.
CMD ["sh", "-c", "exec uvicorn service.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
