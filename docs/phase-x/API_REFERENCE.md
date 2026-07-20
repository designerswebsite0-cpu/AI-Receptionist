# API Reference — Endpoints Added or Extended in Phase X

All responses use the existing `{"success": bool, "data": ...}` /
`{"success": false, "error": {"code", "message"}}` envelope
(`app/common/responses.py`). All paginated list endpoints return
`{"items": [...], "meta": {"page", "page_size", "total", "total_pages"}}`
via `app/common/pagination.py`, except the older Knowledge Base endpoints
(`/sources`, `/jobs`, `/sources/{id}/chunks`), which predate that helper and
return the flatter `{"items", "total", "offset", "limit"}` shape — noted here
as a pre-existing inconsistency, not something Phase X introduced.

## Staff Management — `/api/v1/users`
- `GET /api/v1/users` — list, filters: `status`, `search`; paginated
- `GET /api/v1/users/{id}` — detail, includes `assigned_conversation_count`
- `PATCH /api/v1/users/{id}` — update `full_name`/`role`/`status`

## Booking Management — `/api/v1/bookings`
- `GET /api/v1/bookings` — list, filters: `status`, `booking_status`; paginated
- `GET /api/v1/bookings/{id}` — detail
- `PATCH /api/v1/bookings/{id}` — update `status`/`booking_status`/`staff_notes`/`assigned_agent_id`

## Notifications — `/api/v1/notifications`
- `GET /api/v1/notifications` — list, filters: `unread_only`, `notification_type`; paginated
- `GET /api/v1/notifications/unread-count`
- `POST /api/v1/notifications/{id}/read`
- `POST /api/v1/notifications/read-all`

## Customer Feedback — `/api/v1/feedback`
- `GET /api/v1/feedback` — list, filters: `category`, `rating`, `status`; paginated
- `GET /api/v1/feedback/stats` — `{total, up_count, down_count, positive_rate, by_category}`
- `GET /api/v1/feedback/{id}`
- `PATCH /api/v1/feedback/{id}` — update `status`/`assigned_agent_id`

## Audit Logs — `/api/v1/audit`
- `GET /api/v1/audit/logs` — filters: `action`, `resource_type`, `search`, `date_from`, `date_to`; paginated; each row includes a resolved `actor_name`

## Health / System Monitoring — staff-only
- `GET /api/v1/health/integrations` — Supabase/OpenAI/Groq/Redis status, masked keys only
- `GET /api/v1/health/system` — aggregated `{overall, checks: {...}}`
- (unchanged, public) `GET /healthz`, `GET /readyz`

## Dashboard & Analytics — `/api/v1/analytics`
- `GET /api/v1/analytics/dashboard?range=today|7d|30d|custom&start=...&end=...`
  → `{summary, conversations_by_day, bookings_by_status, feedback_by_rating}`

## Extended existing endpoints

### `/api/v1/conversations`
- `GET` list gained `priority`, `ai_active`, `unread` filters
- `POST /{id}/read`, `POST /{id}/unread` (new)
- Response payloads gained `unread_count`, `customer_name`

### `/api/v1/customers`
- `GET` list and `GET /{id}` gained `tags`, `is_vip`, `conversation_count`,
  `last_interaction_at` (list also: `primary_contact`)

### `/api/v1/knowledge`
- `GET /sources/{id}/chunks` (new, paginated chunk browser)
- `POST /sources/{id}/reprocess` (new)
- `DELETE /sources/{id}` (new, guarded — 409 if `active`/`retrieval_enabled`)

### `/api/v1/auth`
- `GET /me` now also returns `role`, `status`, `last_login_at`
- `POST /login` now also stamps `last_login_at`
