# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /build
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# requirements.txt is copied before the app code so this layer stays cached
# across ordinary code changes.
COPY requirements.txt .
# The BuildKit cache mount persists pip's *download* cache between builds, so
# adding or bumping one package no longer re-downloads every wheel. The mount
# lives outside the image, so this costs nothing in final image size - which is
# why --no-cache-dir is deliberately absent here.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
    && pip install -r requirements.txt


FROM python:3.12-slim

# ffmpeg powers the audio preprocessing in app/services/audio_service.py:
# transcoding to 16 kHz mono Opus, silence detection for chunk boundaries, and
# cutting chunks that would otherwise exceed the STT provider's size limit.
# The alternative for silence detection (Silero VAD) needs torch at ~800 MB.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app && adduser --system --ingroup app app
WORKDIR /app

COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

RUN chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).getcode() == 200 else sys.exit(1)"

# Run migrations before serving so a fresh container always has a schema
# that matches the current code (see alembic/versions/ - this replaced the
# old Base.metadata.create_all-on-boot approach in app/main.py).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
