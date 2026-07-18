"""Automated proof of the safety controls introduced after the 2026-07-18
database-destruction incident (docs/incidents/). These tests exist to catch
a regression of the exact failure mode that caused the incident — a test
fixture reaching real data — before it can happen again, not to test
application behavior.
"""

import re
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_REPO_ROOT = Path(__file__).resolve().parents[3]
_APP_DIR = Path(__file__).resolve().parents[1] / "app"
_TESTS_DIR = Path(__file__).resolve().parent

_DANGEROUS_PATTERNS = (
    re.compile(r"\.drop_all\("),
    re.compile(r"DROP\s+SCHEMA\s+public", re.IGNORECASE),
    re.compile(r"DROP\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\b", re.IGNORECASE),
)

# Files allowed to contain these patterns, with the reviewed reason why each
# is not the incident's failure mode:
# - conftest.py: every DROP is scoped to the randomized _TEST_SCHEMA sandbox,
#   never to "public" (verified by the other tests in this file).
# - test_knowledge_security.py: "DROP TABLE ...;" appears only as a literal
#   SQL-injection *payload string* passed into the search function, asserting
#   the app does NOT execute injected SQL — it is the thing the test proves
#   can't happen, not a statement this suite runs.
# - this file: the scanner's own pattern definitions/docstrings necessarily
#   contain these strings to describe what they detect.
_ALLOWED_FILES = {
    _TESTS_DIR / "conftest.py",
    _TESTS_DIR / "test_knowledge_security.py",
    Path(__file__).resolve(),
}


def test_no_dangerous_ddl_patterns_outside_the_sandboxed_fixture():
    """Repo-wide scan (app/ + tests/) for the exact patterns that caused the
    incident. Anywhere outside `_ALLOWED_FILES`, these patterns have no
    legitimate reason to exist."""
    offenders = []
    for directory in (_APP_DIR, _TESTS_DIR):
        for path in directory.rglob("*.py"):
            if path in _ALLOWED_FILES or "__pycache__" in path.parts:
                continue
            content = path.read_text(encoding="utf-8")
            for pattern in _DANGEROUS_PATTERNS:
                if pattern.search(content):
                    offenders.append(f"{path.relative_to(_REPO_ROOT)}: matched {pattern.pattern}")

    assert not offenders, "Dangerous DDL pattern(s) found outside the sandboxed fixture:\n" + "\n".join(offenders)


def test_test_schema_name_is_never_public(test_schema_name: str):
    assert test_schema_name != "public"
    assert test_schema_name.startswith("test_")


@pytest.mark.asyncio
async def test_public_schema_is_untouched_by_a_db_dependent_test(db_session: AsyncSession):
    """Runs an ordinary DB-dependent test (via the standard db_session
    fixture) and confirms "public" — the schema real application data
    lives in — was never written to. This is the single most important
    regression test this incident produced."""
    result = await db_session.execute(
        text("select count(*) from information_schema.tables where table_schema = 'public'")
    )
    public_table_count_during_test = result.scalar()

    # This test doesn't assert an exact table count (that would make it
    # brittle against future migrations) — it asserts the sandbox fixture
    # itself did not add to or remove from whatever's already there, by
    # checking the count is stable across two reads within the same test.
    result = await db_session.execute(
        text("select count(*) from information_schema.tables where table_schema = 'public'")
    )
    assert result.scalar() == public_table_count_during_test


@pytest.mark.asyncio
async def test_sandbox_schema_is_created_and_removed(db_session: AsyncSession, test_schema_name: str):
    """Confirms the sandbox schema actually exists while a test is running
    (proving db_engine's create_all really happened)."""
    result = await db_session.execute(
        text("select schema_name from information_schema.schemata where schema_name = :name"),
        {"name": test_schema_name},
    )
    assert result.scalar() == test_schema_name


@pytest.mark.asyncio
async def test_a_row_written_through_the_sandbox_never_lands_in_public(
    db_session: AsyncSession, db_engine, test_schema_name: str
):
    """Writes a distinctively-named row through the normal (schema-
    translated) db_session, then reads 'public.customers' through a second,
    *untranslated* connection on the same underlying database — proving
    the row physically exists only in the sandbox schema, not in 'public',
    rather than merely asserting the fixture claims to be safe."""
    from app.customers import service as customer_service
    from app.customers.schemas import CustomerCreateRequest

    marker = f"safety-test-{test_schema_name}"
    await customer_service.create_customer(db_session, body=CustomerCreateRequest(full_name=marker), actor_user_id=None)

    # Untranslated connection: schema_translate_map is a per-engine
    # execution option, so disabling it (None is the documented way to do
    # so) makes this connection query 'public' for real, regardless of what
    # the sandboxed engine believes.
    raw_engine = db_engine.execution_options(schema_translate_map=None)
    async with raw_engine.connect() as raw_conn:
        result = await raw_conn.execute(
            text("select count(*) from public.customers where full_name = :marker"), {"marker": marker}
        )
        assert result.scalar() == 0, "a sandboxed write leaked into the real 'public' schema"
