# Production image for the always-on trading service.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY core ./core
COPY agents ./agents
COPY app ./app
COPY data ./data
COPY memory ./memory
COPY knowledge ./knowledge
COPY scripts ./scripts

RUN pip install --upgrade pip && pip install ".[research]"

EXPOSE 8080

ENV PORT=8080 AUTO_START=true
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
