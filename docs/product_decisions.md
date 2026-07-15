# product_decisions.md

> Status: Living log of significant architectural/tooling decisions and why they were made.
> Append new entries at the top; never delete history, only supersede it.

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
