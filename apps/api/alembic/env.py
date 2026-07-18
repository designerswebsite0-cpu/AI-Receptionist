import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Import models so they register on Base.metadata for autogenerate support.
from app.audit.models import AuditLog  # noqa: E402,F401
from app.config import get_settings  # noqa: E402
from app.conversations.models import Conversation, ConversationStateEvent  # noqa: E402,F401
from app.customers.models import Customer, CustomerContact, CustomerNote, CustomerTag  # noqa: E402,F401
from app.database import Base  # noqa: E402
from app.knowledge.models import (  # noqa: E402,F401
    KnowledgeBenchmarkQuestion,
    KnowledgeChunk,
    KnowledgeConflict,
    KnowledgeIngestionJob,
    KnowledgeMedia,
    KnowledgeRetrievalLog,
    KnowledgeSearchFeedback,
    KnowledgeSource,
    KnowledgeSourceVersion,
    WebsiteCrawlRun,
)
from app.messages.models import Message, MessageAttachment  # noqa: E402,F401
from app.orchestration.models import OrchestrationTurn, ServiceRequest  # noqa: E402,F401
from app.resort.models import ResortSettings  # noqa: E402,F401
from app.users.models import User  # noqa: E402,F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_database_url() -> str:
    """Alembic runs synchronously; reuse the same Settings loader the app
    uses (repo-root .env) rather than reading raw os.environ, so migrations
    and the app never disagree about where the database is. Prefers the
    explicit direct-connection DATABASE_URL_SYNC over deriving one from
    DATABASE_URL, since the latter may point at a transaction-mode pooler."""
    settings = get_settings()
    if settings.database_url_sync:
        return settings.database_url_sync
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _sync_database_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
