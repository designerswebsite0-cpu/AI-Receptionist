from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.config import get_settings
from app.conversations.router import router as conversations_router
from app.customers.router import router as customers_router
from app.errors import register_exception_handlers
from app.health.router import router as health_router
from app.logging import configure_logging
from app.middleware import RequestContextMiddleware
from app.tenants.router import router as tenants_router

settings = get_settings()
configure_logging("DEBUG" if settings.app_env == "development" else "INFO")

app = FastAPI(
    title="AI Receptionist API",
    version="0.1.0",
    description="Unified multi-tenant backend for WhatsApp, Website Chat, and (future) Voice.",
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
app.include_router(tenants_router)
app.include_router(customers_router)
app.include_router(conversations_router)
