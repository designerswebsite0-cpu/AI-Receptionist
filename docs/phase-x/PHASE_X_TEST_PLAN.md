# Phase X Test Plan

## Methodology

Every backend stage was verified against the **real Supabase project**, not
a mocked database — using the pre-existing disposable-schema sandbox
pattern in `tests/conftest.py`: each test run creates a randomly named
schema (`test_<uuid>`), runs `Base.metadata.create_all` into it, and drops it
afterward. `DROP SCHEMA ... CASCADE` is scoped to that random name, so it can
never reach `public` even if `DATABASE_URL` (not a separate
`TEST_DATABASE_URL`) is what's configured — see
`docs/incidents/DATABASE_SAFETY_CONTROLS.md`.

Each stage's verification, run before moving to the next stage:

1. `cd apps/api && python -m uv run ruff check .`
2. `cd apps/api && python -m uv run alembic upgrade head` (stages with a migration)
3. `cd apps/api && python -m uv run pytest tests/test_<new_or_touched>.py -q`
   with `DATABASE_URL`/`TEST_DATABASE_URL` etc. exported from the repo-root
   `.env` into the shell first
4. `cd apps/dashboard && npm run lint && npm run typecheck && npm run build`

Stages that touched a shared code path also re-ran the existing tests for
that path to confirm no regression — e.g. Stage 6's notification wiring
inside `app/orchestration/tools/handlers.py` and `app/orchestration/pipeline.py`
was checked against `test_orchestration_tool_handlers.py` and
`test_orchestration_pipeline.py` (17/17 passed, unchanged); Stage 7's
additive insert into `webchat.submit_feedback()` was checked against
`test_webchat_service.py` (10/10 passed, including the pre-existing
`test_submit_feedback_writes_an_audit_event`, unchanged).

## New test files (Phase X)

| File | Domain | What it covers |
|---|---|---|
| `tests/test_users.py` | Staff Management | defaults, update, 404, list filters, batched open-conversation count |
| `tests/test_booking_requests.py` | Booking Management | detail flattening, non-booking-type rejection, 404, update merge semantics, list filters |
| `tests/test_notifications.py` | Notifications | create, idempotent mark-read, 404, unread filter, mark-all-read |
| `tests/test_customer_feedback.py` | Customer Feedback | webchat record path, 404, update, rating filter, stats aggregation |
| `tests/test_settings_hub.py` | Settings hub | audit log filter/search, batched actor-name resolution, key masking, system/integrations status shape |
| `tests/test_analytics.py` | Dashboard & Analytics | range validation, real-data counting, custom-range exclusion of out-of-range data |

## A pre-existing, unrelated bug found and left alone

While verifying Stage 3, `tests/test_knowledge_indexing.py::test_index_source_version_removes_stale_chunks_when_content_shrinks`
was found failing. Confirmed pre-existing and unrelated to Phase X by
stashing every Phase X change to `app/knowledge/` and reproducing the
identical failure on the unmodified code. Flagged as a separate background
task rather than fixed inline, since it's a chunk-diffing logic bug in code
Phase X never touched (`app/knowledge/indexing.py` / `chunking/strategies.py`).

## Full-suite run (Stage 10)

A full `pytest` run (all 39 test files, ~[N] tests) was executed at the end
of Phase X — see `PHASE_X_COMPLETION_REPORT.md` for the pass/fail count and
any findings.

## Website webchat regression check

Phases 3/4/5's webchat pipeline was not touched beyond the two additive
insert points already listed (`app/orchestration/pipeline.py`'s handoff
notification, `app/webchat/service.py`'s feedback insert) — both are
side-effect additions after the existing logic already completed, never a
change to the guest-facing response, retrieval, or handoff behavior itself.
Verified via `test_webchat_service.py`'s full suite (10/10 passed) and the
full backend suite's `test_webchat_*` / `test_orchestration_*` files.
