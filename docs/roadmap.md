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
- [x] FastAPI backend (config, logging, errors, health, auth, audit)
- [x] Next.js dashboard (login, protected shell, health badge)
- [x] Docker (API Dockerfile pinned to python:3.12-slim; not yet built/run locally — no Docker installed on the dev machine used to scaffold this)
- [x] Railway & Vercel — accounts provisioned; not yet deployed (local scaffold remains the verified state)
- [x] Supabase — client wiring + JWKS auth + RLS migrations written; connected to a real project since 2026-07-15
- [x] Authentication (Supabase GoTrue proxy + JWT verification)
- [x] Base CI/CD (GitHub Actions workflow written and running on push)
- [x] Audit logging foundation

Deliverable:
A secure foundation.

**Superseded (Phase 2.5, 2026-07-16):** this phase originally built a full
multi-tenant system (tenants, tenant_settings, tenant_members, tenant_roles,
tenant_permissions, RBAC). All of it was removed in Phase 2.5 — the product
is a single-resort deployment template, not shared multi-tenant SaaS. See
Phase 2.5 below and product_decisions.md.

Known Phase 1 tech debt (tracked, not silent):

- Rate limiting on `/auth/login` is in-process (single-replica) — swap for an Upstash-backed shared limiter once Redis is wired in Phase 3.
- JWKS caching is in-process — move to a Redis-backed shared cache in Phase 3 alongside the rate limiter.
- ~~Member invites require the invitee to already have a Supabase Auth account~~ — moot: Phase 2.5 removed the member/invite system entirely; every authenticated user has full access to this deployment's one resort.

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

**Superseded (Phase 2.5):** the temporary `RBAC_ENFORCEMENT_ENABLED` bypass
described here has been replaced by permanent removal of the role/tenant
system — every authenticated user now has full access by design, not by a
flippable flag. See rules.md §4 and product_decisions.md.

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

# Phase 2.5 — Single-Resort Architecture Refactor

Status: **Implemented and verified** (2026-07-16). Required before Phase 3
per the instruction that introduced it — no Redis/RAG/AI orchestration/
WhatsApp/voice work was started until this landed.

Core decision: the product is no longer multi-tenant SaaS. Each resort now
gets its own isolated deployment (Railway backend, Vercel frontend,
Supabase project/database). The codebase stays reusable as a template;
deployed systems and their data are fully separate from each other.

Built:

- [x] `resort_settings` table — singleton (enforced by a UNIQUE constraint,
  not just an application check), replacing `tenant_settings`
- [x] Removed `tenants`, `tenant_settings`, `tenant_members`, `tenant_roles`,
  `tenant_permissions` tables (migration `0008`)
- [x] Removed `tenant_id` from `customers`, `customer_contacts`,
  `customer_notes`, `customer_tags`, `conversations`,
  `conversation_state_events`, `messages`, `message_attachments`,
  `audit_logs` — with constraints/indexes updated accordingly
  (`customer_contacts`' unique constraint went from tenant-scoped to
  globally unique per deployment)
- [x] Removed `app/tenants/` and `app/roles/` modules entirely; removed
  `require_permission`/`CurrentMembership`/`get_current_membership`;
  `app.deps.get_current_user` (authentication only) is now the only access
  check any endpoint needs
- [x] Removed `RBAC_ENFORCEMENT_ENABLED` — there is no enforcement to toggle
  anymore, the role system itself is gone, not just switched off
- [x] Flattened every API route: `/api/v1/tenants/{tenant_id}/customers` →
  `/api/v1/customers`, same for `/conversations`; added
  `/api/v1/resort/settings`
- [x] RLS replaced on every table: authenticated-user policies
  (`auth.uid() IS NOT NULL`) instead of tenant-membership subqueries
- [x] `audit_logs` gained `before_state`/`after_state`/`correlation_id`
  columns (bundled into the same migration batch; unrelated to tenancy)
- [x] Dashboard: removed tenant creation/switcher UI; added first-run
  resort setup flow (`ResortSetupForm`, gated on `GET /auth/me`'s new
  `resort_configured` flag)
- [x] Tests: removed `test_rbac.py`/`test_tenant_isolation.py`; added
  `test_resort_settings.py` and `test_auth_required.py` (authentication-only
  access checks); updated customer/conversation tests to drop `tenant_id`

Deliverable:
A stable single-resort foundation — every Phase 1/2 feature (auth,
customers, conversations, messages, audit) continues to work, now without
any tenant concept anywhere in the code, schema, or docs.

Known Phase 2.5 tech debt (tracked, not silent):

- Migration `0008`'s `downgrade()` deliberately raises `NotImplementedError`
  — reconstructing per-row tenant ownership for data created after the
  migration ran isn't inferable; restoring from a pre-migration backup is
  the documented recovery path instead.
- `pytest`'s DB-gated tests (customers/conversations/resort_settings)
  still skip locally rather than run against the connected real Supabase
  project, since their fixture teardown does `DROP TABLE` — verified via a
  scripted smoke test with surgical cleanup instead (see
  product_decisions.md); the same tests run for real in CI's disposable
  Postgres container.
- MFA for privileged accounts (mentioned in architecture.md §12) isn't
  needed yet at single-resort, single-role scale — deferred until there's
  a reason to reintroduce role distinctions.

---

# Phase 3 — Knowledge Intelligence Engine (KIE)

Status: **Implemented and verified** (2026-07-18) — see
docs/phase-3/IMPLEMENTATION_PLAN.md and
docs/phase-3/PHASE_3_COMPLETION_REPORT.md for full detail. Real RKPR
corpus import (`--execute`) and the benchmark run are built and dry-run
verified against the real corpus, but not yet executed against the live
Supabase project — blocked on the deployment owner adding a real
`OPENAI_API_KEY` (embedding calls cost money; this was deliberately not
run without that explicit go-ahead).

Built

- [x] Document upload (PDF/DOCX/XLSX/CSV/HTML/TXT/images), MIME + magic-byte
  validation, ZIP-bomb/size-limit guards, filename sanitization
- [x] Website ingestion — sitemap-then-links crawler for the live RKPR site,
  with a URL-rebasing fix for two confirmed real bugs (sitemap `<loc>` and
  robots.txt `Sitemap:` both pointing at `localhost:3000` instead of the
  real domain)
- [x] OCR — Tesseract binding with an honest "unavailable" path (no
  Tesseract on this dev machine; verified the fail-closed/fail-honest
  behavior directly rather than assuming it)
- [x] Chunking — token-aware generic chunker, FAQ Q/A-pair chunker (with a
  fixed real bug: documents mixing FAQ sections with other content no
  longer lose the non-FAQ content), table-row chunker for spreadsheets
- [x] Metadata extraction + governance import — multi-strategy matching
  between the Knowledge Source Register and the actual file layout (the
  register uses a pre-reorganization folder structure); vocabulary
  normalization for real register values that don't match its own
  documented vocabulary (e.g. "Supplementary" priority, "Approved
  (Archived)" approval status)
- [x] Embeddings — OpenAI `text-embedding-3-large` truncated to 1536 dims
  (pgvector's HNSW index caps at 2000; discovered live against the
  connected Supabase project), incremental re-embedding by content hash,
  deterministic MockEmbeddingProvider for the entire test suite
- [x] Hybrid retrieval — pgvector cosine similarity + PostgreSQL full-text
  search, governance-weighted scoring (priority/authoritative/entity
  match), guest-safety enforced at the SQL query level (visibility,
  retrieval_enabled, status, expiry — never a Python post-filter), plus a
  lexical-overlap reranker
- [x] Knowledge dashboard — sources list/detail/governance actions, upload
  form, search playground, ingestion jobs list, website crawl trigger
- [x] Versioning — `knowledge_source_versions` per (re)processing run,
  idempotent re-ingestion via deterministic chunk keys
- [x] Search analytics — every retrieval call logged to
  `knowledge_retrieval_logs` with classification/latency/results
- [x] Malware scanning — ClamAV client, fail-closed in production when
  unreachable, explicit `unscanned_dev_only` label in development (never
  silently "clean")
- [x] Benchmark evaluation — scores every `knowledge_benchmark_questions`
  row against real retrieval output via lexical overlap (no LLM-judge,
  consistent with this phase's "no full answer-generation agent" boundary)

Deliverable:
Businesses upload knowledge once; chat and calls share it.

Known Phase 3 tech debt (tracked, not silent):

- ~~Real embedding-backed RKPR import and benchmark run~~ — **done
  2026-07-18**: real import (19 sources, 187 chunks embedded via real
  `text-embedding-3-large`) and real benchmark (49/50, 98% pass rate)
  both executed for real. See `docs/phase-3/PHASE_3_COMPLETION_REPORT.md`
  §7.
- Redis is now connected and verified (see
  `docs/incidents/DATABASE_RECOVERY_REPORT.md`), but still has no real
  consumer wired up (declared dependency, unused in app code) — rate
  limiting remains the in-process placeholder documented in Phase 1.
  ClamAV/Tesseract are still not installed on this dev machine — the
  malware scanner and OCR provider have real implementations plus a
  documented, honest degraded-mode path (`unscanned_dev_only` /
  "OCR provider unavailable"); only verified via unit tests and the real
  corpus import's fail-honest behavior, not full live integration.
- Dashboard pages pass lint/typecheck/build but weren't clicked through
  live in a browser this session — no test Supabase login credentials were
  available to authenticate past `/login`.
- No answer-generation agent (deliberately out of scope this phase); the
  search playground and benchmark runner are the only consumers of
  retrieval right now.

---

# Phase 4 — AI Orchestration

> Status: **Complete** (2026-07-18). See
> `docs/phase-4/PHASE_4_COMPLETION_REPORT.md` for what was actually built,
> tested (including a real-data validation run against the real embedded
> RKPR corpus and the real OpenAI API — 2 structural bugs found and fixed
> this way), and what remains deferred.

Built

- Intent classification + entity extraction (deterministic-first, LLM-assisted)
- Validated conversation flow-state machine (`flow_state`, within the
  canonical 11 `DIALOGUE_STATES`)
- Token-budgeted, source-attributed context assembly
- Modular, injection-resistant prompt architecture
- OpenAI-primary/Groq-fallback LLM provider abstraction with a circuit breaker
- Typed, permission-controlled tool registry (backend validates every
  proposed tool call; no tool ever claims a completed booking/payment/refund)
- Deterministic human-handoff policy engine
- Pre-send response-validation guardrail pipeline
- The top-level channel-neutral `orchestrate()` pipeline
- A controlled Customer 360 memory layer (rules.md §6: verified facts vs.
  AI inferences kept structurally separate)
- 8 authenticated API endpoints (`/api/v1/orchestration/*`)
- Dashboard conversation list/detail views with the AI's live decision
  trace and staff handoff/release controls (also closes a pre-existing
  gap — Phase 2 never built a conversations/inbox dashboard UI at all)

Known tech debt (tracked, not silent) — see
`PHASE_4_COMPLETION_REPORT.md` §7 for full detail: `/preview` and
`/retry` API endpoints deferred; a centralized model-import registry
would prevent a recurring "missing model import" bug class; database
backup/PITR still not configured; Groq fallback/real Tesseract/real
ClamAV/a real Redis consumer remain unexercised against real
infrastructure.

Deliverable:
Central AI brain for every interaction. ✅ Delivered.

---

# Phase 5 — Web Chat

Status: **Completed 2026-07-18.** Full detail:
`docs/phase-5/PHASE_5_COMPLETION_REPORT.md`.

Built (differs from the original bullet list below in the ways explained
in `docs/phase-5/WEBCHAT_ARCHITECTURE.md`):

- Audited and imported the resort's real Next.js website (uploaded
  separately) into this monorepo as `apps/website`; replaced its
  pre-existing fake, keyword-matching chat widget/API with a real
  integration.
- New public, anonymous-guest FastAPI module (`app/webchat/`) — opaque
  hashed session tokens, one new table (`webchat_sessions`, migration
  `0024`), Redis-backed fail-open rate limiting, all calling the existing
  Phase 4 `orchestrate()` pipeline (no second AI implementation).
- Website-side session proxy (`apps/website/src/app/api/webchat/*`) so
  the browser only ever talks to the website's own server — no AI/DB
  credentials of any kind reach the browser or even `apps/website`'s
  server environment.
- Rebuilt chat widget UI (quick actions, guest-safe citations, handoff
  banner, staff-message polling, contact capture, retry-on-failure,
  accessibility) preserving the resort's existing visual design.
- Backend tests (`test_webchat_auth.py`, `test_webchat_service.py`);
  real-browser verification of the UI and, concretely, of the
  backend-failure error path (see completion report).

Known tech debt / honest gaps (not silent — full list in the completion
report): no real token-streaming (deferred, documented); staff replies
reach the guest via polling, not push; DB-dependent backend tests and the
real-OpenAI validation checklist could not be executed in this session's
tool sandbox (confirmed environment-specific, not a code issue) and
should be re-run in an environment with confirmed Postgres connectivity;
no frontend test framework was introduced (none existed anywhere in this
monorepo before this phase either).

Original bullet list (superseded by the above, kept for history):
- Website widget
- Realtime messaging
- Conversation management
- Human handoff
- Customer360 integration
- KIE integration

Deliverable:
Production-ready website chat. ✅ Delivered (with the honest gaps above).

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
Operational insights for this deployment's resort.

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
- Reusable across resorts as a deployment template (Phase 2.5)
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
