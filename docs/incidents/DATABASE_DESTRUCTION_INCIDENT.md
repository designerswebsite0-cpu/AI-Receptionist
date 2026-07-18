# Database Destruction Incident

## Summary

During a debugging session for Phase 4 (AI Orchestration) test coverage, the
entire application schema in the `public` schema of the project's Supabase
Postgres database was destroyed by a `DROP TABLE`/`DROP SCHEMA`-equivalent
operation (`sqlalchemy.MetaData.drop_all()`), executed by the pytest test
suite's database fixture against the same database used for real development
data. There is no backup. All row data that existed in `public` at the time
is permanently lost. The database schema itself (structure, not data) is
fully recoverable from the Alembic migration chain, which is intact in the
repository.

## Timeline (2026-07-18, IST)

- **~13:09** — A full backend `pytest` run was started in the background to
  validate new Phase 4 orchestration code (`test_orchestration_pipeline.py`)
  and a `conftest.py` fix applied minutes earlier. It was piped through
  `tail -60`, discarding all but the last 60 lines of output.
- **~13:20–13:53** — The run appeared to stall (no output growth). A
  `taskkill //F //T //PID 1363` was issued to stop it, based on the PID shown
  by Git Bash's `ps aux`. Git Bash (MSYS) reports its own translated PID in
  that column, not the real Windows PID — the kill command reported "process
  not found" and silently failed. **The process kept running, undetected.**
- **13:09–~13:54** — Multiple additional `pytest` invocations were run in
  this window (targeted test files, then the full suite again) while the
  orphaned process from 13:09 was still alive, unbeknownst to the operator.
  Each invocation's `db_engine` fixture called
  `Base.metadata.create_all()`/`drop_all()` directly against the `public`
  schema of the shared `DATABASE_URL`. With multiple such fixtures running
  concurrently across processes, one process's teardown (`drop_all()`) very
  likely executed while another process's tests were still relying on those
  same tables — consistent with the `UndefinedTableError` ("relation ...
  does not exist") errors observed partway through this window.
- **~13:53** — A direct read-only query confirmed every application table in
  `public` was gone except `alembic_version`.
- **~13:54** — The orphaned process was correctly identified via its real
  Windows PID (`ps aux`'s `WINPID` column, not the leading MSYS `PID`
  column) and terminated with `taskkill //F //PID 26652`.
- **13:54 onward** — No further destructive commands were run. A schema
  isolation fix was applied to `tests/conftest.py` (see Root Cause below)
  before any further database interaction.

## Database / Project Affected

The Supabase Postgres project referenced by this repo's `DATABASE_URL` (the
project's own transaction-pooler connection string in `.env`, not restated
here). This is the project's single (dev) environment — there is no separate
staging/test project.

## Command / Code Path Responsible

`apps/api/tests/conftest.py`, `db_engine` pytest fixture (function-scoped):

```python
engine = create_async_engine(os.environ["DATABASE_URL"])
...
await conn.run_sync(Base.metadata.create_all)   # setup, every test
...
await conn.run_sync(Base.metadata.drop_all)     # teardown, every test
```

This fixture is used, directly or via `db_session`, by every DB-dependent
test file in `apps/api/tests/`. It is fixture **teardown** (`drop_all()`)
that performed the destructive operation — not a manual command, not a
migration, not application code.

## Exact Environment Variable That Pointed Tests at Live Data

`DATABASE_URL`. There was no separate `TEST_DATABASE_URL`; `conftest.py` read
the same variable the running FastAPI application uses for real data, with
only a `postgresql+asyncpg://postgres:postgres@localhost:5432/...` fallback
default for when it's entirely unset (not applicable here — `DATABASE_URL`
*was* set, to the real Supabase project).

## Tables Observed Missing (public schema)

Every application table: `users`, `audit_logs`, `resort_settings`,
`customers`, `customer_contacts`, `customer_notes`, `customer_tags`,
`conversations`, `conversation_state_events`, `messages`,
`message_attachments`, `knowledge_sources`, `knowledge_source_versions`,
`knowledge_chunks`, `knowledge_media`, `knowledge_ingestion_jobs`,
`knowledge_retrieval_logs`, `knowledge_search_feedback`,
`knowledge_conflicts`, `knowledge_benchmark_questions`,
`website_crawl_runs`, `orchestration_turns`, `service_requests`.

Only `public.alembic_version` survived (it is not part of `Base.metadata`,
so `drop_all()` never touched it — which is why it still (incorrectly)
claims revision `0023` even though none of that revision's tables exist).

## Objects That Survived

- All Supabase-managed schemas: `auth`, `storage`, `realtime`, `vault`,
  `graphql`, `graphql_public`, `extensions`, plus standard Postgres system
  schemas.
- All Postgres extensions: `vector` (pgvector 0.8.2), `pg_trgm`, `pgcrypto`,
  `unaccent`, `uuid-ossp`, `supabase_vault`, `pg_stat_statements`,
  `plpgsql`.
- **`auth.users`: 1 row, intact** (id, email, created_at, last_sign_in_at
  all present and unchanged).
- **`storage.buckets`: 1 bucket (`documents`) intact.** `storage.objects`
  count is 0 — this bucket had no uploaded files at the time of the
  incident, so nothing was lost there.
- `public.alembic_version`: 1 row, value `0023` (stale/inconsistent with
  actual schema state — see Root Cause).
- No custom Postgres functions, triggers, sequences, or enum types existed
  in `public` before the incident (the schema uses `VARCHAR` + `CHECK
  CONSTRAINT` instead of native enums, and UUID primary keys instead of
  sequences) — so none were lost either. All functions still present in
  `public` belong to the `vector`/`pg_trgm`/`unaccent` extensions, not the
  application.
- All RLS policies were attached to the now-dropped tables and were
  therefore dropped along with them — `pg_policies` for `public` now
  returns zero rows. These are fully re-created by the Alembic migrations
  that originally defined them (0002, 0006, 0009, 0019, 0023).

## Root Cause

Two compounding failures:

1. **No test/prod database isolation.** `tests/conftest.py`'s `db_engine`
   fixture ran schema-destructive operations (`create_all`/`drop_all`)
   directly against `DATABASE_URL` — the same database used for real
   development data — with no separate test database, schema, or
   safety guard of any kind.
2. **An orphaned background process was not actually killed**, due to a
   PID-translation mismatch: Git Bash (MSYS) `ps aux` reports its own
   internal process ID in the leading `PID` column, which is *not* the
   real Windows process ID that `taskkill` expects. A `taskkill` issued
   against the MSYS PID silently reported "process not found" while the
   real process kept running for roughly 45 minutes, invisible to further
   `ps aux` checks that were (incorrectly) trusted. This orphaned
   process's own `db_engine` fixture instances continued running
   `create_all`/`drop_all` cycles concurrently with every subsequent test
   invocation in the same window, racing table creation and deletion
   against the shared live schema.

Neither failure alone would necessarily have been catastrophic (a single
`drop_all()` against an idle database, if promptly followed by nothing
else, simply leaves an empty-but-recoverable schema) — the combination of
*no isolation* and *an untracked concurrent process* is what turned a
recoverable mistake into permanent data loss, because there was no
window in which the destructive operation happened once, cleanly, on
data nobody needed anymore.

## Containment Actions Taken

- Identified and killed the orphaned process using its real Windows PID
  (`WINPID` column of `ps aux`, not the leading MSYS `PID`).
- Confirmed via `ps aux` that no python/uv/node/pytest processes remain
  running.
- Confirmed no FastAPI dev server, dashboard dev server, or background
  worker was ever started via the Browser-pane preview tools during this
  session (so no additional concurrent writer exists there either).
- Applied an immediate fix to `tests/conftest.py`: the `db_engine` fixture
  now creates and drops a dedicated `pytest_sandbox` **schema** (via
  SQLAlchemy `schema_translate_map`), never touching `public` — verified
  empirically (ran a test file, confirmed `public` still contained only
  `alembic_version` afterward, and `pytest_sandbox` was fully cleaned up).
  This is a first-pass mitigation; the full permanent safety-control set
  (separate `TEST_DATABASE_URL`, fail-closed guards, CI static scanning)
  is tracked separately per the incident response plan and is not yet
  complete.
- Halted all further destructive or Phase 4 work pending this
  documentation and an explicitly reviewed recovery plan.

## Recovery Plan

See `docs/incidents/DATABASE_RECOVERY_REPORT.md` (produced once the
isolated-recovery verification step has been completed) for the detailed,
executed recovery plan. In summary: the Alembic migration chain (0001
through 0023, confirmed linear with no gaps or branches) is the
authoritative schema-reconstruction source and will be replayed from a
clean state to rebuild `public` — proven first in an isolated sandbox
before any write against the live project.

## Data Recovery Assessment

See `docs/incidents/DATA_RECOVERY_ASSESSMENT.md` for the full breakdown of
what is regeneratable vs. permanently lost. In short: the RKPR knowledge
corpus is regeneratable (source files still exist locally and were never
successfully imported with real embeddings before this incident — the real
import was blocked on `OPENAI_API_KEY`, which only just became available).
Any customer/conversation/message/audit rows that may have existed from
earlier manual testing are **permanently lost** — there is no local export,
CI artifact, or Supabase backup to recover them from.

## Permanent Prevention Measures

Tracked in `docs/incidents/DATABASE_SAFETY_CONTROLS.md`. The schema-sandbox
fix above is a necessary first step but is not the complete fix — separate
test/prod database variables, fail-closed environment guards, and a CI-level
static scan for dangerous DDL patterns are still required before this
incident is considered fully remediated.
