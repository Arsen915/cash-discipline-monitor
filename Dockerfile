FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY backend/scripts ./scripts
COPY backend/app ./app
COPY backend/tools ./tools
COPY backend/config ./config

RUN python scripts/download_models.py --dest /app/models

RUN useradd --create-home --uid 10001 appuser && mkdir -p /data && chown appuser /data
USER appuser

ENV MODEL_PATH=/app/models/yolox_s.onnx \
    RULESET=room \
    ANALYSIS_FPS=2.5 \
    PROCESSING_BUDGET_SEC=120 \
    DATA_DIR=/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv('PORT', '8000')}/api/health', timeout=3)"

CMD ["sh", "-c", "uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*' --timeout-keep-alive 75"]
