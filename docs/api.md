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

Status: **Implemented** (Phase 3, 2026-07-18; `app/knowledge/router.py`).
Endpoint shapes below are the actual implementation — reconciled with
this section's pre-Phase-3 draft (no separate `/website`/`/manual`
registration endpoints or a `DELETE`/`reindex` pair; see the
per-endpoint notes for what replaced each).

POST   /api/v1/knowledge/sources/upload — multipart file upload; runs the
  full pipeline synchronously (validate → Storage upload → register →
  extract → chunk → embed). Draft's `/upload` kept the same path.
GET    /api/v1/knowledge/sources — list, filterable by
  `source_type`/`visibility`/`status`/`search`, paginated.
GET    /api/v1/knowledge/sources/{id}
PATCH  /api/v1/knowledge/sources/{id} — governance fields only
  (title/description/category/visibility/source_priority/authoritative/
  effective_date/expiry_date/tags); content/processing fields are never
  client-writable.
POST   /api/v1/knowledge/sources/{id}/approve
POST   /api/v1/knowledge/sources/{id}/reject — body: `{"reason": "..."}`
POST   /api/v1/knowledge/sources/{id}/activate — the only path by which
  `retrieval_enabled` ever becomes true; enforces approved + processing
  completed + malware scan clean/unscanned_dev_only + non-archive
  visibility, all explicitly, before flipping it.
POST   /api/v1/knowledge/sources/{id}/archive — replaces the draft's
  `DELETE`: sources are archived (soft, auditable, `retrieval_enabled`
  revoked), never hard-deleted.
GET    /api/v1/knowledge/sources/{id}/versions
GET    /api/v1/knowledge/media?source_id={id}
GET    /api/v1/knowledge/jobs — filterable by `job_type`/`job_status`, paginated.
GET    /api/v1/knowledge/jobs/{id}
POST   /api/v1/knowledge/search — the staff search playground / benchmark
  entry point. Body: `{"query", "guest_only", "limit", "chunk_type"}`.
  Response includes citations (source title/id/version/section/date/
  priority/URL — never a storage path) and the `retrieval_log_id` every
  call is recorded under.
POST   /api/v1/knowledge/website/crawl — triggers a live crawl for a
  website source (creates the source if `source_id` doesn't exist yet),
  returns the `WebsiteCrawlRun` summary including per-page results.

All endpoints require `get_current_user` (staff authentication) — there
is no unauthenticated guest-facing HTTP endpoint yet. The guest-facing
retrieval path (once the AI Orchestration layer, Phase 4, lands) will
call `app.knowledge.retrieval.service.search` in-process, not through
this router — see docs/phase-3/IMPLEMENTATION_PLAN.md §8 for what's
deliberately out of scope this phase (no answer-generation agent, no
WhatsApp/voice channel wiring).

Internal (draft, not built this phase — deferred to Phase 4 AI Orchestration):
POST /api/v1/internal/knowledge/retrieve

---

# AI Orchestration

Status: **Implemented** (Phase 4, 2026-07-18; `app/orchestration/router.py`).
All endpoints require `get_current_user` (this deployment's single-resort
auth model — no separate role/permission check). All under
`/api/v1/orchestration`.

POST /messages/{conversation_id}/process — body: `{"message_id", "channel"}`.
  Runs the full pipeline (classify → extract → retrieve → assemble →
  generate → validate tool calls → execute approved tools → validate
  response → persist) for one already-persisted guest message. The single
  entry point every channel (webchat now, WhatsApp/voice later) calls.
  Idempotent: replaying an already-processed `message_id` returns the
  prior outcome without re-invoking the LLM or re-executing any tool.
GET  /conversations/{id}/state — current `current_state`/`flow_state`/
  `status`/`ai_active`/`human_active` plus the most recent turn's detected
  intent + confidence.
GET  /conversations/{id}/turns — paginated `orchestration_turns` history
  (the decision trace — never chain-of-thought).
GET  /turns/{id}/citations — the citations (chunk id/source title/
  priority/authoritative/score) a specific turn's response was grounded in.
GET  /turns/{id}/tool-executions — the tool name/input/output/status a
  specific turn proposed and (if approved) executed.
POST /conversations/{id}/handoff — body: `{"reason", "department",
  "priority"}`. Staff-initiated handoff, independent of the deterministic
  handoff policy engine's own automatic triggers.
POST /conversations/{id}/release — staff releases a conversation back to
  the AI after handling a handoff; resumes at `discovering_needs` if it
  was escalated (never loops straight back into another handoff).
GET  /health/providers — configuration presence only (`llm_configured`,
  `llm_fallback_configured`, `embedding_configured`) — never a real API
  call (would cost money on every health check) and never key values.

Deliberately deferred this phase (thin-wrapper endpoints, not core
pipeline logic — see `docs/phase-4/PHASE_4_COMPLETION_REPORT.md`):
`POST /messages/{id}/preview` (dry-run without persisting) and
`POST /turns/{id}/retry` — the existing idempotent-replay behavior of
`/process` already covers the most common retry scenario (a redelivered
message), and both would need a non-persisting pipeline variant that
doesn't exist yet.

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
