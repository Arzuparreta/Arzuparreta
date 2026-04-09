FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    systemd \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY db ./db
COPY ingestor ./ingestor
COPY embedder ./embedder
COPY query ./query
COPY eval ./eval
COPY tools ./tools
COPY logpilot ./logpilot
COPY alembic.ini ./
COPY alembic ./alembic
COPY docker ./docker

RUN pip install --no-cache-dir -U pip setuptools wheel \
    && pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["/app/docker/entrypoint.sh"]
