import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging import correlation_id_var, get_logger, user_id_var

logger = get_logger("app.request")

CORRELATION_ID_HEADER = "X-Correlation-Id"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attaches a correlation ID to every request and logs outcome + latency.

    user_id is populated later by the auth dependency once the request is
    authenticated; this middleware only guarantees the correlation ID and
    the final structured access log line.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())
        correlation_token = correlation_id_var.set(correlation_id)
        user_token = user_id_var.set(None)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed",
                extra={"method": request.method, "path": request.url.path},
            )
            raise
        else:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "request_completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                },
            )
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            return response
        finally:
            correlation_id_var.reset(correlation_token)
            user_id_var.reset(user_token)
