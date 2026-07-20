# Phase X Audit — Dashboard Restructure, Feature Integration, Production Hardening

This audit was performed before any Phase X code was written, to establish what
already existed and worked (Phases 1–5) versus what was genuinely missing. Its
purpose was to prevent duplicate work: every stage below reused an existing
backend surface wherever one existed, and only added a new domain where the
brief's required feature had no real backing data or endpoint at all.

## Dashboard (`apps/dashboard`) — state before Phase X

- No app shell: `dashboard-nav.tsx` was a flat 7-link row re-rendered per page.
  No sidebar, no persistent header, no user-profile UI beyond ad-hoc email
  text on the home page.
- Route protection was a hand-copied `getServerAccessToken()` + `redirect("/login")`
  check duplicated in every page component — no middleware.
- No refresh-token flow: an expired access token just went stale with no
  silent recovery.
- Conversations page was a flat table + a 2-column detail view (messages | AI
  decision trace). **No reply composer for staff at all** — despite the
  backend already supporting staff-authored messages (see below). No
  search/filter/assign, no live updates.
- Knowledge pages were the most complete section already: upload / list /
  detail / jobs / search / website-crawl all worked.
- Resort settings was a one-shot setup wizard, not an always-editable
  settings page.
- No shared design system: hand-rolled Tailwind class strings repeated
  everywhere, no Button/Card/Input primitives, no chart library.

## Backend (`apps/api`) — reusable vs. genuinely missing

| Area | Found | Decision |
|---|---|---|
| Conversations | Rich already: `status`, `priority`, `assigned_agent_id`, `ai_active`/`human_active`, `tags`, full CRUD/assign/status/state router, and — critically — `POST /{id}/messages` already existed, was auth-protected, and persisted a message by `sender_type` **without invoking the AI pipeline**. This was already the correct staff-reply endpoint; no UI used it. | Reuse as-is. Add only: priority/ai_active list filters, unread tracking (a query addition, no new column), unassign via the existing generic PATCH. |
| Customers | `Customer` + `CustomerContact` + `CustomerNote` + `CustomerTag`, full CRUD/search router. Existing test suite already treated `"vip"` as a **tag**, not a column. | Reuse as-is. Add only batched lookups (tags/contacts/conversation-stats per page) to avoid N+1 queries in the new list views. |
| Users | Bare auth-mirror (`id`, `email`, `full_name`, `avatar_url`), **no router at all**. | Add `role`/`status`/`last_login_at` columns (migration 0025) + a new `app/users` router. `role` is display-only, never RBAC-enforcing (this deployment has no permissions system). |
| Audit | `AuditLog` model + `record_audit_event()` writer already complete and rich (actor/action/resource/before-after/metadata/ip/correlation_id) — but **no read endpoint existed anywhere**. | Add a read-only `app/audit` router + repository. No new table. |
| Booking | No booking table existed. `app.orchestration.models.ServiceRequest` (already in place since migration 0022) captures exactly "safe enquiry, not a fake completed operation" records, with `request_type="booking_enquiry"` already written by the `create_booking_enquiry` tool. | Reuse `ServiceRequest` — no new table. New `app/service_requests` module is a thin, scoped read/update surface over it. Its own `status` column (open/in_progress/resolved/cancelled) stays untouched; a `booking_status` (pending_review/confirmed/rejected/completed) and `staff_notes` live inside the existing `details` JSONB. |
| Notifications | Nothing existed. | Genuinely new domain (migration 0026), populated from real event points already in the codebase (handoff escalation, new booking enquiry, knowledge reprocess failure) — never a synthetic/demo event. |
| Customer Feedback | The only feedback signal was webchat's guest thumbs-up/down, written **only into the audit log** (`webchat.feedback_submitted`), not a queryable table. | Genuinely new domain (migration 0027). webchat's existing `submit_feedback()` keeps its current audit-log write untouched and additionally inserts one row into the new table. |
| Settings | `ResortSettings` already had name/contact/address/timezone/default_language/logo/brand-colors/check-in-out **and** a `settings_metadata` JSONB catch-all. | General Settings needed **no migration** — the AI-behavior fields (business hours, supported languages, chat availability, hand-off hours, fallback message, AI display name, emergency contact) all live in the existing JSONB. |
| Health / monitoring | `/healthz` and `/readyz` liveness/readiness probes existed; nothing staff-facing. Redis is configured in `Settings` but **never actually wired into any code path** — rate limiting (`app/rate_limit.py`) is explicitly in-process/interim, and there is no ingestion queue using it either. | Add staff-only `app/health/service.py` aggregation endpoints. Redis is reported honestly as "not configured / not wired in" rather than faking a ping. |
| Analytics | Nothing existed beyond ad-hoc counts on individual list pages. | New `app/analytics` module computing every metric directly from `conversations`, `customers`, `service_requests`, `customer_feedback`, and `notifications` — no invented numbers, no fabricated trend lines. |

## Common backend patterns replicated everywhere new

- `app/common/pagination.py` (`PageParams`, `PageMeta`, `build_page_meta`) —
  every new/extended list endpoint returns `{"items": [...], "meta": {...}}`.
- `app/common/responses.py`'s `success()` envelope on every endpoint.
- Batched `get_X_by_ids(db, ids) -> dict[id, value]` lookups (customers,
  users) instead of per-row queries, matching the existing
  `get_conversation_stats_by_customer` pattern.
- RLS on every new table follows the single-resort pattern established in
  migrations 0009/0019/0023/0024: the backend's `service_role` connection is
  the real authorization gate; `auth.uid() IS NOT NULL` is defense-in-depth
  for any direct Postgres/PostgREST access path.
