# product_decisions.md

> Status: Living log of significant architectural/tooling decisions and why they were made.
> Append new entries at the top; never delete history, only supersede it.

---

## 2026-07-19 — Post-launch chat tuning: latency, cost, persona, pacing

Real guest usage after Phase 5 shipped surfaced three practical problems:
30-45s reply latency, ~$0.05-0.06 per message (4-5 messages costing
$0.20-0.30), and a chat experience that read as an obvious, verbose bot
rather than a resort receptionist. Fixes, in order of impact:

**Model choice is an operator setting, not a code fix.** The deployment's
`OPENAI_MODEL` was set to `gpt-5` — a reasoning-tier model, both slower
and far more expensive per token than needed for grounded FAQ-style
answers. `Settings.openai_model`'s own Python default was already
`gpt-4o-mini`; `.env.example` had drifted to suggest `gpt-5` and was
corrected back. This is the single biggest lever for both latency and
cost, and it lives in Railway's environment variables, not in this
repository — flagged clearly to the user rather than something a code
change alone could fix.

**Response length was uncapped.** No `max_tokens`/`max_completion_tokens`
was ever passed to any LLM call — nothing stopped a verbose model from
generating an arbitrarily long reply, which costs more (completion
tokens, not input tokens, dominate spend) and takes longer to generate.
Added `orchestration_max_response_tokens` (default 220) to `Settings`,
threaded through `LLMProvider.complete()`'s signature (`base.py`,
`openai_provider.py` — as `max_completion_tokens`, the parameter
reasoning-tier models require and non-reasoning models also accept —
`groq_provider.py`, `fallback.py`, `mock_provider.py`), applied to the
main generation and its tool-result follow-up call in `pipeline.py`. Also
capped intent classification (100) and entity extraction (200) — already
short JSON, but worth bounding as well.

**Intent classification and entity extraction ran sequentially despite
being fully independent** (`pipeline.py` called `classify_intent()` then
`extract_entities()`, neither depending on the other's result) — the
single largest avoidable fixed latency cost in the whole turn. Changed to
`asyncio.gather()`, cutting one full sequential LLM round trip off every
turn for free.

**Entity extraction always called the LLM when a provider was supplied**
(a deliberate Phase 4 design, documented then as intentional), even for
small talk ("Hi", "thanks") that can never contain a semantic entity
(room category, dietary restriction, etc.). Added a skip via the
already-existing `is_small_talk()` check — a narrow, safe reduction in
call volume, not a change to the confidence-gate policy for genuine
requests.

**Persona and brevity are prompt content, not framework behavior.**
`identity_block()` (`prompts/templates.py`) previously opened with "You
are the AI receptionist" — guests don't want to be constantly reminded
they're talking to software. Rewritten so the model presents as "Aranya,
a front-desk receptionist" and never volunteers "AI"/"bot" language
unprompted — **with one deliberate, non-negotiable exception**: if a
guest directly and explicitly asks whether they're speaking with a person
or a computer, the model must answer honestly (briefly, without dwelling
on it) rather than claim to be human. This is a hard line, not a style
preference — see `docs/rules.md` and general responsible-AI/consumer-
disclosure norms; pretending to be human on direct, explicit questioning
would be deceptive regardless of what makes the product feel more
polished. `channel_block()` was also rewritten to mandate 2-4 sentence
replies ("the way a real front-desk chat message reads"), not just
"concise" (too weak — the model was still writing paragraphs).

**Realistic pacing is a frontend concern, not a backend one.** Guests
expect a short pause before any "typing…" indicator, then a WhatsApp-style
animated-dots bubble, then the reply — not an instant wall of text.
Implemented client-side in `ChatWidget.tsx`: a 1200ms delay before the
typing indicator appears at all, and a 1800ms floor on total time before
the reply is revealed (only on the success path — a failure surfaces
immediately, no reason to fake a delay on bad news). The UI label was
also softened from "AI Concierge · Online" to "Front Desk · Online",
consistent with the prompt-side persona change above.

---

## 2026-07-18 — Phase 5: Website Chat Channel — key decisions

**Where the uploaded website codebase landed.** The resort's real website
(`RKPR-WEBSITE-main.zip`, uploaded separately, no `.git` history — a
GitHub branch export) was imported into this monorepo as a new npm
workspace, `apps/website`, rather than kept as a standalone repo. It
needed to share this platform's env-var conventions, CI, and deployment
story, and Phase 5's own audit (`docs/phase-5/WEBSITE_CODEBASE_AUDIT.md`)
found nothing that argued for keeping it separate. The pre-existing empty
`apps/widget` placeholder (reserved since Phase 1 for a future
*embeddable* third-party widget) was left untouched — different concept
from a resort's own full site.

**The existing chat widget was fake and was replaced, not extended.** The
uploaded site already had a polished, on-brand `ChatWidget.tsx`
("Aranya"), but it posted to a Next.js route that was ~170 lines of
keyword-matching fabricating specific room rates, spa prices, and canned
escalation messages — zero connection to any LLM, database, or the real
Phase 4 pipeline. This directly violated `docs/CLAUDE.md`'s "never invent
prices/policies" rule. The widget's JSX/animation/visual identity was
reused; its entire data layer was rebuilt from scratch against the real
`app.orchestration.pipeline.orchestrate()`.

**Browser never talks to FastAPI directly.** `apps/website`'s own Next.js
server proxies every webchat call server-to-server
(`apps/website/src/lib/server-webchat.ts` → FastAPI's
`/api/v1/webchat/*`) — the same shape `apps/dashboard` already uses for
its own staff-facing calls. This means `apps/website` never holds any
AI/database credential, and the guest's session token lives only in an
`HttpOnly` cookie the Next.js server manages, never in browser-readable
storage. Full rationale: `docs/phase-5/WEBCHAT_ARCHITECTURE.md`.

**Reused `"webchat"` as the channel value, not `"website_chat"`** (the
brief's suggested name) — `app.conversations.constants.CHANNELS` already
had `"webchat"` from Phase 4's `ProcessMessageRequest.channel` default.
Reusing an existing valid value avoided a needless migration.

**One new table, not a redesign.** `webchat_sessions` (migration `0024`)
maps a SHA-256 token hash to `(customer_id, conversation_id)` — the same
"never store the raw secret" principle as a password hash. No changes
were needed to `customers`/`conversations`/`messages`: an anonymous guest
is already fully representable as a `Customer` with zero contacts plus a
`Conversation` where `channel="webchat"` (Phase 2 schema, unchanged).

**Guest-initiated handoff reuses staff-handoff primitives, not a second
implementation.** The "Speak to staff" quick action calls a dedicated
`POST /handoff` endpoint that invokes the exact same
`flow_engine.apply_handoff` + `conversations_service` state-transition
calls the staff-facing forced-handoff endpoint already uses — only
`changed_by="system"` differs (a guest is neither `"ai"` nor `"human"`
staff in `STATE_CHANGED_BY`'s existing vocabulary).

**Streaming deferred, not faked.** `orchestrate()` has no token-level
streaming path, and retrofitting one would touch a pipeline just
hardened and real-data-validated in Phase 4. Per the brief's own
instruction against fragile fake-streaming shims, the widget shows a
clean typing indicator and renders one complete response — a documented
deferral, not a workaround.

**Staff replies reach the guest via polling, not push.** There's no
websocket/SSE transport in this stack yet. While the widget is open it
polls the transcript every 10s and appends new non-guest messages — an
explicit, temporary stand-in for real-time delivery, not a permanent
design choice.

**Pre-existing lint debt in the uploaded website was fixed, not left.**
`npm run website:lint` surfaced 33 pre-existing errors/57 warnings
(unescaped JSX apostrophes, unused imports, one `no-explicit-any`, one
`react-hooks/set-state-in-effect`) across ~20 files unrelated to the chat
work. These were fixed as a small, mechanical, non-visual cleanup
(escaping characters, removing dead imports, converting one effect-based
state seed into a `useState` initializer) so the new `website` CI job
would be meaningful — explicitly not a redesign, and independently
re-verified (lint + build both clean) rather than taken on faith.

**DB connectivity limitation in this session's tool sandbox.** Raw
Postgres TCP connections to the project's Supabase pooler failed
throughout this phase's work (`WinError 1225`), identically on the
pre-existing, previously-passing Phase 3/4 pytest suite — confirmed
environment-specific (a direct `Test-NetConnection` probe succeeded at
the TCP layer; only the actual Postgres wire-protocol connection failed),
not a regression introduced here. This blocked running the new
DB-dependent webchat tests and the real-OpenAI validation checklist in
this session. Real-browser verification did confirm the backend starts
correctly, reaches Supabase's HTTPS API successfully, and — when the
in-process database call then fails — returns a safe, generic,
non-technical error to the guest rather than any stack trace or SQL
detail, a genuine (if partial) live confirmation of the error-handling
design. Full detail: `docs/phase-5/WEBCHAT_TEST_PLAN.md` and
`docs/phase-5/PHASE_5_COMPLETION_REPORT.md`.

---

## 2026-07-18 — Phase 4: AI Orchestration — key decisions and a real incident

**Database-destruction incident and the permanent fix.** Mid-phase, a test
fixture's `Base.metadata.create_all`/`drop_all` ran directly against the
live Supabase project's `public` schema (the same database real
development data lives in — there was no separate test project), combined
with an orphaned background test process that went undetected due to a
PID-translation mismatch between Git Bash's `ps` output and Windows
`taskkill`. Result: every application table was dropped, with no backup to
recover from. Full incident record, forensics, and recovery proof in
`docs/incidents/`. **Permanent fix**: `tests/conftest.py`'s `db_engine`
fixture now runs every test inside a dedicated, randomly-named schema
(`test_<uuid4>`, regenerated fresh per pytest invocation) via SQLAlchemy's
`schema_translate_map` — structurally incapable of reaching `public`
regardless of what else is running concurrently against the same
database. Proven, not just asserted: `tests/test_database_safety.py`
empirically writes a row through the sandbox and independently confirms
(via a second, untranslated connection) that it never lands in `public`.
This is the single most important lesson from this session: **destructive
DDL from any test/dev tooling must be structurally incapable of reaching
shared/production data**, not just "be careful" — the incident happened
despite considerable existing care, because the isolation boundary itself
didn't exist yet.

**Customer 360 memory: a namespaced sub-key, not a new table.** rules.md
§6 requires verified facts, AI inferences, and AI summaries to be stored
and read back separately, with an AI inference never overwriting verified
data. Rather than a new table, AI-inferred guest preferences are written
into `customers.resort_preferences["ai_inferred"]` — a namespaced sub-key
kept structurally apart from anything a staff member enters directly (that
stays in the top-level `resort_preferences` keys, `customer.full_name`,
`preferred_language`, and `CustomerNote` rows, none of which
`app.orchestration.memory.record_inferences` ever touches). Only a fixed,
curated vocabulary of durable, transferable-across-conversations
preferences is ever written this way (dietary restrictions, allergies,
view preference, room category, accessibility needs, meal plan, language,
guest name) — deliberately **not** the full `ENTITY_FIELDS` vocabulary,
since stay-specific transactional details (check-in dates, num_nights,
booking references) would be actively wrong if "remembered" into some
future, unrelated stay.

**The OpenAI tool-calling round-trip needs the real `tool_calls`/
`tool_call_id` correlation — mocks don't enforce this.** `LLMMessage` and
`LLMToolCall` originally only carried `role`/`content` and
`tool_name`/`arguments`. Every mock-based test passed, because
`MockLLMProvider` doesn't validate OpenAI's actual message-format
contract. Against the real API, replaying an assistant's tool proposal
back as a plain-text message (instead of its real `tool_calls[]`
structure) and following it with a `role: "tool"` message with no
`tool_call_id` is rejected outright: "messages with role 'tool' must be a
response to a preceeding message with 'tool_calls'." This broke 3 of the
first 13 messages in the real-data validation checklist run (room
comparison, cancellation policy, a hallucination probe) — all silently
falling back to a generic "I ran into an issue" response instead of
answering. Fixed by adding `call_id` to `LLMToolCall` and
`tool_calls`/`tool_call_id` to `LLMMessage`, threading the real id through
both providers via a shared `to_openai_wire_format()` helper. **Lesson**:
a mock that doesn't enforce a real API's actual protocol constraints can
hide structural bugs indefinitely — the real-data validation checklist
(run against real embeddings + a real LLM, at a small, explicitly-approved
cost) is what caught this, not any amount of additional mock-based test
writing would have.

---

## 2026-07-18 — Phase 3: Knowledge Intelligence Engine — key decisions and real bugs found

**Embedding dimensions: 3072 → 1536.** `text-embedding-3-large`'s native
output is 3072 dimensions, but pgvector's HNSW index has a hard 2000-
dimension cap regardless of pgvector version — discovered when migration
`0013` failed against the live, connected Supabase project ("column
cannot have more than 2000 dimensions for hnsw index"), not from reading
pgvector's docs in advance. Fixed by using OpenAI's `dimensions` parameter
to truncate via Matryoshka representation learning to 1536 — the same
technique `text-embedding-3-small` uses natively, keeping most of
`-3-large`'s quality edge while fitting the index. Every embedding call
passes `dimensions=1536` explicitly (`app/knowledge/embeddings.py`), not
just the column width.

**Governance importer: the ingestion manifest, not the register, is the
primary driver.** Initial design assumed `Knowledge_Source_Register.xlsx`
would drive what gets ingested, with the manifest as secondary
confirmation. Inspecting both files directly showed the manifest
(`00_CONTROL/PHASE3_INGESTION_MANIFEST.csv`) has an explicit,
unambiguous `ingest_status`/`target_index` for every one of the 90 files
in the package — including ~66 files the register never mentions at all
(media images, control docs, templates) — while the register only
describes 24 rows and 3 of those don't correspond to any single ingestible
file (an aggregate photo-library entry, an archived scanned card, a
tracking-only row). Flipped the design: manifest classifies every file
first; the register enriches a manifest row when a match is found (by
normalized basename, since register paths use the pre-reorganization
folder layout), but a manifest row with no register match still gets a
safe, correct classification on its own.

**Governance vocabulary doesn't match its own documented vocabulary.**
The register's "Lists" tab defines Source Priority as
{Critical, High, Normal, Low}, but real rows (SRC-018/019/020) use
"Supplementary", which isn't in that list at all. Similarly Processing
Status real values include "N/A" and "Archived - Historical Reference
Only", neither in the Lists tab's own vocabulary. `app/knowledge/
governance/mapping.py` maps every value actually observed in the live
file (not just what the vocabulary tab claims exists) and flags anything
genuinely new in the reconciliation report rather than guessing.

**Website crawler: two confirmed live bugs on the resort's own site.**
Curl'd the real site before writing any crawler code:
`robots.txt`'s `Sitemap:` line and every `<loc>` in `sitemap.xml` both
point at `http://localhost:3000` instead of the real Vercel domain — a
deployment misconfiguration on the resort's side, not a hypothetical.
The crawler (`app/knowledge/website/crawler.py`) treats the seed config's
`base_url` as ground truth and rebases every discovered URL onto it,
using only the path/query from the sitemap's `<loc>`. Verified against
the real live site: 49 URLs discovered, 40 fetched successfully, 9
genuine 404s (sitemap entries pointing at pages that don't exist on the
live deployment — also a real bug on their side, not the crawler's).

**Chunking bug found and fixed: mixed-content documents.** The FAQ
chunker's initial design classified a whole document as "FAQ" or "not
FAQ" based on whether it contained 3+ `Q:` lines anywhere. Tested against
the real `RKPR_Resort_Restaurant_Menu_Full_2026.pdf`, which has a 5-
question FAQ appendix after 7 pages of actual menu/pricing content — the
whole document collapsed into 5 FAQ-only chunks, silently discarding all
the menu content. Fixed by extracting FAQ pairs from wherever they occur
and chunking the remaining non-FAQ text separately (`app/knowledge/
chunking/strategies.py::chunk_source`), with a regression test pinned to
this exact scenario.

**Malware/OCR: fail-closed and fail-honest, not silently permissive.**
Neither ClamAV nor Tesseract is installed on this dev machine (confirmed
via direct checks, not assumed). Both providers report a real
`unavailable` state rather than pretending success:
`malware_scan_status` is stamped `unscanned_dev_only` in development
(never `clean`) and blocks activation outright in production unless
explicitly overridden; OCR failure sets `processing_status=failed` with a
real error message. Verified both behaviors by actually running them
against real files in this environment, not just reading the code.

**RKPR import blocked on user-supplied `OPENAI_API_KEY`, by design.**
The CLI script (`app.scripts.import_rkpr_knowledge`) is built and
`--dry-run` verified against the real corpus (19 sources, 50 media, 21
skipped, matching the manual audit exactly). `--execute` was not run
autonomously: it calls the real OpenAI embeddings API (real, if small,
cost — estimated well under $0.10 for this corpus) and writes to the
live, connected Supabase project. Per this project's safety rules around
spending real money and touching shared/production infrastructure, this
required an explicit user go-ahead — asked before proceeding; `.env` has
no `OPENAI_API_KEY` configured yet, so the real import and benchmark run
are pending that.

---

## 2026-07-16 — Phase 2.5: single-resort architecture refactor (removed multi-tenancy)

**Context:** The business model changed — instead of one shared application
serving multiple resorts, every resort now gets its own fully isolated
deployment (own Supabase project/database, own Railway backend, own Vercel
frontend). The entire multi-tenant system built in Phase 1 (and extended in
Phase 2) became unnecessary and was ordered removed before Phase 3 begins.

**Pre-migration data check (why this was low-risk):** before writing any
migration, queried the live database directly: 1 tenant, 1 tenant_member, 1
user, 0 customers/conversations/messages, 8 audit_log rows. There was
essentially nothing to lose or reconcile — this shaped the decision to do a
clean, irreversible-by-design migration rather than build elaborate data-
preservation machinery for data that didn't exist.

### Migration structure: 3 new migrations, none of the old ones touched

`0007` (create `resort_settings`), `0008` (drop all tenant-referencing RLS
policies, then `tenant_id` columns/constraints/indexes from every business
table, then the tenant system tables themselves), `0009` (new
authenticated-only RLS policies). Migrations `0001`-`0006` were left
completely untouched — editing an already-applied migration's DDL would
desync anyone re-running the chain on a fresh database from what actually
ran against the live one. This does mean a fresh database briefly builds
the tenant system before Phase 2.5 tears it down again — accepted as a
harmless one-time cost of keeping migration history honest, not something
worth rewriting history to avoid.

**Real bug caught mid-migration:** the first attempt at migration `0008`
failed with `DependentObjectsStillExist` trying to `DROP TABLE
tenant_members` — policies on `tenants`/`tenant_settings`/`tenant_roles`
referenced `tenant_members` in their `USING` clause (the shared membership
subquery from migration `0002`) even though they weren't defined on
`tenant_members` itself. Postgres tracks that as a real dependency. Fixed
by dropping every policy that referenced the tenant system — including
ones defined on tables that were about to be dropped anyway — before
dropping any table. Alembic's transactional DDL meant the failed attempt
rolled back cleanly with zero side effects; this is exactly why we don't
skip transactional safety for "just a migration."

### `resort_settings` singleton enforced at the database level

A `singleton boolean NOT NULL DEFAULT true` column under a `UNIQUE`
constraint plus `CHECK (singleton = true)` guarantees at most one row can
ever exist — not just an application-layer check before insert (which is
also there, for a clean error message, but the DB constraint is the real
guarantee). This is the standard "singleton table" Postgres pattern.

### RLS: authenticated-only, not "no RLS"

Replaced every tenant-membership-subquery policy with `auth.uid() IS NOT
NULL` — RLS stays as defense-in-depth for any future direct-Postgres access
path (Realtime, future connectors), it just no longer needs to answer "which
tenant" since there's only ever one resort's data per database.
`audit_logs` keeps its no-INSERT-policy pattern from Phase 1 (readable by
authenticated users, writable only by the backend's service_role
connection, which bypasses RLS).

### `audit_logs` gained `before_state`/`after_state`/`correlation_id`

Not part of removing tenant_id, but bundled into migration `0008` since the
table was already being altered. The Phase 2.5 brief listed these as
audit-log requirements; `correlation_id` is populated automatically from
the existing per-request context var (`app.logging.correlation_id_var`) so
no call site needs to pass it manually. `before_state`/`after_state` are
populated at the "update" call sites where the old value was already cheap
to capture (customer update, conversation status/state change,
resort_settings update) — not retrofitted everywhere, since most actions
(create, add tag, add note) don't have a meaningful "before" state.

### Access model: authentication only, not "RBAC bypassed"

Phase 1's temporary `RBAC_ENFORCEMENT_ENABLED` flag is gone, not set to
some new default — the role/permission system it gated doesn't exist
anymore (`app/roles/`, `app/tenants/` deleted; `CurrentMembership`,
`get_current_membership`, `require_permission` removed from `app.deps`).
`app.deps.get_current_user` — authentication only — is now the sole access
check any endpoint depends on. This is a stronger, more final decision than
the Phase 1 bypass: there is no flag left to flip back on. Reintroducing
role distinctions later means deliberately rebuilding them, not toggling a
switch.

### Verification approach: same "surgical live smoke test" pattern as Phase 2

`pytest`'s DB-gated tests (customers/conversations/resort_settings) still
skip locally, for the identical reason as Phase 2: their fixture teardown
calls `Base.metadata.drop_all`, which would destroy the connected live
Supabase project's schema. Verified the actual migration and service-layer
correctness instead via: (1) direct SQL inspection of the resulting schema/
RLS policies, (2) a scripted smoke test creating a resort_settings row +
customer + conversation + message directly against the live database and
confirming the singleton constraint fires correctly, followed by surgical
(non-`drop_all`) cleanup. Both approaches together give real confidence
without risking the connected project.

### Dashboard: resort setup replaces tenant creation

`CreateTenantForm` and the `/api/tenants` proxy route were deleted, not
just hidden. `GET /api/v1/auth/me` now returns `resort_configured: boolean`
instead of a memberships array; the dashboard home page checks that flag
and shows `ResortSetupForm` (posts to a new `/api/v1/resort/settings` proxy
route) until it's true, then a plain welcome view. No tenant-switcher
concept ever existed to remove beyond that.

---

## 2026-07-16 — Phase 2: shared conversation foundation

**Context:** Building the Phase 2 brief (customers, conversations,
messages, conversation state engine, unified inbox APIs) on top of the
verified Phase 1 foundation, against the real Supabase project connected
the same day.

### Two independent conversation states, not one

The Phase 2 brief's `status` enum (open/waiting_for_guest/waiting_for_staff/
ai_handling/human_handling/escalated/closed) and architecture.md's
original AI_ACTIVE/HUMAN_ACTIVE/AI_ASSIST/WAITING_FOR_CUSTOMER/RESOLVED/
BLOCKED vocabulary describe the same conceptual slot on a conversation.
Resolved by adopting the Phase 2 list as `conversations.status` (it's the
more recent, more detailed instruction), retaining `blocked` as an 8th
value since rules.md requires a way to halt automated processing entirely
and nothing in the new brief covers that need, and capturing the old
AI_ASSIST nuance (AI drafts, human sends) via the existing
`ai_active`/`human_active` boolean pair instead of a 9th status value.
Separately, the Phase 2 brief's own "Conversation State Foundation"
section (Greeting → Closed, 11 states) is a genuinely different concept —
dialogue/reasoning state, stored as `conversations.current_state` — and
was reconciled with the near-identical but not-quite-matching list in
functions.md's AI Intelligence Layer by adopting the Phase 2 brief's exact
11-state list as canonical everywhere (functions.md's conversation-state
section and architecture.md §4.4 both updated to match).

### Tenant-scoped URL convention extended, not re-decided

Phase 1 already established `/api/v1/tenants/{tenant_id}/...` with
URL-supplied-but-verified tenant_id for tenant member management. api.md's
original (pre-Phase-1) sketch had flat `/api/v1/customers`,
`/api/v1/conversations` paths with no tenant scoping mechanism at all.
Rather than inventing a second convention, Phase 2 extends the existing
one to customers/conversations/messages — one pattern, one place
(`app.deps.get_current_membership`) where tenant trust is established.

### Customer identity resolution: one contact table, not three

"Multiple phone numbers, emails, WhatsApp identity" could have been three
near-identical tables. Built as one `customer_contacts` table with a
`contact_type` discriminator and a `UNIQUE(tenant_id, contact_type, value)`
constraint instead — this is also exactly the shape identity resolution
needs (`find_customer_by_contact`), and adding a new contact type later
(e.g. an Instagram handle) needs no schema change.

### "Previous stays" / "communication history" are derived, not stored

Both were listed as customer fields in the brief. Neither gets a column:
previous stays will be a query against `bookings` (Phase 7, doesn't exist
yet) and communication history a query against `conversations`/`messages`
(this phase), both filtered by `customer_id`. Storing either as a
duplicated column/table would drift from the source of truth immediately.

### Tests are written but skip locally by design — verified another way

`tests/test_customers.py` and `tests/test_conversations.py` use the same
`db_engine` fixture as Phase 1's `test_tenant_isolation.py`, which calls
`Base.metadata.drop_all` in teardown. Running pytest with `DATABASE_URL`
pointed at the now-connected real Supabase project would **drop every
table in it** — unacceptable. So these tests keep skipping locally (same
as Phase 1) and are meant to run for real in CI's disposable Postgres
service container. To still get real verification before calling Phase 2
done, ran a one-off script exercising the full customer → conversation →
message → dialogue-state-transition → close lifecycle directly against
the real database, then surgically deleted only the rows it created
(no `drop_all`) — confirmed working end-to-end, including cascade
deletes and idempotent message sends.

### RBAC extended, bypass unchanged

Added `customers.view`/`customers.manage`/`conversations.view`/
`conversations.manage` to the permission matrix and seeded them onto the
5 existing system roles via a new migration (`0005`) rather than editing
`0001` (already applied to the real database — migrations must stay
additive). `RBAC_ENFORCEMENT_ENABLED` is still `false`, so these are
declared-but-unenforced for now, same as Phase 1's permissions.

---

## 2026-07-15 — Resort business pivot, functions.md, temporary RBAC bypass, infra defaults

**Context:** Phase 1 verified complete. The user provided `functions.md`
(luxury resort business function catalog + AI Intelligence Layer + RAG
domains + Guest Memory spec) and confirmed GitHub/Railway/Vercel/Supabase
accounts are now provisioned.

### Business domain: Luxury 5-Star Resort is the first real implementation

This is not a demo — the platform's first concrete tenant is a luxury
resort covering rooms, dining, spa, activities, events, concierge,
housekeeping, billing, loyalty, and guest profiles. `docs/functions.md` is
now canonical and referenced from Goal.md, requirements.md, architecture.md,
and CLAUDE.md. The AI reasoning pipeline (architecture.md §4.4) is written
generically so a future non-resort tenant only needs a different
functions.md/knowledge base — not a different platform.

### functions.md is the Business Tool Layer, not the AI's intelligence

Sections 1–27 (`get_resort_information`, `search_rooms`, `create_booking`,
etc.) are deterministic backend tools the Business Action Engine executes.
Sections 28–30 (AI Intelligence Layer, RAG Knowledge Domains, Guest Memory)
describe the reasoning layer that decides *when* to call those tools. The
8-step pipeline (understand intent → extract entities → conversation state
→ RAG retrieval → decide if verification needed → call function → generate
response → update guest memory) is now written into architecture.md §4.4
so this distinction survives independently of any one prompt.

### Temporary RBAC bypass — `RBAC_ENFORCEMENT_ENABLED=false`

To reduce friction while building the AI/RAG/booking layers, every
authenticated tenant member now has full admin access regardless of their
assigned role. Implemented as a single settings flag
(`app.config.Settings.rbac_enforcement_enabled`, default `False`) checked
inside `require_permission()` in `app.roles.permissions` — when it's off,
the dependency returns the membership without querying
`tenant_permissions` at all. Deliberately **not** implemented as removing
or weakening `get_current_membership`: tenant isolation is a release-
blocking invariant (architecture.md §6) and is never touched by this flag.
Flipping `RBAC_ENFORCEMENT_ENABLED` back to `true` re-enables enforcement
with zero code changes elsewhere, since every call site already goes
through `require_permission()`. No dashboard role-based UI hiding exists
yet, so nothing needed to change on the frontend for this.

### Infra defaults confirmed: GitHub, Railway, Vercel, Supabase

These are now the default and only infrastructure to use for version
control, backend/worker hosting, frontend hosting, and database/auth
respectively, unless explicitly told otherwise. No credentials have been
shared in chat (by design — see rules.md §12 Secrets Management); actual
connection still requires the user to supply real values into `.env`
locally, or to run `railway login` / `vercel login` / `gh` auth themselves,
since those are interactive/credentialed flows this assistant should not
perform on the user's behalf.

---

## 2026-07-14 — Phase 1 foundation decisions

**Context:** Repository contained only the 8 spec documents; no code, no git,
no installed tooling beyond Node 24 / npm 11 / Python 3.14 / git.

### JS monorepo tooling: npm workspaces, no Turborepo yet

requirements.md doesn't mandate a specific package manager. Chose npm
workspaces over pnpm/yarn because npm was already installed and Phase 1 only
has one real JS app building (`apps/dashboard`) plus placeholders
(`widget`, `voice-agent`). Turborepo's build-caching value shows up once
there are 3+ apps actually building — adding it now would be complexity
without payoff (rules.md golden rule: "simplicity beats unnecessary
complexity"). Revisit when the widget (Phase 5) starts building for real.

### Python dependency management: uv

Chose `uv` over Poetry/pip+requirements.txt for speed and because it's
becoming the FastAPI-ecosystem default. Single tool for venv + dependency
resolution + lockfile.

### Python version: code on 3.14 locally, pin 3.12 in Docker/CI

requirements.md pins Python 3.12, but only 3.14 was available on the
machine used to scaffold this (no Docker either). The Dockerfile and CI
pin `python:3.12-slim` (the real Railway deploy target); nothing in this
codebase uses 3.13/3.14-only syntax, so local dev on 3.14 is safe. Revisit
if a 3.12-specific behavior difference is ever found.

### Auth: backend-proxied, not direct-client Supabase Auth

api.md lists `/api/v1/auth/login|logout|refresh` as backend endpoints;
architecture.md/rules.md say "use Supabase Auth" which could be read as
"let the dashboard call Supabase directly." Resolved in favor of backend
proxying (via `httpx` to Supabase GoTrue) because:

- Every future client (widget, voice-agent) shares one auth surface instead
  of each needing Supabase env vars and its own session logic.
- Every login/logout is uniformly audited in `audit_logs`.
- The Next.js dashboard never holds access/refresh tokens in client-side
  JS — Next.js route handlers (`/api/auth/login`, `/api/auth/logout`) set
  them as httpOnly cookies, satisfying rules.md's "secure cookies"
  requirement more directly than client-side token storage would.

JWT verification uses the project's JWKS endpoint (asymmetric, ES256/RS256)
rather than a shared HS256 secret — this matches current Supabase Auth
signing key behavior and avoids distributing a shared secret to the backend
that would need rotation in lockstep with Supabase.

### RLS as defense-in-depth, not the primary gate

Phase 1's actual authorization enforcement happens in FastAPI
(`app.deps.get_current_membership` + `app.roles.permissions.require_permission`),
using the Supabase `service_role` connection (bypasses RLS). RLS policies
are still written and enabled on every tenant-owned table so that any
future direct-Postgres access path (Supabase Realtime subscriptions in
Phase 2+, ad-hoc reporting) cannot cross a tenant boundary even if the
application layer is ever misconfigured. Both layers are real, not
decorative — see `alembic/versions/0002_rls_policies.py`.

### RBAC: 5 system roles, tenant_id nullable on tenant_roles for future custom roles

`tenant_roles.tenant_id` is nullable specifically so per-tenant custom
roles are a future additive change (Phase 10 "Enterprise" territory) rather
than a schema redesign. Phase 1 seeds exactly 5 global system roles (owner,
admin, manager, staff, read_only) per rules.md §4.

### Deferred rather than stubbed

Two things rules.md nominally requires "now" are implemented as explicit,
documented interim solutions rather than either being skipped silently or
over-built before they're needed:

- **Rate limiting** on `/auth/login`: in-process token bucket (single
  replica only). Real shared limiting needs Redis, which isn't wired until
  Phase 3. Tracked in roadmap.md tech debt.
- **JWKS caching**: in-process (PyJWT's `PyJWKClient`, 1hr lifespan). Same
  Phase 3 Redis dependency.

### Git: not initialized yet

Per explicit user decision this session — files exist on disk only, no
version history yet. CI workflow and `.gitignore` are still written now
since they're pure config that costs nothing to have ready.
