# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /build
RUN pip install --no-cache-dir uv==0.5.*

COPY pyproject.toml ./
RUN uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python -e .

FROM python:3.12-slim AS runtime

RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
