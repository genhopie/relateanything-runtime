# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RELATEANYTHING_UPSTREAM_PATH=/opt/RelateAnything \
    RELATEANYTHING_ARTIFACT_ROOT=/opt/artifacts

RUN apt-get update && apt-get install -y --no-install-recommends \
    git ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md LICENSE NOTICE THIRD_PARTY_NOTICES.md ./
COPY src ./src
COPY scripts ./scripts

RUN pip install --no-cache-dir -e ".[dev]"

ARG RELSGG_UPSTREAM_GIT=e9ea42aed60f766f12ad19d51709129c50110a3b
RUN git clone https://github.com/maelic/RelateAnything.git "${RELATEANYTHING_UPSTREAM_PATH}" \
    && cd "${RELATEANYTHING_UPSTREAM_PATH}" \
    && git fetch --depth 1 origin "${RELSGG_UPSTREAM_GIT}" \
    && git checkout "${RELSGG_UPSTREAM_GIT}" \
    && pip install --no-cache-dir -e ".[hub]"

# Artifact download is performed at image build time in deployment pipelines using
# scripts/fetch_artifacts.sh with checksum verification (not committed to Base).
RUN mkdir -p /opt/artifacts/relation /opt/artifacts/detector

EXPOSE 8080
CMD ["uvicorn", "relateanything_runtime.api:app", "--host", "0.0.0.0", "--port", "8080"]
