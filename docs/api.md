# api.md
# AI Receptionist Platform API Specification (v1)

> Status: Living API Specification
> Scope: Unified APIs for Chat, Calls, Customer360 and Knowledge Intelligence Engine
> Architecture: Single-resort deployment template (Phase 2.5) — one deployment, one resort, no tenant scoping

---

# API Principles

- REST-first
- JSON request/response
- Versioned (`/api/v1`)
- HTTPS only
- JWT Authentication (any authenticated user has full access — see rules.md §4)
- Idempotent where required

---

# Health

GET /healthz — liveness probe, unauthenticated, no dependency checks.
GET /readyz  — readiness probe, unauthenticated, verifies the database is reachable.

---

# Authentication

POST /api/v1/auth/login
POST /api/v1/auth/logout
POST /api/v1/auth/refresh
GET  /api/v1/auth/me

**Implementation note:** these endpoints are real backend proxies to
Supabase GoTrue (via `httpx`), not thin documentation of a client-side Supabase
Auth call. Every client — dashboard, widget, and the future voice-agent —
authenticates through this one backend surface so login/logout are
consistently audited (`audit_logs`) and no client ever needs the Supabase
anon/service keys directly for auth. `/auth/login` is rate-limited
(in-process token bucket; moves to an Upstash-backed shared limiter once
Redis is wired in Phase 3+ — see roadmap.md tech debt).

`/auth/me` returns the verified user plus `resort_configured` (whether
`resort_settings` has been created yet) — no memberships/roles (Phase 2.5
removed the tenant/role system entirely, not just its enforcement).

---

# Resort Settings

**Status: implemented (Phase 2.5).** Replaces the old Tenants section —
there is exactly one resort per deployment, configured once via first-run
setup.

POST  /api/v1/resort/settings — create (fails with 409 if already configured)
GET   /api/v1/resort/settings — get the current configuration (404 if not yet configured)
PATCH /api/v1/resort/settings — update any subset of fields

Any authenticated user may call these (rules.md §4 — no role restriction).
`resort_settings` allows exactly one row, enforced by a database-level
UNIQUE constraint on a `singleton` column, not just an application check.

---

# Customer 360

**Status: foundation implemented in Phase 2, flattened in Phase 2.5.** No
tenant scoping — a verified session is all that's required.

POST   /api/v1/customers
GET    /api/v1/customers?search=&tag=&page=&page_size=
GET    /api/v1/customers/{customer_id}
PATCH  /api/v1/customers/{customer_id}
POST   /api/v1/customers/{customer_id}/contacts
GET    /api/v1/customers/{customer_id}/notes
POST   /api/v1/customers/{customer_id}/notes
POST   /api/v1/customers/{customer_id}/tags
DELETE /api/v1/customers/{customer_id}/tags/{tag}

Not yet implemented: `/summary` (AI-generated brief — Phase 4),
`/history`/`/timeline` (derived from conversations + bookings — query
directly for now, a dedicated aggregating endpoint can follow once Phase 7
bookings exist), `DELETE /customers/{id}` (no hard-delete path yet; add
with the data-retention work referenced in rules.md §19).

---

# Conversations

**Status: foundation implemented in Phase 2, flattened in Phase 2.5.**

POST   /api/v1/conversations
GET    /api/v1/conversations?status=&channel=&assigned_agent_id=&customer_id=&page=&page_size=
GET    /api/v1/conversations/{conversation_id}
PATCH  /api/v1/conversations/{conversation_id}
POST   /api/v1/conversations/{conversation_id}/assign
POST   /api/v1/conversations/{conversation_id}/status
POST   /api/v1/conversations/{conversation_id}/close
POST   /api/v1/conversations/{conversation_id}/state

`status` (lifecycle/queue state — one of `open`, `waiting_for_guest`,
`waiting_for_staff`, `ai_handling`, `human_handling`, `escalated`, `closed`,
`blocked`) and `state` (dialogue state — one of `greeting`,
`discovering_needs`, `collecting_information`, `recommending`, `booking`,
`waiting`, `confirmation`, `upselling`, `support`, `escalation`, `closed`)
are independent — see architecture.md §4.4 and product_decisions.md for
why, and why `blocked` is retained from the original architecture spec
alongside the 7 statuses the Phase 2 brief specified.

`/handoff` from an earlier sketch is superseded by `/status` with
`status=human_handling` (also flips `ai_active`/`human_active`
accordingly) — one endpoint, not two overlapping ones.

---

# Messages

**Status: foundation implemented in Phase 2, flattened in Phase 2.5.**
Nested under a conversation, not flat at the top level.

GET    /api/v1/conversations/{conversation_id}/messages?page=&page_size=
POST   /api/v1/conversations/{conversation_id}/messages
POST   /api/v1/conversations/{conversation_id}/messages/{message_id}/read

`POST .../messages` accepts an optional `external_message_id`; sending the
same one twice returns the original message instead of creating a
duplicate (rules.md §13 idempotency) — this is what a WhatsApp webhook
retry (Phase 6) will rely on. Attachments are metadata-only right now
(`storage_path` pointing at a private Supabase Storage object the caller
already uploaded some other way) — there's no upload endpoint yet; that
arrives with the Knowledge Intelligence Engine's storage plumbing (Phase 3).

Flat `/api/v1/messages/send` and `/api/v1/messages/retry` from an earlier
sketch are not implemented — retry logic is meaningless before Phase 6
gives us a real provider whose deliveries can actually fail and need
retrying.

---

# WhatsApp

POST /api/v1/webhooks/whatsapp
GET  /api/v1/webhooks/whatsapp
POST /api/v1/whatsapp/send
POST /api/v1/whatsapp/template

---

# Web Chat

POST /api/v1/widget/session
POST /api/v1/widget/message
GET  /api/v1/widget/config

---

# Voice (Future)

POST /api/v1/calls/start
POST /api/v1/calls/end
POST /api/v1/calls/events
GET  /api/v1/calls/{id}
GET  /api/v1/calls/{id}/transcript

---

# Knowledge Intelligence Engine

POST   /api/v1/knowledge/upload
POST   /api/v1/knowledge/website
POST   /api/v1/knowledge/manual
GET    /api/v1/knowledge/sources
GET    /api/v1/knowledge/sources/{id}
DELETE /api/v1/knowledge/sources/{id}
POST   /api/v1/knowledge/sources/{id}/reindex
GET    /api/v1/knowledge/jobs/{id}
POST   /api/v1/knowledge/search

Internal:
POST /api/v1/internal/knowledge/retrieve

---

# Business Actions

POST /api/v1/bookings
PATCH /api/v1/bookings/{id}
DELETE /api/v1/bookings/{id}

POST /api/v1/orders
PATCH /api/v1/orders/{id}

POST /api/v1/leads
PATCH /api/v1/leads/{id}

---

# Dashboard

GET /api/v1/dashboard/metrics
GET /api/v1/dashboard/activity
GET /api/v1/dashboard/inbox

---

# Analytics

GET /api/v1/analytics/business
GET /api/v1/analytics/customers
GET /api/v1/analytics/ai
GET /api/v1/analytics/knowledge

---

# Admin

**Not implemented.** A single-resort deployment has no cross-tenant
superadmin concept (Phase 2.5 removed the tenant/role system entirely —
see product_decisions.md). Staff account management, if ever needed beyond
Supabase Auth's own user management, would live here — not built yet and
not currently planned.

GET    /api/v1/admin/users
POST   /api/v1/admin/users
PATCH  /api/v1/admin/users/{id}
DELETE /api/v1/admin/users/{id}

GET /api/v1/admin/settings
PATCH /api/v1/admin/settings

---

# Common Response

Success

{
  "success": true,
  "data": {}
}

Error

{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Description"
  }
}

---

# Security Rules

- JWT required unless endpoint is public
- Verify webhook signatures
- Validate request schema
- Audit critical actions
- Rate limit sensitive endpoints
- Never expose Supabase service-role keys to any client

---

# Versioning

Current:
v1

Future:
v2 introduces backward-compatible expansion where possible.
