# product_decisions.md

> Status: Living log of significant architectural/tooling decisions and why they were made.
> Append new entries at the top; never delete history, only supersede it.

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
