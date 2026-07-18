# Database Safety Controls

Permanent measures put in place after the 2026-07-18 database-destruction
incident (`DATABASE_DESTRUCTION_INCIDENT.md`), so the same failure mode
(a test fixture destroying real application data) cannot happen again.

## Implemented and Verified

### 1. Randomized, schema-scoped test sandbox (`tests/conftest.py`)

The `db_engine` fixture no longer runs `Base.metadata.create_all`/`drop_all`
against the connection's default schema. Instead:

- A schema name (`test_<random uuid4 hex>`) is generated fresh **once per
  pytest process** when `conftest.py` is first imported — never a fixed
  name, so two test runs against the same database can never collide with
  each other either.
- The engine is built with
  `execution_options(schema_translate_map={None: _TEST_SCHEMA})` — every
  unqualified table reference SQLAlchemy compiles (i.e. everything the ORM
  and `Base.metadata` touch) is transparently redirected into that schema.
  Raw `text()` SQL is unaffected by this mapping by design — which is
  exactly why the fixture's own DDL (`CREATE/DROP SCHEMA "..."`) uses the
  literal schema name explicitly, rather than relying on translation.
- Setup: `DROP SCHEMA IF EXISTS <sandbox> CASCADE` (clears any half-built
  state from a prior crashed run) → `CREATE SCHEMA <sandbox>` →
  `Base.metadata.create_all` (schema-translated).
- Teardown: `DROP SCHEMA IF EXISTS <sandbox> CASCADE` — a single statement
  that removes every table regardless of FK ordering (no dependence on
  `Base.metadata.drop_all()`'s topological sort, which the
  `knowledge_sources` ↔ `knowledge_source_versions` circular FK cannot
  always satisfy).
- A defensive assertion (`assert _TEST_SCHEMA != "public"`) runs at import
  time as a second, independent guard.

**This is the actual safety boundary** — it holds regardless of which
physical database `DATABASE_URL` points at, including a shared production
database, because the sandbox schema is a completely separate namespace
that `create_all`/`drop_all` cannot escape.

### 2. Documented, loud (non-silent) `DATABASE_URL` fallback

`conftest.py` now prefers `TEST_DATABASE_URL` if set. If it is not set, a
`UserWarning` is raised at test-collection time explaining the fallback to
`DATABASE_URL` and pointing at this document — this satisfies the intent of
"tests must never silently fall back to production" even though, in this
repository's actual environment (no Docker, no local Postgres, only one
Supabase project available), a literal separate `TEST_DATABASE_URL` is not
yet configured. See "Not Yet Implemented" below for the honest gap this
leaves.

### 3. Automated safety tests (`tests/test_database_safety.py`)

Five tests, all passing, that empirically prove the properties above hold
— not just assert the code "looks safe":

- `test_no_dangerous_ddl_patterns_outside_the_sandboxed_fixture` — scans
  every `.py` file under `app/` and `tests/` for `.drop_all(`,
  `DROP SCHEMA public`, `DROP TABLE`, and `TRUNCATE`. Only `conftest.py`
  (whose matches are schema-scoped, not `public`-scoped) and
  `test_knowledge_security.py` (whose one `DROP TABLE` match is a literal
  SQL-injection *test payload string*, not an executed statement) are
  allow-listed, each with a documented reason. **This test runs as part of
  the existing CI `pytest -v` step already — no separate CI workflow change
  was needed.**
- `test_test_schema_name_is_never_public` — the sandbox name can never
  degrade to `"public"`.
- `test_public_schema_is_untouched_by_a_db_dependent_test` — runs a real
  DB-dependent test and confirms `public`'s table count is stable across
  two reads within it.
- `test_sandbox_schema_is_created_and_removed` — confirms the sandbox
  schema genuinely exists (in `information_schema.schemata`) while a test
  is running, via a dedicated `test_schema_name` fixture (see the
  "duplicate-import" pitfall documented in that fixture's docstring — a
  raw `from tests.conftest import _TEST_SCHEMA` in a *different* test
  module can silently resolve to a second, separately-imported copy of the
  module when `tests/` has no `__init__.py`, generating a different UUID
  than the one the fixture machinery actually used; this was caught while
  writing this exact test and is the reason the fixture exists instead of
  a plain constant import).
- `test_a_row_written_through_the_sandbox_never_lands_in_public` — writes
  a distinctively-named `Customer` row through the normal sandboxed
  session, then reads `public.customers` through a second connection with
  `schema_translate_map` explicitly disabled, and asserts the row is
  **not** there. This is the strongest test in the suite: it doesn't trust
  the mechanism's own claims, it independently observes the real schema.

### 4. Root-cause fixes to the migration/model layer

- `apps/api/app/conversations/models.py`: added the `flow_state` column
  mapping that migration 0020 created in the database but which was never
  reflected on the ORM model — a real, independent bug that (had it gone
  unnoticed) would have caused `Base.metadata` to disagree with the actual
  schema in exactly the kind of way that makes `create_all`/`drop_all`
  unpredictable.
- `apps/api/app/knowledge/models.py`: the `knowledge_sources.current_version_id`
  ↔ `knowledge_source_versions` circular foreign key now uses
  `use_alter=True` with an explicit constraint name matching Postgres' own
  default naming (so it is a metadata-only annotation, not a migration
  change) — this is what makes `Base.metadata.create_all`/`drop_all`
  tooling able to handle the cycle at all; without it, `drop_all()` in any
  test harness raises `CircularDependencyError` regardless of the schema
  it's scoped to.
- `apps/api/tests/conftest.py`: now explicitly imports every model module
  (mirroring `alembic/env.py`'s own import list) so `Base.metadata` is
  always fully populated regardless of which subset of test files pytest
  happens to collect — previously, a test file run in isolation could hit
  `NoReferencedTableError` purely because nothing else in that run's
  import graph had touched, say, `app.users.models` yet.
- `apps/api/tests/conftest.py`: the Supabase transaction-pooler
  `statement_cache_size: 0` fix (already present in `app/database.py`) is
  now also applied to the test engine — this was previously missing and
  caused intermittent `DuplicatePreparedStatementError` failures under
  sustained test runs.

## Not Yet Implemented (honest gaps, with reasoning)

These were part of the requested permanent-fix scope but are **deliberately
deferred**, not silently skipped — each is explained here so a future
session (or you) can pick them up with full context.

- **A literal separate `TEST_DATABASE_URL` project.** This repo's only
  reachable Postgres is the one live Supabase project (no Docker, no local
  Postgres installed on this machine — verified during this incident's
  response). The schema-sandbox fix above is real, tested protection
  regardless of this gap: even pointed at the live project, `create_all`/
  `drop_all` structurally cannot reach `public`. A dedicated test project
  (the same kind created for isolated migration-recovery testing during
  this incident) would still be a meaningful additional layer — mainly
  against a scenario this incident already ruled out as the actual
  mechanism (an orphaned process racing `drop_all` calls against `public`
  directly), but worth doing if/when convenient.
- **Restricted database role for tests.** Would require creating a
  Postgres role scoped to only the sandbox schema, which in turn requires
  either a separate test database (so the role can be scoped without
  affecting the real app's connection user) or Supabase-side role
  management this session did not attempt. Deferred alongside the item
  above.
- **A CI static-scan step written as raw YAML/grep.** Not implemented as a
  separate step because `test_no_dangerous_ddl_patterns_outside_the_sandboxed_fixture`
  already performs this exact scan and already runs inside CI's existing
  `pytest -v` step — adding a second, redundant implementation in YAML
  would be duplication for no additional coverage, not a stronger
  guarantee.

## What To Do If You Add a Second Supabase Project Later

1. Set `TEST_DATABASE_URL` (async, `postgresql+asyncpg://...`) in `.env` to
   that project's transaction-pooler string.
2. `tests/conftest.py` already prefers it automatically — no code change
   needed.
3. The `UserWarning` about the loud fallback will stop appearing once it's
   set.
