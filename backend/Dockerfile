FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Веса скачиваются на этапе сборки: в рантайме интернет не нужен
COPY scripts/ scripts/
RUN python scripts/download_models.py --dest /app/models

COPY app/ app/
COPY tools/ tools/
COPY config/ config/

RUN useradd --create-home --uid 10001 appuser && mkdir -p /data && chown appuser /data
USER appuser

ENV MODEL_PATH=/app/models/yolox_s.onnx \
    RULESET=room \
    ANALYSIS_FPS=2.5 \
    PROCESSING_BUDGET_SEC=120 \
    DATA_DIR=/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*", "--timeout-keep-alive", "75"]
