FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    YOLO_CONFIG_DIR=/tmp/ultralytics \
    MPLCONFIGDIR=/tmp/matplotlib \
    DETECTOR_MODE=real \
    MODEL_PATH=/models/best.pt \
    INFERENCE_DEVICE=cpu

WORKDIR /app

# CPU wheels are installed from PyTorch's CPU index; no CUDA runtime is included.
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
      torch==2.8.0 torchvision==0.23.0
COPY requirements-production.txt .
RUN python -m pip install --no-cache-dir -r requirements-production.txt \
    && useradd --system --uid 10001 --create-home --shell /usr/sbin/nologin appuser

COPY --chown=appuser:appuser backend/ ./backend/
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)" || exit 1
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
