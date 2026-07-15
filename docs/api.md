# api.md
# AI Receptionist Platform API Specification (v1)

> Status: Living API Specification
> Scope: Unified APIs for Chat, Calls, Customer360 and Knowledge Intelligence Engine

---

# API Principles

- REST-first
- JSON request/response
- Versioned (`/api/v1`)
- HTTPS only
- JWT Authentication
- Tenant isolation on every request
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

**Implementation note (Phase 1):** these endpoints are real backend proxies to
Supabase GoTrue (via `httpx`), not thin documentation of a client-side Supabase
Auth call. Every client — dashboard, widget, and the future voice-agent —
authenticates through this one backend surface so login/logout are
consistently audited (`audit_logs`) and no client ever needs the Supabase
anon/service keys directly for auth. `/auth/login` is rate-limited
(in-process token bucket in Phase 1; moves to an Upstash-backed shared
limiter once Redis is wired in Phase 3+ — see roadmap.md tech debt).
`/auth/me` returns the verified user plus their active tenant memberships.

---

# Tenants

GET    /api/v1/tenants/me                          — list tenants the caller belongs to
POST   /api/v1/tenants                              — create a tenant; caller becomes its owner
GET    /api/v1/tenants/{tenant_id}                  — get tenant details (requires `tenant.view`)
GET    /api/v1/tenants/{tenant_id}/members           — list members (requires `members.view`)
POST   /api/v1/tenants/{tenant_id}/members           — invite a member by email (requires `members.invite`)
PATCH  /api/v1/tenants/{tenant_id}/members/{member_id} — change a member's role (requires `members.update_role`)
DELETE /api/v1/tenants/{tenant_id}/members/{member_id} — remove a member (requires `members.remove`)

**Conflict resolution (Phase 1):** earlier drafts of this document had no
Tenants section even though database.md/architecture.md require a full
tenant module. This section is the authoritative one. `tenant_id` in every
path above is resolved from the URL but never blindly trusted — the backend
verifies the caller has an active `tenant_members` row for that tenant
before authorizing anything (see `app.deps.get_current_membership`), which
satisfies rules.md §5's "never trust a client-supplied tenant ID" rule
without requiring a separate header scheme.

**Roles (Phase 1, system-seeded, shared across all tenants):** `owner`,
`admin`, `manager`, `staff`, `read_only`. Permission matrix lives in
`apps/api/app/roles/seed_data.py` and is frozen into Alembic migration
`0001` at write time (migrations must stay reproducible even if the seed
data module changes later).

**Superseded:** the `# Admin` section's `/api/v1/admin/users` endpoints
below are not implemented in Phase 1. Tenant member management is exposed
exclusively via `/api/v1/tenants/{tenant_id}/members` instead — there is no
cross-tenant superadmin surface yet.

**Known Phase 1 limitation:** inviting a member requires that person to
already have a Supabase Auth account (matched by email). A pending-invite
flow (invite email, deferred until an account exists) is deferred to Phase
7 alongside Resend integration — this is documented tech debt, not a
silent gap.

---

# Customer 360

**Status: foundation implemented in Phase 2.** Nested under
`/tenants/{tenant_id}/` for the same reason the Tenants section above is —
tenant_id is resolved from the URL but verified against the caller's own
membership before anything is authorized (`app.deps.get_current_membership`).
This supersedes the flat `/api/v1/customers` paths originally sketched
below; there is no cross-tenant customer listing.

POST   /api/v1/tenants/{tenant_id}/customers
GET    /api/v1/tenants/{tenant_id}/customers?search=&tag=&page=&page_size=
GET    /api/v1/tenants/{tenant_id}/customers/{customer_id}
PATCH  /api/v1/tenants/{tenant_id}/customers/{customer_id}
POST   /api/v1/tenants/{tenant_id}/customers/{customer_id}/contacts
GET    /api/v1/tenants/{tenant_id}/customers/{customer_id}/notes
POST   /api/v1/tenants/{tenant_id}/customers/{customer_id}/notes
POST   /api/v1/tenants/{tenant_id}/customers/{customer_id}/tags
DELETE /api/v1/tenants/{tenant_id}/customers/{customer_id}/tags/{tag}

Requires `customers.view` (read endpoints) / `customers.manage` (write
endpoints) — currently unenforced while `RBAC_ENFORCEMENT_ENABLED=false`
(rules.md §4), but every endpoint already declares the correct requirement
so enforcement is a config flip, not a code change.

Not yet implemented: `/summary` (AI-generated brief — Phase 4),
`/history`/`/timeline` (derived from conversations + bookings — query
directly for now, a dedicated aggregating endpoint can follow once Phase 7
bookings exist), `DELETE /customers/{id}` (no hard-delete path yet; add
with the data-retention work referenced in rules.md §19).

---

# Conversations

**Status: foundation implemented in Phase 2.** Same tenant-scoped
convention as Customers above — supersedes the flat paths originally
sketched below.

POST   /api/v1/tenants/{tenant_id}/conversations
GET    /api/v1/tenants/{tenant_id}/conversations?status=&channel=&assigned_agent_id=&customer_id=&page=&page_size=
GET    /api/v1/tenants/{tenant_id}/conversations/{conversation_id}
PATCH  /api/v1/tenants/{tenant_id}/conversations/{conversation_id}
POST   /api/v1/tenants/{tenant_id}/conversations/{conversation_id}/assign
POST   /api/v1/tenants/{tenant_id}/conversations/{conversation_id}/status
POST   /api/v1/tenants/{tenant_id}/conversations/{conversation_id}/close
POST   /api/v1/tenants/{tenant_id}/conversations/{conversation_id}/state

`status` (lifecycle/queue state — one of `open`, `waiting_for_guest`,
`waiting_for_staff`, `ai_handling`, `human_handling`, `escalated`, `closed`,
`blocked`) and `state` (dialogue state — one of `greeting`,
`discovering_needs`, `collecting_information`, `recommending`, `booking`,
`waiting`, `confirmation`, `upselling`, `support`, `escalation`, `closed`)
are independent — see architecture.md §4.4 and product_decisions.md for
why, and why `blocked` is retained from the original architecture spec
alongside the 7 statuses the Phase 2 brief specified.

`/handoff` from the original sketch is superseded by `/status` with
`status=human_handling` (also flips `ai_active`/`human_active`
accordingly) — one endpoint, not two overlapping ones.

Requires `conversations.view` / `conversations.manage` (same
currently-unenforced-by-default caveat as Customers above).

---

# Messages

**Status: foundation implemented in Phase 2.** Nested under a conversation,
not flat — supersedes the sketch below.

GET    /api/v1/tenants/{tenant_id}/conversations/{conversation_id}/messages?page=&page_size=
POST   /api/v1/tenants/{tenant_id}/conversations/{conversation_id}/messages
POST   /api/v1/tenants/{tenant_id}/conversations/{conversation_id}/messages/{message_id}/read

`POST .../messages` accepts an optional `external_message_id`; sending the
same one twice returns the original message instead of creating a
duplicate (rules.md §13 idempotency) — this is what a WhatsApp webhook
retry (Phase 6) will rely on. Attachments are metadata-only right now
(`storage_path` pointing at a private Supabase Storage object the caller
already uploaded some other way) — there's no upload endpoint yet; that
arrives with the Knowledge Intelligence Engine's storage plumbing (Phase 3).

Flat `/api/v1/messages/send` and `/api/v1/messages/retry` from the original
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

**Not implemented in Phase 1** — see the Tenants section above, which is the
current member-management surface. This section is reserved for a future
platform-level (cross-tenant) superadmin role, not yet built.

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
- Enforce tenant_id server-side
- Audit critical actions
- Rate limit sensitive endpoints
- Never expose internal IDs across tenants

---

# Versioning

Current:
v1

Future:
v2 introduces backward-compatible expansion where possible.

