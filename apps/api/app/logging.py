import contextvars
import json
import logging
import sys
import time
from typing import Any

correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
tenant_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("tenant_id", default=None)
user_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("user_id", default=None)

# Fields that must never reach the logs, even if accidentally passed in `extra`.
_FORBIDDEN_LOG_FIELDS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "secret",
    "authorization",
    "jwt",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.Logger) -> str:  # type: ignore[override]
        payload: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_var.get(),
            "tenant_id": tenant_id_var.get(),
            "user_id": user_id_var.get(),
        }
        for key, value in record.__dict__.items():
            if key in _FORBIDDEN_LOG_FIELDS:
                continue
            if key.startswith("_") or key in payload or hasattr(logging.LogRecord("", 0, "", 0, "", None, None), key):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet noisy third-party loggers unless something goes wrong.
    for noisy in ("uvicorn.access", "httpx"):
        logging.getLogger(noisy).setLevel("WARNING")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
