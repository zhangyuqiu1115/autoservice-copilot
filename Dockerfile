FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/app/data/home

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app

COPY requirements.txt ./
RUN python -m pip install --only-binary=:all: -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
COPY evaluation ./evaluation
COPY sample_documents ./sample_documents
COPY alembic.ini pyproject.toml ./

RUN mkdir -p /app/data/uploads /app/data/qdrant /app/data/models /app/data/home \
    && chown -R app:app /app/data

USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "scripts.serve", "--host", "0.0.0.0", "--port", "8000"]
