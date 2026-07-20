# Backend Domains Added or Extended in Phase X

## New domains

### `app/users` (Stage 4)
- Migration 0025 adds `role` (String, default `"Administrator"`, display-only
  — never RBAC-enforcing), `status` (`active`/`inactive`), `last_login_at`.
- `repository.py`: `list_users` (search/status filter, paginated),
  `get_names_by_ids` (batched, reused by Audit Logs for actor names).
- `service.py`: `mark_login` (called from `/auth/login`), `update_user`.
- `router.py`: `GET /api/v1/users`, `GET /api/v1/users/{id}`,
  `PATCH /api/v1/users/{id}`.

### `app/service_requests` (Stage 5) — Booking Management
- No new table — a thin read/update surface over
  `app.orchestration.models.ServiceRequest`, scoped to
  `request_type == "booking_enquiry"`.
- `BookingRequestOut.from_service_request()` flattens the enquiry's `details`
  JSONB (`check_in_date`, `num_nights`, `adults`, `room_category`, plus
  staff-added `booking_status`/`staff_notes`) into fixed response fields.
- `router.py`: `GET /api/v1/bookings`, `GET /api/v1/bookings/{id}`,
  `PATCH /api/v1/bookings/{id}` (status / booking_status / staff_notes /
  assigned_agent_id).

### `app/notifications` (Stage 6)
- Migration 0026. A resort-wide shared feed (`read_at`/`read_by_user_id`
  directly on the row — no per-recipient join table, matching the rest of
  this single-resort deployment's no-per-user-scoping philosophy).
- `service.notify()` is self-committing (unlike `record_audit_event`, which
  relies on the caller's transaction) so a notification is never silently
  lost if a call site forgets to commit afterward.
- Emission points: `app/orchestration/pipeline.py` (handoff escalation),
  `app/orchestration/tools/handlers.py` (new `booking_enquiry`),
  `app/knowledge/service.py` (`reprocess_source` failure),
  `app/feedback/service.py` (new feedback row).
- `router.py`: `GET /api/v1/notifications`,
  `GET /api/v1/notifications/unread-count`,
  `POST /api/v1/notifications/{id}/read`,
  `POST /api/v1/notifications/read-all`.

### `app/feedback` (Stage 7) — Customer Feedback
- Migration 0027. Mirrors the one real signal that exists — webchat's
  thumbs-up/down (`FEEDBACK_RATINGS = ("up", "down")`) — not a fabricated
  star scale.
- `service.record_webchat_feedback()` is the only write path today, called
  additively from `app/webchat/service.py`'s existing `submit_feedback()`
  (its audit-log write is untouched).
- `repository.get_stats()` returns real aggregate counts only (by rating, by
  category) — no sentiment scoring.
- `router.py`: `GET /api/v1/feedback`, `GET /api/v1/feedback/stats`,
  `GET /api/v1/feedback/{id}`, `PATCH /api/v1/feedback/{id}`.

### `app/analytics` (Stage 9) — Dashboard & Analytics home
- No new table — every metric is a live aggregation over `conversations`,
  `customers`, `service_requests`, `customer_feedback`, `notifications`.
- `service.resolve_range()` supports `today`/`7d`/`30d`/`custom` (with
  explicit `start`/`end`), rejecting an unknown range key or an inverted
  custom range.
- `router.py`: `GET /api/v1/analytics/dashboard?range=...`.

## Extended domains

### `app/audit` (Stage 8)
- Previously model + writer only, no read endpoint anywhere. Added
  `repository.py` (`list_audit_logs` — action/resource_type/search/date-range
  filters) and `router.py`: `GET /api/v1/audit/logs`.

### `app/health` (Stage 8)
- Added `service.py`: `get_integrations_status()` (masked API-key fragments
  only — first 4 + last 4 characters, e.g. `sk-a…mnop` — never a raw
  secret; Redis reported as "not wired into any code path" rather than
  faking a ping) and `get_system_status()` (aggregated status strings only,
  never a stack trace or environment variable).
- New staff-only endpoints (unlike the public `/healthz`/`/readyz` probes):
  `GET /api/v1/health/integrations`, `GET /api/v1/health/system`.

### `app/conversations`, `app/customers`, `app/knowledge` (Stages 1–3)
- Conversations: unread tracking (SQL `exists()`/`~exists()` subquery, no
  new column), `priority`/`ai_active` list filters, batched customer-name
  lookup, `POST /{id}/read`, `POST /{id}/unread`.
- Customers: batched `get_tags_by_customer_ids`, `get_contacts_by_customer_ids`,
  and `get_conversation_stats_by_customer` — replacing what would otherwise
  be an N+1 query per row on the list page.
- Knowledge: `GET /sources/{id}/chunks` (paginated chunk browser),
  `POST /sources/{id}/reprocess` (re-extracts from the already-stored file
  via `KnowledgeIngestionJob` tracking), `DELETE /sources/{id}` (hard delete,
  cascades via existing FK `ondelete=CASCADE`, blocked while the source is
  `active`/`retrieval_enabled`).

### `app/auth` (Stage 4)
- `/auth/login` now also calls `mark_login()`; `/auth/me` now returns real
  `role`/`status`/`last_login_at` instead of the Stage 0 placeholder
  defaults.
