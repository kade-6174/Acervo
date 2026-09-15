FROM python:3.13.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 10001 acervo \
    && useradd --uid 10001 --gid acervo --create-home --shell /usr/sbin/nologin acervo

COPY pyproject.toml README.md ./
COPY accounts ./accounts
COPY audit ./audit
COPY config ./config
COPY core ./core
COPY management_portal ./management_portal
COPY manage.py ./manage.py
COPY static ./static
COPY templates ./templates
COPY deploy ./deploy

RUN python -m pip install . \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R acervo:acervo /app/media /app/staticfiles \
    && chmod 0555 /app/deploy/entrypoint.sh

USER acervo

EXPOSE 8000

ENTRYPOINT ["/app/deploy/entrypoint.sh"]
