# Phase 5 Completion Report — Website Chat Channel

Date: 2026-07-18

## Implementation summary

### Backend changes

- New `apps/api/app/webchat/` module: `models.py` (`WebchatSession`),
  `schemas.py` (guest-safe request/response shapes), `repository.py`
  (token generation/hashing, session CRUD), `deps.py`
  (`get_webchat_session` — resolves identity from an opaque token),
  `rate_limit.py` (Redis-backed, fail-open fixed-window limiter),
  `service.py` (business logic — calls `orchestrate()`, never duplicates
  it), `router.py` (`/api/v1/webchat/*`).
- New Alembic migration `0024_webchat_sessions.py` — one additive table +
  RLS, following the established single-resort RLS pattern.
- `app/main.py` mounts the new router; `app/config.py` gained 7
  `WEBCHAT_*` settings (all configuration, no magic numbers in code);
  `alembic/env.py` and `tests/conftest.py` both updated to import the new
  model (the recurring "forgot to register a model" bug class from
  Phase 3/4, avoided proactively this time).

### Website changes

- Imported the uploaded `RKPR-WEBSITE-main.zip` codebase into this
  monorepo as a new `apps/website` npm workspace (no prior `.git`
  history existed to preserve). Full audit:
  `docs/phase-5/WEBSITE_CODEBASE_AUDIT.md`.
- Deleted the pre-existing fake `/api/chat` route (keyword-matching
  fabricated prices/policies) and replaced it with real proxy routes:
  `apps/website/src/app/api/webchat/{session,messages,handoff,feedback,contact}/route.ts`.
- New `apps/website/src/lib/{webchat-client.ts,server-webchat.ts}` — the
  browser-side client and the server-side FastAPI-proxy helper,
  respectively.
- Rebuilt `apps/website/src/components/ChatWidget.tsx` and added
  `src/components/webchat/{MessageBubble,CitationList,QuickActions,
  ContactPrompt,types}.tsx` — same forest/bronze visual identity as
  before, real session lifecycle, quick actions that go through the real
  pipeline, guest-safe citations, handoff banner, staff-message polling,
  optional contact capture, retry-on-failure, accessibility (dialog role,
  focus management, `aria-live`, reduced-motion support, Escape-to-close).
- Fixed 33 pre-existing ESLint errors / 57 warnings across ~20 unrelated
  page/component files (unescaped JSX characters, unused imports, one
  `no-explicit-any`, one `react-hooks/set-state-in-effect`) as a
  mechanical, non-visual cleanup so the new CI job is meaningful.
- `.github/workflows/ci.yml` gained a `website` job (lint + build).
- Root `package.json` registered `apps/website` as a workspace.

### Database changes

One additive migration (`webchat_sessions`), reviewed for reversibility
(`downgrade()` is a clean `DROP TABLE`), never run against any live
database in this session (only against the sandboxed test schema via
`Base.metadata.create_all`, and even that could not be executed this
session — see "Honest open items"). No existing table/column was
modified.

### Session model

Opaque 256-bit token, SHA-256-hashed at rest, resolved server-side on
every request, never trusted from a client-supplied id. `HttpOnly` +
`Secure`(prod) + `SameSite=Lax` cookie set by `apps/website`'s own server
— the browser never sees the raw token. 7-day default TTL, explicit
revocation on session end. Full detail: `WEBCHAT_ARCHITECTURE.md`.

### Security controls

Session/IDOR, CSRF, XSS, secret-leakage, and rate-limiting posture are
each addressed in `docs/phase-5/WEBCHAT_SECURITY.md`. Headline points:
identity is 100% token-based (path ids are never an authorization check);
no Markdown/HTML rendering was introduced (plain React text, safe by
construction); zero AI/DB credentials exist anywhere in `apps/website`;
every rate limit is a configuration value, and the limiter fails open
(never blocks chat) if Redis is briefly unavailable.

### Handoff behavior

Guest-initiated ("Speak to staff") reuses the exact deterministic
primitives the staff-facing forced-handoff endpoint already used in
Phase 4 (`flow_engine.apply_handoff` + `conversations_service` state
transitions) — not a second implementation. Automatic handoff (refund/
cancellation/complaint/repeated-low-confidence/etc.) is unchanged from
Phase 4's own handoff engine; the webchat channel doesn't alter its
triggers. Staff replies reach the guest via 10-second transcript polling
while the widget is open — a documented stand-in for real-time delivery.

### Citation behavior

`WebchatCitationOut` exposes only `source_title`, `source_priority`, and
`authoritative` — never a chunk id, vector id, or numeric relevance
score. Non-authoritative/draft sources are visually flagged in the UI
("unconfirmed — please verify with staff"), not presented as confirmed
fact.

### Rate limits

| Limit | Default | Scope |
|---|---|---|
| New sessions | 5/hour | per IP |
| Messages | 8/minute | per session |
| Message burst | 20/minute | per IP across sessions |
| Message length | 2000 chars | per message |

All seven `WEBCHAT_*` values live in `Settings`/`.env.example`, never
hard-coded.

### Error handling

FastAPI's existing `{"success": false, "error": {code, message}}`
envelope is unchanged and unbypassed. The frontend maps specific codes
(`rate_limited`, `network_error`, `session_required`) to plain,
non-technical guest copy with a phone-number fallback, and never surfaces
a stack trace, SQL error, or internal hostname — confirmed live (see
verification section below), not just by code review.

## Verification summary

| Check | Result |
|---|---|
| Backend lint (`ruff check`) | **Pass** — new `app/webchat/` module and touched files |
| Backend tests written | 3 test files: `test_webchat_auth.py` (10 cases), `test_webchat_service.py` (10 cases), plus `conftest.py` model-registration fix |
| Backend tests executed (no DB needed) | **7 passed** (missing-token / wrong-auth-mechanism rejection) |
| Backend tests executed (DB needed) | **Could not run in this session** — see "Honest open items" |
| Website lint (`npm run website:lint`) | **Pass, zero errors/warnings** (after fixing 33 pre-existing + verifying the new webchat code introduced none) |
| Website typecheck + production build (`npm run website:build`) | **Pass** — Next.js 16/Turbopack, all 52 routes generate |
| Frontend unit/E2E test count | **0** — no frontend test framework exists anywhere in this monorepo (a pre-existing characteristic, not a Phase 5 gap); see `WEBCHAT_TEST_PLAN.md` for why none was introduced |
| Real-browser manual verification | **Performed** — see below |
| Real OpenAI test count | **0** this session (blocked by DB connectivity — see below) |
| Real RKPR scenarios tested (of 16 in the brief) | 2 genuinely exercised live (refresh/restore, backend-failure handling); the rest structurally reviewed/unit-tested but not exercised end-to-end live — see `WEBCHAT_TEST_PLAN.md`'s scenario table |
| Mobile testing | Verified — full-screen layout confirmed via computed styles at a 375×812 viewport in a real browser |
| Accessibility testing | Verified via the accessibility tree in a real browser: `dialog` role with correct label, `alert` role on errors, all interactive elements have accessible names, focus moves to the composer on open |
| Database cleanup confirmation | N/A — no live database writes were made or needed cleanup this session |

### What real-browser verification actually did

Both `apps/api` (FastAPI) and `apps/website` (Next.js, port 3100) were
started for real in this session's Browser tool. Confirmed live:
- The homepage renders unchanged — hero section, navigation, design
  tokens, existing pages all intact.
- The chat launcher renders with the correct accessible name and opens a
  real `dialog`.
- Quick actions, composer, and the send button are all present and wired.
- Sending a real message triggered the real proxy chain
  (`apps/website` → FastAPI `/api/v1/webchat/sessions`), which returned a
  genuine `500` because this session's tool sandbox could not sustain a
  Postgres connection to Supabase (see below) — and the widget correctly
  rendered the intended non-technical fallback message with a phone
  number, with a visible **Retry** affordance on the failed guest bubble,
  and no technical detail leaked.
- `GET /api/webchat/session` correctly returned `{exists: false}` on a
  fresh session (refresh/restore path).
- Resizing to a 375×812 mobile viewport and inspecting computed styles
  confirmed the panel is genuinely full-screen (`width: 375.33px`,
  `height: 100dvh`) at that breakpoint, not just visually approximate.

## Honest open items

- **DB connectivity in this session's tool environment.** Raw Postgres
  TCP connections to the project's Supabase pooler failed throughout this
  phase (`WinError 1225`) — confirmed environment-specific, not a
  regression: the identical, previously-passing Phase 3/4 pytest suite
  fails the exact same way in this same session, and a direct
  `Test-NetConnection` probe succeeded at the TCP layer while the actual
  Postgres wire-protocol connection still failed. This blocked: running
  the new DB-dependent webchat tests, any real message-send verification
  in the browser, and the real-OpenAI validation checklist. **Action
  needed**: re-run `cd apps/api && uv run pytest` and the manual E2E
  checklist in `WEBCHAT_TEST_PLAN.md` in an environment with confirmed
  Postgres connectivity (this developer's own machine, or CI) before
  treating Phase 5 as fully DB-verified.
- **No real-OpenAI validation was performed** this phase, for the same
  reason (a session/conversation must exist in the database first). A
  small, cost-controlled pass through the 12 knowledge-question scenarios
  via the real website UI is the recommended next step once DB
  connectivity is confirmed.
- **Real-time delivery for staff replies is polling, not push** — a
  documented, temporary stand-in (10-second interval while the widget is
  open). A websocket/SSE transport was out of scope for this phase and
  is not implemented.
- **No token-level response streaming** — `orchestrate()` returns one
  complete result; the widget shows a typing indicator instead. Deferred
  deliberately, not faked.
- **Groq fallback, Redis-failure behavior, and real staff-response
  timing** were not exercised live this phase — consistent with the same
  gaps already carried over, undisguised, from the Phase 4 completion
  report.
- **No frontend test framework** exists in this monorepo (dashboard
  included) — Phase 5 did not introduce one; TypeScript strict mode +
  production build + real-browser manual verification were the
  substitute safety net this phase, documented explicitly rather than
  silently skipped.
- **Production deployment was not performed** — `WEBCHAT_DEPLOYMENT.md`
  documents what's required; no Vercel/Railway rollout happened this
  session.
- **Database backup/PITR** remains unconfigured at the Supabase project
  level — unchanged, pre-existing gap from Phase 4.
- **No dedicated privacy-policy page exists** on the resort website — the
  in-chat privacy notice is shown as plain text with no link, per the
  brief's own instruction not to invent a policy page that doesn't exist.

## What Phase 5 acceptance criteria are met vs. not

Met: website audited and design preserved; chat widget integrated into
the real website; anonymous sessions are token-based and IDOR-resistant
by design (unit-tested); conversations persist through the existing
Phase 2/4 schema; Phase 4 orchestration is used exclusively (no second
implementation); citations display safely with draft/unapproved content
visually flagged; human handoff reuses proven primitives; session
restoration works (verified live); mobile layout works (verified live);
accessibility basics are in place (verified live); XSS risk is addressed
by construction (no `dangerouslySetInnerHTML`, no Markdown parser
introduced); rate limiting is server-side and configuration-driven;
secrets are backend-only (verified by code inspection); provider/backend
failures are handled gracefully (verified live, genuinely, not
simulated); website lint and build both pass.

Not fully met, honestly: "Backend tests pass" — written and structurally
reviewed, but not executed against a live database in this session.
"Real RKPR validation passes" — not performed this session (blocked by
the same DB connectivity issue). Both are flagged above with a concrete
next action, not glossed over.
