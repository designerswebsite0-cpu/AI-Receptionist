import os

# Settings requires these to construct at all; dummy values let pure-logic
# and HTTP-layer tests import the app without a real Supabase project. Tests
# that need an actual reachable Postgres opt in via `db_engine` below, which
# skips cleanly when DATABASE_URL points at nothing real (e.g. no Docker/DB
# installed locally) — see docs/roadmap.md Phase 1 tech-debt notes.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_receptionist_test"
)
os.environ.setdefault("SUPABASE_URL", "https://test-project.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base


@pytest_asyncio.fixture
async def db_engine():
    """Yields a connected async engine against DATABASE_URL, or skips the
    test if no real database is reachable (expected locally without Docker;
    CI provides a postgres service container — see .github/workflows/ci.yml).
    """
    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"No reachable test database: {exc}")
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncSession:
    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
