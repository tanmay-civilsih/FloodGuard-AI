FROM python:3.12.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock

RUN useradd --create-home --uid 10001 floodguard
COPY --chown=floodguard:floodguard . .
USER floodguard

EXPOSE 8000
CMD ["sh", "-c", "python -m floodguard.common.database_wait && alembic upgrade head && python -m floodguard.registry.seed && exec uvicorn apps.api.main:app --host 0.0.0.0 --port 8000"]
