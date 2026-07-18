# Phase 5 — Website Chat Deployment Readiness

## New environment variables

Backend (`.env`, read by `apps/api/app/config.py`):

```env
WEBCHAT_ENABLED=true
WEBCHAT_ALLOWED_ORIGINS=http://localhost:3000
WEBCHAT_SESSION_TTL_SECONDS=604800
WEBCHAT_MAX_MESSAGE_LENGTH=2000
WEBCHAT_RATE_LIMIT_PER_MINUTE=8
WEBCHAT_CONVERSATION_LIMIT_PER_IP_PER_HOUR=5
WEBCHAT_MESSAGE_LIMIT_PER_IP_PER_MINUTE=20
```

`WEBCHAT_ALLOWED_ORIGINS` is currently informational/reserved — the
webchat endpoints are designed to be called server-to-server by
`apps/website`'s own Next.js server (see `WEBCHAT_ARCHITECTURE.md`), which
isn't subject to browser CORS at all. If a deployment ever needs the
browser to call FastAPI's webchat endpoints directly, wire this setting
into a dedicated CORS policy for that router rather than widening
`CORS_ALLOWED_ORIGINS` (which governs the staff dashboard's origin list).

Website (`apps/website`, only `NEXT_PUBLIC_*` — never a secret):

```env
NEXT_PUBLIC_SITE_URL=https://www.rkprresort.com
NEXT_PUBLIC_API_BASE_URL=https://api.rkprresort.com
NEXT_PUBLIC_WEBCHAT_ENABLED=true
```

`apps/website` needs no `OPENAI_API_KEY`, `SUPABASE_*`, `DATABASE_URL`, or
`REDIS_URL` at all — confirmed by code inspection (see
`WEBCHAT_SECURITY.md`).

## Running locally (all pieces)

```bash
# 1. Backend
cd apps/api
uv sync
uv run alembic upgrade head     # includes 0024_webchat_sessions
uv run uvicorn app.main:app --reload --port 8000

# 2. Website (new — port 3100 to avoid colliding with the dashboard's 3000)
npm run dev -w apps/website -- -p 3100
# or: npm run website:dev (defaults to 3000 — adjust if running alongside the dashboard)

# 3. Dashboard (unrelated to webchat, but shares the same backend)
npm run dashboard:dev
```

Redis is optional locally (`REDIS_URL` unset) — the webchat rate limiter
fails open with a logged warning rather than blocking guest chat; see
`WEBCHAT_SECURITY.md`.

## CORS / cookies / HTTPS in production

- FastAPI's `cors_allowed_origins` is unaffected by this phase — the
  webchat router is not called by any browser directly in the intended
  deployment shape.
- The webchat session cookie is `Secure` in production
  (`session_cookie_secure`, an existing setting, reused here) — meaning
  it will **not** be set at all over plain HTTP. Production must serve
  `apps/website` over HTTPS for the chat to function; this is already
  the expected posture for any real deployment (per `docs/architecture.md`).
- `SameSite=Lax` requires no additional configuration since the browser
  only ever talks to its own origin (`apps/website`).

## Build / lint / typecheck

```bash
npm run website:build   # next build — production build + TypeScript check
npm run website:lint    # eslint (next lint)
```

Both were run and passing as of this phase's completion (see
`PHASE_5_COMPLETION_REPORT.md` for the exact output).

## CI

`.github/workflows/ci.yml` gained a `website` job mirroring the existing
`dashboard` job (checkout, Node 20, `npm ci`, lint, build) — the website
has no `typecheck` script separate from `next build`'s own TypeScript
pass (Next.js 16 runs `tsc` as part of `next build` itself, unlike the
dashboard's separate `tsc --noEmit` script), so the CI job's steps are
lint + build only.

## Database migration checklist (per `docs/incidents/DATABASE_SAFETY_CONTROLS.md`)

Before running `0024_webchat_sessions` against any live/shared database:
1. Confirm the target database identity (`SUPABASE_URL`/connection
   string) matches the intended project.
2. Run it first against an isolated schema/database — this phase's own
   `tests/conftest.py` sandbox (`Base.metadata.create_all` in a randomized
   schema) already exercises the exact same table shape the migration
   creates; a from-scratch `alembic upgrade head` replay in a scratch
   database is the recommended second check before a production run.
3. It is purely additive (`CREATE TABLE` + indexes + RLS policies) — no
   existing table, column, or data is modified. `downgrade()` is a clean
   `DROP TABLE`.
4. No `Base.metadata.drop_all()`, `TRUNCATE`, or `alembic downgrade` was
   run against any live database as part of this phase.

## Honest deployment gaps (not addressed this phase)

- **Production deployment itself was not performed** — no Vercel/Railway
  deploy was made; this document describes what's required, not a
  completed rollout.
- **Database backup/PITR** remains unconfigured at the Supabase project
  level (a pre-existing gap carried over from the Phase 4 completion
  report, not newly introduced or newly closed here).
- **Groq fallback** was not exercised as part of this phase's webchat
  work (unchanged from Phase 4's own honest-gaps list).
- **Redis failure behavior** for the webchat rate limiter is reviewed by
  code inspection, not exercised against a live Redis instance failing
  mid-session, in this tool environment.
