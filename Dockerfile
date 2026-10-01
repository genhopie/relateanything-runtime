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

RUN pip install --no-cache-dir -e ".[dev,inference]"

RUN git clone https://github.com/maelic/RelateAnything.git "${RELATEANYTHING_UPSTREAM_PATH}" \
    && pip install --no-cache-dir -e "${RELATEANYTHING_UPSTREAM_PATH}[hub]" \
    && git -C "${RELATEANYTHING_UPSTREAM_PATH}" rev-parse HEAD > /opt/relsgg-corresponding-source-git-revision.txt

RUN python scripts/fetch_artifacts.py \
    && python scripts/verify_artifact_pins.py \
    && python scripts/verify_tracker_wheel.py

EXPOSE 8080
CMD ["uvicorn", "relateanything_runtime.api:app", "--host", "0.0.0.0", "--port", "8080"]
