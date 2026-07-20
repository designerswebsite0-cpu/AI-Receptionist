from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.audit.router import router as audit_router
from app.auth.router import router as auth_router
from app.config import get_settings
from app.conversations.router import router as conversations_router
from app.customers.router import router as customers_router
from app.errors import register_exception_handlers
from app.feedback.router import router as feedback_router
from app.health.router import router as health_router
from app.knowledge.router import router as knowledge_router
from app.knowledge.storage import ensure_bucket_exists
from app.logging import configure_logging, get_logger
from app.middleware import RequestContextMiddleware
from app.notifications.router import router as notifications_router
from app.orchestration.router import router as orchestration_router
from app.resort.router import router as resort_router
from app.service_requests.router import router as service_requests_router
from app.users.router import router as users_router
from app.webchat.router import router as webchat_router

settings = get_settings()
configure_logging("DEBUG" if settings.app_env == "development" else "INFO")
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await ensure_bucket_exists()
    except Exception:
        # Non-fatal: see ensure_bucket_exists' own logging. Startup must not
        # crash over a Storage hiccup — upload calls will surface a real
        # StorageError if the bucket genuinely doesn't exist.
        logger.exception("knowledge_bucket_ensure_raised")
    yield


app = FastAPI(
    title="AI Receptionist API",
    version="0.1.0",
    description=(
        "Single-resort AI Receptionist backend (WhatsApp, Website Chat, future Voice) — "
        "reusable as a deployment template; each deployment serves exactly one resort."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)

register_exception_handlers(app)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(audit_router)
app.include_router(resort_router)
app.include_router(customers_router)
app.include_router(conversations_router)
app.include_router(knowledge_router)
app.include_router(orchestration_router)
app.include_router(users_router)
app.include_router(service_requests_router)
app.include_router(notifications_router)
app.include_router(feedback_router)
app.include_router(webchat_router)
