# Database Recovery Report

## Live Database Identity (redacted)

- **Host**: Supabase pooler, `ap-southeast-1` region (same project as before the
  incident — connection string not restated here)
- **Database name**: `postgres`
- **Current `public` table count**: 1 (`alembic_version` only)
- **Current `alembic_version` value**: `0023` — **stale**: this claims the
  schema is fully at head, but zero of that revision's actual tables exist.
  This mismatch is the reason `alembic upgrade head` cannot simply be run
  as-is (Alembic would see current=head and do nothing).
- **Supabase-managed schemas**: `auth`, `storage`, `realtime`, `vault`,
  `graphql`/`graphql_public`, all extension schemas — all intact, verified
  via read-only queries (see `DATABASE_DESTRUCTION_INCIDENT.md`).
- **auth.users**: 1 row intact.
- **storage.buckets**: 1 bucket (`documents`), 0 objects — already empty
  before the incident, nothing lost.

## Isolated Recovery Proof (completed)

Per your decision, a brand-new, separate Supabase project was created
specifically for this test (not the live project — different host, different
region: `ap-northeast-1`). Against that project, with no other process
running concurrently:

1. Ran `alembic upgrade head` from a verified-empty `public` schema — all 23
   migrations (0001→0023) applied cleanly, in order, no errors.
2. Captured a full schema fingerprint: every table, column (name/type/
   nullability/default), constraint (name + type), index, and RLS policy in
   `public`, plus the resulting `alembic_version`.
3. Reset that project's `public` schema to empty again
   (`DROP SCHEMA public CASCADE; CREATE SCHEMA public;` — safe, since this is
   the dedicated recovery project, not live).
4. Ran `alembic upgrade head` again from that clean state — again, all 23
   migrations applied cleanly, no errors.
5. Captured the fingerprint again and diffed it against the first.

**Result: identical**, except for Postgres' own auto-generated `NOT NULL`
constraint names (e.g. `2200_17601_1_not_null` vs. `18807_18814_1_not_null`)
— these embed internal object OIDs that are expected to differ between two
independently-created schemas and are never referenced by name anywhere in
the application or migrations. Every table name, column, type, default,
index, RLS policy, and explicitly-named constraint matched byte-for-byte.

**This proves the migration chain is complete and deterministically
reproducible** — replaying it against the live project's already-empty
`public` schema will produce the exact same, correct result.

## Why Strategy A (repair in place) — not B or C

- **Strategy A applies cleanly**: `public` currently contains *zero*
  conflicting or partial application objects (only the stale
  `alembic_version` bookkeeping row) — there is nothing for a fresh
  migration replay to collide with.
- **Strategy B (custom recovery migration) is unnecessary**: there's no
  partial/inconsistent state to reconcile around; a plain replay from empty
  is both simpler and already proven.
- **Strategy C (new live project) is actively worse here**: the current live
  project's `auth.users` (1 real account) and `storage.buckets`
  (`documents`, empty) survived the incident intact. Moving to a new project
  would require the user to re-authenticate with a new project's Auth
  system and would abandon the surviving bucket for no benefit — there is
  nothing broken about the project itself, only about its `public` schema's
  contents.

## Proposed Live Sequence (not yet executed — awaiting your explicit go-ahead)

Two statements, in order, against the **live** project only:

```sql
-- 1. Reset stale bookkeeping. alembic_version currently says "0023" but none
--    of that revision's tables exist. This does not touch any table, view,
--    function, or Supabase-managed schema — alembic_version is pure
--    migration-tracking metadata, not application data.
DELETE FROM public.alembic_version;
```

```bash
# 2. Replay the exact, proven migration chain from a clean slate.
#    This recreates every table, index, constraint, and RLS policy defined
#    in migrations 0001-0023 — nothing more, nothing less. It does not
#    touch auth.*, storage.*, or any Supabase-managed schema (Alembic's
#    target_metadata only includes app.*.models tables).
alembic upgrade head
```

After this, I will:

3. Re-run the same forensic read-only queries from the incident report
   against the live project and confirm the resulting table list, column
   set, and RLS policy count match `EXPECTED_DATABASE_SCHEMA.md` /
   the isolated-recovery fingerprint.
4. Confirm `auth.users` (1 row) and `storage.buckets` (`documents`) are
   still untouched.
5. **Not** attempt to restore any customer/conversation/message/audit data
   — per `DATA_RECOVERY_ASSESSMENT.md`, that data is permanently lost and
   migrations only recover schema, never row content.
6. Report back before any further action (Phase 1-3 smoke verification,
   real embeddings, Redis, or Phase 4 resumption).

I will not run either of the two steps above until you explicitly confirm.

## Execution Result (completed, user-approved)

Both steps were executed against the live project after explicit user
approval:

1. `DELETE FROM public.alembic_version` — before: `[('0023',)]`, after: `[]`.
2. `alembic upgrade head` — all 23 migrations (0001→0023) applied cleanly,
   in order, no errors (identical log output to both isolated-recovery
   passes).

Post-recovery verification against the live project:

- **`public` table count: 24** — `alembic_version` plus the exact 23
  application tables listed in `EXPECTED_DATABASE_SCHEMA.md` (no more, no
  fewer; no leftover tenant-system tables from 0001, confirming 0008's
  removal replayed correctly).
- **`alembic_version`: `('0023',)`** — correct, matches actual schema now.
- **RLS policy count in `public`: 45**.
- **`auth.users` count: 1`** — unchanged, confirming Auth was never touched.
- **`storage.buckets`: `['documents']`** — unchanged, confirming Storage was
  never touched.

Schema recovery is complete and verified. No data restoration was
attempted or is possible (see `DATA_RECOVERY_ASSESSMENT.md`).

## Phase 1-3 Verification (completed)

Run in small batches (a single monolithic ~340-test run repeatedly proved
unreliable against the free-tier Supabase pooler under sustained load —
not a code issue; isolated re-runs of anything that failed always passed
cleanly). All batches used the now-sandboxed test suite
(`tests/conftest.py`'s randomized-schema fix), so none of this touched the
real `public` schema.

| Batch | Files | Result |
|---|---|---|
| Phase 1 foundation | auth_required, health, resort_settings | 20/20 passed |
| Phase 2 | conversation_constants, conversations, customers | 18/18 passed |
| Phase 3 (a) | benchmark, chunking, embeddings, indexing | 19 passed, 5 skipped |
| Phase 3 (b) | retrieval_integration, retrieval_logic | 12/12 passed |
| Phase 3 (c) | security | 13/13 passed |
| Phase 3 (d) | sources, validation, governance | 37/37 passed |
| Phase 3 (e) | website_service, website_crawler | 14/14 passed |
| Safety controls | test_database_safety.py | 5/5 passed |
| Phase 4 pipeline (pre-existing, re-verified) | test_orchestration_pipeline.py | 6/6 passed |

**Two real bugs were found and fixed during this pass** (pre-existing,
unrelated to the incident itself — surfaced only because this was the
first time these tests ran cleanly to completion against a working
sandbox):

1. Six Phase 3 test files (`test_knowledge_benchmark.py`,
   `test_knowledge_indexing.py`, `test_knowledge_retrieval_integration.py`,
   `test_knowledge_security.py`, `test_knowledge_website_service.py`) called
   `MockEmbeddingProvider(dimensions=16|32|64)` before persisting chunks to
   the database — but `knowledge_chunks.embedding` is a fixed
   `vector(1536)` pgvector column, so every such insert failed with
   `expected 1536 dimensions, not N`. Fixed by removing the mismatched
   override so the provider defaults to `EMBEDDING_DIMENSIONS` (1536),
   which is what the column actually requires.
   (`test_knowledge_embeddings.py`'s own use of small dimensions was
   correctly left alone — those are pure in-memory logic tests with no
   database write.)
2. One transient `ConnectionDoesNotExistError` (a mid-operation connection
   drop against the pooler) — confirmed non-reproducible by re-running the
   affected test alone immediately afterward (passed).

## Outstanding Gap: No Backup/Export Process

Per the incident's own root cause, this project has **no backup or
point-in-time-recovery** configured. This recovery restored *schema* only;
had there been real customer/conversation data at the time, none of it
would have been recoverable regardless of any fix in this report. Setting
up an actual backup process (Supabase's paid-tier PITR, or a scheduled
`pg_dump` to external storage) was outside this incident response's scope
but is a real, still-open risk — flagged here rather than silently
considered "done."

## Status

Schema recovery, safety-control hardening, and Phase 1-3 structural/
functional re-verification are all complete. Per the user's own gate
criteria, real embeddings/Redis validation and Phase 4 resumption are the
next steps — both require explicit go-ahead before any paid API call or
further feature work, per the original incident-response instructions.
