# Phase X Implementation Plan — Dashboard Restructure, Feature Integration, Production Hardening

Executed stage by stage, each verified (backend `ruff check` + targeted
`pytest` against the real Supabase project via a disposable schema sandbox;
dashboard `npm run lint` + `npm run typecheck` + `npm run build`) before
moving to the next stage — see `PHASE_X_TEST_PLAN.md`. Commits were batched
roughly every 3 stages per an explicit instruction, not after every stage.

## Stage 0 — Dashboard shell + auth hardening
Replaced the flat nav with a collapsible sidebar (all 9 required sections +
Settings' 4 subsections), a persistent header with a real user-profile
button, and `src/middleware.ts` for centralized route protection (replacing
the per-page duplicated redirect check) with silent refresh-token recovery.
Added a small shared UI primitive set (`Button`/`Card`/`Input`/`EmptyState`/
`Skeleton`). Redesigned the login page (password show/hide, remember-session,
session-expired messaging) and fixed a login bug where every failure showed
a generic "something went wrong" instead of distinguishing wrong-credentials
from a genuine upstream/server outage.

## Stage 1 — Inbox
Backend: unread tracking (SQL-level `exists()`/`~exists()` subquery, no new
column), `priority`/`ai_active` list filters, batched customer-name lookup.
Frontend: real 3-panel layout (list | thread + composer | customer context)
wired onto the already-working `POST /conversations/{id}/messages` staff-reply
endpoint and the already-working handoff/release controls, with 8s polling.

## Stage 2 — Customer 360
Backend: batched tags/contacts/conversation-stats-by-customer lookups (no
N+1 queries), VIP derived from the existing `"vip"` tag convention. Frontend:
guest list + detail page (contacts, tags, staff notes, AI-inferred
preferences labeled as unconfirmed, linked conversation history).

## Stage 3 — Knowledge Base completion
Backend: a chunk-browse endpoint, a `reprocess` action (re-runs
extract→chunk→embed against the already-stored file, the same recovery path
used manually to fix a stuck source earlier), and a governance-guarded hard
delete (blocked while a source is `active`/`retrieval_enabled` — archive
first). Frontend: chunk browser page, reprocess/delete actions, ingestion
error surfaced directly on the source detail page.

## Stage 4 — Staff Management
Migration 0025 added `role` (display-only, default `"Administrator"`),
`status` (`active`/`inactive`), `last_login_at` to `users`. New `app/users`
domain (list/get/update, workload = open-conversation count via the existing
`assigned_agent_id` FK). `/auth/me` and `/auth/login` now surface real role/
status/last-login instead of the Stage 0 placeholder defaults.

## Stage 5 — Booking Management
New thin `app/service_requests` module scoped to
`request_type == "booking_enquiry"`, reusing the existing
`ServiceRequest` table (no new table). `booking_status` and `staff_notes`
live inside its `details` JSONB, kept separate from the shared, generic
`status` column every enquiry type uses. Frontend list + detail with a
triage panel (status, booking status, assignment, notes) — never implies a
confirmed reservation or live PMS availability.

## Stage 6 — Notifications
New `app/notifications` domain (migration 0026): a resort-wide shared feed
(no per-recipient scoping, matching the rest of this single-resort
deployment). Emitted from three real event points: handoff escalation
(`app/orchestration/pipeline.py`), a new booking enquiry
(`app/orchestration/tools/handlers.py`), and a knowledge reprocess failure
(`app/knowledge/service.py`). Frontend: header bell with an unread badge
(polling) + a notification center page.

## Stage 7 — Customer Feedback
New `app/feedback` domain (migration 0027) mirroring the one real signal
that exists — webchat's thumbs-up/down (`RATING_VALUES = ("up", "down")`) —
rather than inventing a star scale nothing collects. webchat's
`submit_feedback()` keeps its existing audit-log write untouched and
additionally inserts one structured row, plus emits a
`feedback_received` notification. Frontend: list + real analytics (up/down
counts, positive rate, category rollup — no fabricated sentiment scoring).

## Stage 8 — Settings hub
- **General**: no migration needed — extended the existing resort-setup
  form into an always-editable page using `ResortSettings` +
  `settings_metadata` JSONB.
- **Integrations**: new `app/health/service.py` reporting masked API-key
  fragments only (`sk-a…mnop`), never a raw secret; Redis reported honestly
  as not wired into any code path.
- **Audit Logs**: new read-only `app/audit` router/repository over the
  already-existing `AuditLog` table.
- **System Monitoring**: aggregated database/embedding-provider/LLM-provider/
  Redis status into one view — status strings only, never a stack trace or
  environment variable.

## Stage 9 — Dashboard & Analytics home
New `app/analytics` module computing every number from real tables
(`conversations`, `customers`, `service_requests`, `customer_feedback`,
`notifications`) with `today`/`7d`/`30d`/custom date-range filtering.
Installed `recharts` and replaced the placeholder home page with real stat
tiles, a conversations-per-day bar chart, a bookings-by-status breakdown,
and a feedback pie chart.

## Stage 10 — Docs, full verification, completion report
This directory, plus a full-suite `pytest` run, a full-project `ruff check`,
a dashboard `lint`/`typecheck`/`build`, and a website webchat regression
check — see `PHASE_X_COMPLETION_REPORT.md` for the results.
