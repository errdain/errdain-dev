FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system errdain && adduser --system --ingroup errdain errdain

COPY pyproject.toml README.md ./
COPY backend ./backend
COPY config ./config
COPY errdain ./errdain
COPY retail_generator.py ./retail_generator.py

RUN pip install --upgrade pip && pip install ".[parquet]"

RUN mkdir -p /var/lib/errdain/output && chown -R errdain:errdain /var/lib/errdain /app

USER errdain

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3)"]

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
