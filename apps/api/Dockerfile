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
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

USER app
EXPOSE 8000

# Shell form (not exec-form CMD ["..."]) so $PORT actually expands — Railway
# assigns a dynamic port via this env var and routes public traffic to
# whatever the container actually binds, not to the Dockerfile's EXPOSE
# value. Defaults to 8000 for plain `docker run` / other hosts that don't
# set PORT.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
