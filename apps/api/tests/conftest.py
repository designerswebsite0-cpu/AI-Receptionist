import os
import uuid
import warnings

# Settings requires these to construct at all; dummy values let pure-logic
# and HTTP-layer tests import the app without a real Supabase project. Tests
# that need an actual reachable Postgres opt in via `db_engine` below, which
# skips cleanly when no database is reachable (expected locally without
# Docker/DB installed) — see docs/roadmap.md Phase 1 tech-debt notes.
os.environ.setdefault("SUPABASE_URL", "https://test-project.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")

# TEST_DATABASE_URL is preferred (a real separate database/project reserved
# for tests); DATABASE_URL is a documented, loud fallback only — see the
# 2026-07-18 database-destruction incident (docs/incidents/) for why this is
# not a silent fallback. The schema-sandbox below (_TEST_SCHEMA) is the
# actual safety boundary regardless of which connection string is used: it
# guarantees create_all/drop_all can never reach "public" even when
# DATABASE_URL points at a shared/real database, but a dedicated
# TEST_DATABASE_URL is still the safer long-term setup (see
# docs/incidents/DATABASE_SAFETY_CONTROLS.md).
if "TEST_DATABASE_URL" in os.environ:
    os.environ.setdefault("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
else:
    warnings.warn(
        "TEST_DATABASE_URL is not set — DB-dependent tests will fall back to "
        "DATABASE_URL (the same database the running application uses). "
        "This is safe from actual data loss (tests only ever touch a "
        "dedicated, disposable schema, never 'public'), but a separate "
        "TEST_DATABASE_URL is still recommended. See "
        "docs/incidents/DATABASE_SAFETY_CONTROLS.md.",
        stacklevel=1,
    )
    os.environ.setdefault(
        "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_receptionist_test"
    )

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Registers every table on Base.metadata (mirrors alembic/env.py's import
# list) so db_engine's create_all/drop_all is self-sufficient regardless of
# which subset of test files pytest happens to collect — without this, a
# test file run in isolation can fail with NoReferencedTableError (e.g.
# audit_logs.actor_user_id -> users.id) purely because nothing else in that
# run's import graph happened to pull in app.users.models first.
from app.audit.models import AuditLog  # noqa: F401
from app.bookings.models import RoomBooking, RoomType  # noqa: F401
from app.conversations.models import Conversation, ConversationStateEvent  # noqa: F401
from app.customers.models import Customer, CustomerContact, CustomerNote, CustomerTag  # noqa: F401
from app.database import Base
from app.knowledge.models import (  # noqa: F401
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
from app.messages.models import Message, MessageAttachment  # noqa: F401
from app.orchestration.models import OrchestrationTurn, ServiceRequest  # noqa: F401
from app.payments.models import Payment  # noqa: F401
from app.resort.models import ResortSettings  # noqa: F401
from app.users.models import User  # noqa: F401
from app.voice.models import VoiceCall  # noqa: F401
from app.webchat.models import WebchatSession  # noqa: F401

# CRITICAL SAFETY BOUNDARY — read before touching this fixture.
#
# DATABASE_URL may point at the same real Supabase project used for actual
# development data (there is often no separate test project). This fixture
# used to run Base.metadata.create_all/drop_all directly against that
# connection's default ("public") schema — which, combined with an
# orphaned background test process left running during a debugging
# session, resulted in a real DROP TABLE of every application table
# (customers, conversations, the entire Phase 3 knowledge base, etc.) with
# no backup to recover from. Never again: every test table now lives in a
# dedicated, disposable, randomly-named schema (regenerated fresh each time
# this module is imported, i.e. once per pytest invocation — not a fixed
# name, so two test runs against the same database can never collide with
# each other either), and every destructive statement is scoped so it can
# *physically not reach* "public" no matter what else is running
# concurrently against the same database.
_TEST_SCHEMA = f"test_{uuid.uuid4().hex}"
assert _TEST_SCHEMA != "public"  # defensive — must never be able to degrade to the real schema


@pytest_asyncio.fixture
async def db_engine():
    """Yields a connected async engine, scoped to a dedicated, randomly
    named `_TEST_SCHEMA` sandbox — or skips the test if no database is
    reachable (expected locally without Docker; CI provides a postgres
    service container — see .github/workflows/ci.yml).
    """
    # Same fix as app/database.py: Supabase's transaction-mode pooler (port
    # 6543) doesn't support asyncpg's server-side prepared statement cache —
    # without this, running many tests in one session intermittently fails
    # with "prepared statement already exists" once the pooler reassigns
    # the underlying connection. Harmless no-op against a direct connection.
    engine = create_async_engine(
        os.environ["DATABASE_URL"], connect_args={"statement_cache_size": 0}
    ).execution_options(schema_translate_map={None: _TEST_SCHEMA})
    try:
        async with engine.begin() as conn:
            # Base.metadata includes knowledge_chunks.embedding (pgvector) —
            # the extension must exist before create_all runs. CI's postgres
            # service image is pgvector/pgvector:pg16 for exactly this
            # reason (see .github/workflows/ci.yml). Extensions are
            # database-wide (not schema-scoped), so this is a harmless,
            # idempotent no-op against a database that already has it.
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            # Drop-then-create rather than CREATE SCHEMA IF NOT EXISTS alone:
            # a prior interrupted run (killed process, crashed test) can
            # leave the sandbox in a half-built state; starting every run
            # from a guaranteed-empty schema is safer than layering onto
            # whatever happens to still be there.
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{_TEST_SCHEMA}" CASCADE'))
            await conn.execute(text(f'CREATE SCHEMA "{_TEST_SCHEMA}"'))
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"No reachable test database: {exc}")
    yield engine
    async with engine.begin() as conn:
        # DROP SCHEMA ... CASCADE removes every table in one statement
        # regardless of FK ordering (no need for metadata.drop_all's
        # topological sort, which the knowledge_sources <-> knowledge_source_
        # versions circular FK can't always satisfy).
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{_TEST_SCHEMA}" CASCADE'))
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncSession:
    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
def test_schema_name() -> str:
    """Exposes `_TEST_SCHEMA` to test modules as a fixture rather than a
    plain import — a plain `from tests.conftest import _TEST_SCHEMA` in a
    test file can resolve to a *second*, separately-imported copy of this
    module when `tests/` has no `__init__.py` (an implicit namespace
    package), silently re-running this file's module-level code and
    generating a different UUID than the one `db_engine` actually created.
    Fixture injection always resolves to pytest's own single loaded
    instance of this module, avoiding that trap."""
    return _TEST_SCHEMA
