# roadmap.md
# AI Receptionist Platform Roadmap (v1)

> Status: Living Product Roadmap
> Scope: Unified AI Receptionist Platform

---

# Guiding Principles

- Build a strong foundation first.
- Documentation before architecture changes.
- Security before features.
- Shared systems before channel-specific features.
- Customer360 and KIE power every channel.

---

# Phase 1 — Foundation

Status: **Implemented and verified** (2026-07-14). GitHub, Railway, Vercel,
and Supabase accounts are now provisioned (2026-07-15) as the default
infrastructure for all future deployment work — see requirements.md §6 and
product_decisions.md. Not yet deployed; local scaffold remains the
verified state until deployment is explicitly undertaken.

Goals

- [x] Repository setup
- [x] Monorepo structure (npm workspaces; Turborepo deferred until 3+ JS apps actually build)
- [x] FastAPI backend (config, logging, errors, health, auth, tenants, roles, audit)
- [x] Next.js dashboard (login, protected shell, tenant creation, health badge)
- [x] Docker (API Dockerfile pinned to python:3.12-slim; not yet built/run locally — no Docker installed on the dev machine used to scaffold this)
- [ ] Railway & Vercel — not deployed yet; deliberately deferred until credentials/hosting are set up
- [x] Supabase — client wiring + JWKS auth + RLS migrations written; no live project connected yet (scaffold-only, per product_decisions.md)
- [x] Authentication (Supabase GoTrue proxy + JWT verification)
- [x] Tenant management (tenants, tenant_settings, tenant_members, tenant_roles, tenant_permissions + RBAC)
- [x] Base CI/CD (GitHub Actions workflow written; not yet run — repo is not yet under git/GitHub, per user decision)
- [x] Audit logging foundation

Deliverable:
A secure multi-tenant foundation.

Known Phase 1 tech debt (tracked, not silent):

- Rate limiting on `/auth/login` is in-process (single-replica) — swap for an Upstash-backed shared limiter once Redis is wired in Phase 3.
- JWKS caching is in-process — move to a Redis-backed shared cache in Phase 3 alongside the rate limiter.
- Member invites require the invitee to already have a Supabase Auth account — a pending-invite-by-email flow arrives with Resend in Phase 7.
- No git repository has been initialized yet (user decision) and no Supabase/Docker credentials are configured — the code is written and unit-tested, but DB-dependent tests and real login have not been run end-to-end. See README.md for what's needed to do that.

---

# Current Development Focus (added 2026-07-15)

The active business implementation is a **Luxury 5-Star Resort** (see
docs/Goal.md, docs/functions.md). Channels remain WhatsApp + Website Chat
only — no voice work until Phase 9. The next build effort spans Phases
2–4 together rather than strictly sequentially, because the resort's
functions.md tool catalog and AI Intelligence Layer require Customer
360/Guest Profile, KIE/RAG, and AI Orchestration to land as one coherent
reasoning layer (architecture.md §4.4's 8-step pipeline):

- Intent Detection, Entity Extraction, Conversation State Machine (Phase 4)
- RAG Architecture + Knowledge Base over resort domains (Phase 3)
- Guest Memory (Phase 2 Customer 360, resort-flavored: favourite rooms,
  dietary preferences, celebrations, communication preferences)
- Recommendation Engine, Decision Engine, Sales/Emotional/Operational
  Intelligence, Human Handoff Intelligence (Phase 4)
- The Business Tool Layer itself (docs/functions.md §1–27) lands as Phase 7
  Business Action Engine work, resort-scoped.

**Temporary RBAC bypass (development phase only):** `RBAC_ENFORCEMENT_ENABLED`
defaults to `false` — every authenticated, tenant-verified user has full
admin access while this build-out is underway. Tenant isolation is not
affected. See rules.md §4 and product_decisions.md. Must be flipped back to
`true` before this reaches real guests.

---

# Phase 2 — Database & Customer360

Status: **Implemented and verified** (2026-07-16) — schema, RLS, and
service logic tested end-to-end against the real Supabase project (raw SQL
verification + a scripted smoke test exercising the full customer →
conversation → message → dialogue-state → close lifecycle, with surgical
cleanup). Not yet exercised through the dashboard UI (no inbox frontend
yet — deliberately out of scope, see below) or through `pytest` directly
against this project (the test suite's teardown does `DROP TABLE`, which
would be destructive against a real project — see product_decisions.md;
the same tests run for real in CI against a disposable Postgres).

Actually built (broader than the original bullet list, per the detailed
Phase 2 brief that superseded it — see product_decisions.md):

- [x] Customer 360 foundation — customers, customer_contacts (unified
  phone/email/WhatsApp identity resolution), customer_notes, customer_tags
- [x] Conversations — channel-neutral, with independent lifecycle `status`
  and dialogue `current_state`
- [x] Messages — channel-neutral, with idempotent send and delivery/read
  tracking
- [x] Conversation state engine — reusable, audited (conversation_state_events)
- [x] Unified inbox backend APIs — list/get/search/filter/paginate
  conversations, assign, change status, change dialogue state, send
  message, mark read
- [x] RLS on every new table
- [x] RBAC permissions extended (customers.*, conversations.*) — same
  temporary bypass as Phase 1 applies

Deliverable:
Unified customer + conversation memory shared across all channels — the
foundation every future channel adapter (WhatsApp, web widget) and the AI
Orchestration Engine build on, without any of them existing yet.

Known Phase 2 tech debt (tracked, not silent):

- No dashboard inbox UI yet (deliberately out of scope — spec called for
  backend APIs only, "basic testing" not a UI).
- Attachments are metadata-only; no upload endpoint until Phase 3 wires
  Supabase Storage for the Knowledge Intelligence Engine.
- `/customers/{id}/summary`, `/history`, `/timeline` are not implemented —
  they need the AI Orchestration Engine (Phase 4) and bookings (Phase 7)
  respectively to have real data to summarize/aggregate.
- No hard-delete endpoint for customers yet — pairs with the data-retention
  policy work in rules.md §19, not built standalone.

---

# Phase 3 — Knowledge Intelligence Engine (KIE)

Build

- Document upload
- Website ingestion
- OCR
- Chunking
- Metadata extraction
- Embeddings
- Hybrid retrieval
- Knowledge dashboard
- Versioning
- Search analytics

Deliverable:
Businesses upload knowledge once; chat and calls share it.

---

# Phase 4 — AI Orchestration

Build

- Prompt builder
- Context assembly
- Tool routing
- Model fallback
- Response validation
- Confidence scoring

Deliverable:
Central AI brain for every interaction.

---

# Phase 5 — Web Chat

Build

- Website widget
- Realtime messaging
- Conversation management
- Human handoff
- Customer360 integration
- KIE integration

Deliverable:
Production-ready website chat.

---

# Phase 6 — WhatsApp

Build

- WhatsApp Cloud API
- Templates
- Webhooks
- Media support
- Realtime inbox
- Human takeover

Deliverable:
Unified omnichannel messaging.

---

# Phase 7 — Business Action Engine

Build

- Bookings
- Orders
- Leads
- Calendar
- CRM sync
- Notifications
- Payment integration

Deliverable:
AI can perform validated business actions.

---

# Phase 8 — Analytics Engine

Build

- Business analytics
- Customer analytics
- AI analytics
- Cost tracking
- Usage reports
- Knowledge analytics

Deliverable:
Operational insights for every tenant.

---

# Phase 9 — AI Voice Receptionist

Build

- LiveKit Agents
- Twilio (Global)
- Vobiz (India)
- Deepgram
- ElevenLabs / Sarvam
- Call recording
- Call transcripts
- Customer360 integration
- Shared KIE

Deliverable:
Voice receptionist using the same backend as chat.

---

# Phase 10 — Enterprise

Build

- White-label SaaS
- Teams & permissions
- Advanced branding
- Multi-language
- Enterprise security
- SSO
- API keys
- Billing improvements

Deliverable:
Enterprise-ready platform.

---

# Future Expansion

Channels

- Instagram
- Facebook Messenger
- Telegram
- Email

Capabilities

- Outbound AI calling
- Campaign automation
- CRM integrations
- ERP integrations
- Marketplace integrations
- Advanced workflows

---

# Success Criteria

Technical

- Secure
- Multi-tenant
- Scalable
- Observable
- Maintainable

Business

- Personalized conversations
- Accurate knowledge retrieval
- Low human intervention
- Reliable business actions
- Excellent customer experience

---

# Roadmap Rule

A phase is complete only when:

- Features are implemented
- Tests pass
- Documentation is updated
- Security review is complete
- Monitoring is enabled
- Deployment is production ready
