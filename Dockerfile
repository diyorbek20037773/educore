# syntax=docker/dockerfile:1.7
# EDUCORE image: one image, many commands (web, worker, worker-ai, worker-media, beat, ingestor, migrate).

FROM python:3.12-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    FASTEMBED_CACHE_DIR=/app/.cache/fastembed
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 ffmpeg libmagic1 curl tini gettext \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --home-dir /home/app app
WORKDIR /app

# ---------------------------------------------------------------------------------------------------
FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /uvx /bin/
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
# INSTALL_DEV=1 adds the dev group (pytest, ruff, …) for the local compose image; prod omits it.
ARG INSTALL_DEV=0
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$INSTALL_DEV" = "1" ]; then uv sync --frozen --no-install-project; \
    else uv sync --frozen --no-install-project --no-dev; fi
COPY . .
# Tailwind standalone binary (downloaded by django-tailwind-cli) → static/css/output.css, then collectstatic.
RUN DJANGO_SETTINGS_MODULE=config.settings.dev SECRET_KEY=build-only-dummy \
        python manage.py tailwind build \
    && DJANGO_SETTINGS_MODULE=config.settings.dev SECRET_KEY=build-only-dummy \
        python manage.py collectstatic --noinput --verbosity 0 \
    && rm -rf .django_tailwind_cli

# ---------------------------------------------------------------------------------------------------
FROM base AS final
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.title="educore" \
      org.opencontainers.image.revision=$GIT_SHA
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=app:app /app /app
RUN chmod +x /app/docker/entrypoint.sh \
    && mkdir -p /data/media /data/private /data/telegram /app/.cache/fastembed /tmp/prom \
    && chown -R app:app /data /app/.cache /tmp/prom
USER app
EXPOSE 8000
ENTRYPOINT ["tini", "--", "/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "4", \
     "--timeout", "60", "--access-logfile", "-"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz | grep -q '"ok"' || exit 1
