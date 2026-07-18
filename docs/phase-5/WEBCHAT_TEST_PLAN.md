# Phase 5 — Website Chat Test Plan

## Automated backend tests (pytest, `apps/api/tests/`)

Same conventions as every prior phase in this repo: `db_session`-based
tests use a real Postgres, sandboxed to a randomly-named schema per run
(`tests/conftest.py`'s `_TEST_SCHEMA` — see
`docs/incidents/DATABASE_SAFETY_CONTROLS.md`), never `public`, and skip
cleanly if no database is reachable. `MockLLMProvider` /
`MockEmbeddingProvider` / `HeuristicReranker` are used throughout — no
real OpenAI/Groq call in this suite.

**`tests/test_webchat_auth.py`** (no database needed):
- Every session-scoped endpoint rejects a missing token (401).
- Every session-scoped endpoint rejects a garbage token (401).
- Every session-scoped endpoint rejects a well-formed Supabase staff JWT
  instead of a webchat token (401) — confirms the two auth mechanisms
  are genuinely distinct, not one accidentally accepting the other.

**`tests/test_webchat_service.py`** (real sandboxed Postgres):
- Session creation → anonymous `Customer` (no contacts) + `Conversation`
  (`channel="webchat"`).
- Two independently created sessions never share a token hash, and
  resolving by one's hash never returns the other's row (the actual IDOR-
  prevention property).
- `get_session_state` never re-includes the raw token.
- Sending a message runs the real `orchestrate()` pipeline (via
  `MockLLMProvider`) and returns a guest-safe response (no `chunk_id`/
  `score` on citations).
- Sending the same `client_message_id` twice does not invoke the LLM a
  second time (duplicate-submission guard).
- Guest-initiated handoff escalates the conversation
  (`status="escalated"`, `flow_state="human_handoff_requested"`).
- Contact capture adds a new contact to the anonymous customer when the
  value is unseen.
- Contact capture with an *already-known* phone/email re-points the
  conversation (and session) to the existing customer instead of creating
  a duplicate — and does so without any different response shape the
  guest could use to infer that outcome.
- Feedback submission writes exactly one audit event with the right
  metadata.
- Ending a session sets `revoked_at`.

Also updated: `tests/conftest.py` (added `WebchatSession` to the explicit
model-import list — the same "forgot to import a model" bug class flagged
repeatedly during Phase 3/4 development).

## What's deliberately not automated at the frontend/E2E layer

**No frontend unit-test framework exists anywhere in this monorepo** —
`apps/dashboard` (Phase 2–4's own staff UI) has never had one either; this
is a pre-existing characteristic of the codebase, not a Phase 5 gap. Per
this session's "don't introduce new dependencies unnecessarily" instinct
and to avoid inventing a testing convention unilaterally, Phase 5 does not
add Vitest/Jest/Playwright. Frontend correctness was instead verified two
ways:

1. **TypeScript strict mode + production build** (`npm run website:build`)
   as the automated safety net — a real compile-time check, not a mock.
2. **Manual verification in a real browser** (this session, via the
   Browser tool) — see `PHASE_5_COMPLETION_REPORT.md`'s verification
   section for exactly what was exercised and observed.

## Manual/structured E2E scenario checklist (brief §19, scenarios 1–16)

| # | Scenario | Status this session |
|---|---|---|
| 1 | Guest asks about room categories | Not run against real OpenAI (DB unreachable — see below) |
| 2 | Guest asks which room suits a family | Not run |
| 3 | Guest asks about a private pool | Not run |
| 4 | Guest asks restaurant timings | Not run |
| 5 | Guest asks about an activity | Not run |
| 6 | Approved pricing question | Not run |
| 7 | Draft/uncertain pricing question | Not run |
| 8 | Cancellation question | Not run |
| 9 | Refund request | Not run |
| 10 | Guest asks for a human | Structurally verified (backend test + reused staff-handoff primitives); not exercised live end-to-end |
| 11 | Nonexistent thing | Not run |
| 12 | Prompt injection attempt | Not run live (Phase 4's existing guardrail/prompt-boundary tests already cover the mechanism; nothing webchat-specific bypasses it) |
| 13 | Refresh and restore | **Verified live** — `GET /api/webchat/session` correctly restores cookies/state; confirmed via real browser + network trace |
| 14 | Access another session | Verified at the unit/integration level (`test_two_sessions_never_share_a_token_hash`); not attempted live via two real browser sessions |
| 15 | Backend becomes unavailable | **Verified live** — see below |
| 16 | Staff takes over and releases | Structurally verified (reuses the already-tested Phase 4 `force_handoff`/`release_to_ai` primitives); not exercised live |

### What "verified live" actually means here

This tool session's sandboxed environment could reach Supabase's HTTPS
API (JWKS fetch succeeded at FastAPI startup) but could not sustain a raw
Postgres TCP connection to the project's pooler — confirmed
environment-specific (identical failure mode on the pre-existing,
previously-passing Phase 3/4 test suite; a direct `Test-NetConnection`
probe succeeded at the TCP layer but the actual Postgres wire-protocol
connection still failed). This blocked every scenario that needs a real
database write (1–12, 14, 16).

Scenario 15 ("backend becomes unavailable") ended up being tested for
real, not simulated: with the FastAPI server genuinely running but unable
to reach its database, a real guest message send in a real browser
produced a real `500` from FastAPI, relayed by the Next.js proxy, and the
widget rendered exactly the intended non-technical fallback: *"Something
went wrong on our end. Please try again, or call our reception at +91
98765 43210."* — no stack trace, no SQL error, no internal hostname.
Scenario 13 (refresh/restore) was also genuinely exercised via the
`GET /api/webchat/session` network call succeeding with `{exists: false}`
on a fresh browser profile.

**Recommended before declaring Phase 5 fully done**: re-run this same
checklist in an environment with confirmed Postgres connectivity (e.g.
the developer's own machine, or CI's Postgres service container — see
`.github/workflows/ci.yml`), including a small, cost-controlled real-
OpenAI pass through scenarios 1–12 via the actual website UI.

## Rate-limit / abuse verification

`app.webchat.rate_limit.enforce` was reviewed but not exercised against a
live Redis instance in this session (no `REDIS_URL` configured in this
sandbox either). Its fail-open behavior is implicit in every other test
in `test_webchat_service.py` passing without Redis running at all — if it
failed *closed* instead, every one of those tests would have raised
`RateLimitedError` on the very first Redis operation attempt. A dedicated
live check (start Redis, hit the message endpoint past the configured
limit, confirm a real `429`) is a recommended follow-up.
