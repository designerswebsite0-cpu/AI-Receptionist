# Phase 5 — Website Chat Security Review

## Session security

- **Token entropy**: 256 bits (`secrets.token_urlsafe(32)`) — not
  brute-forceable.
- **Never stored raw**: only `sha256(token)` is persisted
  (`webchat_sessions.token_hash`, unique + indexed). A leaked database row
  cannot be replayed as a live session.
- **Never a sequential/database id**: the guest never sees a raw
  `customers.id`/`conversations.id` as their credential — only the opaque
  token. The `session_id` UUID that does appear in URLs is not itself
  trusted for authorization (see IDOR below).
- **Cookie flags**: `HttpOnly` (JS cannot read it — mitigates XSS
  exfiltration of the session), `Secure` in production
  (`session_cookie_secure` setting, already an existing config value reused
  here), `SameSite=Lax` (sent on top-level navigation and same-site
  requests, not on cross-site subrequests — reasonable default for a
  same-origin-only integration; see CSRF below for why `Lax` is sufficient
  here).
- **Expiry**: `WEBCHAT_SESSION_TTL_SECONDS` (default 7 days), checked on
  every request (`app.webchat.deps.get_webchat_session`); an expired or
  explicitly `revoked_at` session is rejected with 401.
- **No API secrets in browser storage**: the raw token lives only in an
  `HttpOnly` cookie scoped to `apps/website`'s own origin — never
  `localStorage`, never a client-visible cookie, never in a JS variable
  reachable by `document.cookie`.

## IDOR (one guest reading another's conversation)

Identity resolution is **exclusively** token-based
(`app.webchat.deps.get_webchat_session` hashes the presented token and
looks up the exact row). The `{session_id}` path segment is checked for
consistency against the token-resolved session
(`app.webchat.router._require_owns_session`) but is never itself a lookup
key or an authorization credential — supplying someone else's real
`session_id` with your own token still resolves to *your* session, and a
mismatch is rejected with a generic 404 (not "403 wrong session," which
would confirm the id exists). This is exercised by
`test_two_sessions_never_share_a_token_hash` in
`apps/api/tests/test_webchat_service.py`.

## CSRF

The webchat endpoints only accept `application/json` POST bodies via
`fetch()`, never an HTML form `action=`. A cross-site attacker page cannot
set the `Content-Type: application/json` header on a simple form
submission, and a cross-site `fetch()` with credentials would be subject
to the browser's CORS preflight — which `apps/website` doesn't need to
(and doesn't) allow for arbitrary origins, since the browser never calls
FastAPI directly at all (see `WEBCHAT_ARCHITECTURE.md`). `SameSite=Lax`
is a second, independent layer: it's still sent on the guest's own
top-level navigations (so a page refresh/restore works) but not attached
to a cross-site page's background requests.

## XSS / unsafe content rendering

- Guest and assistant text is rendered as **plain React text content**
  (`{message.text}` inside a `<p>`), never `dangerouslySetInnerHTML`.
  React escapes this by construction — a guest typing `<script>` or an
  AI response containing HTML-looking text renders as inert text, not
  markup.
- **No Markdown renderer was introduced.** The brief's Markdown guidance
  ("if supported, sanitize with a proven library") is conditional; adding
  Markdown rendering (and a sanitizer dependency) for formatting that
  isn't currently required is deferred — see "Honest open items" in
  `PHASE_5_COMPLETION_REPORT.md`. If Markdown rendering is added later,
  it must go through a proven sanitizer (e.g. `rehype-sanitize` /
  `dompurify`) before any HTML is ever allowed to reach the DOM.
- Citation `source_title` strings come from the knowledge base (staff-
  curated content, not guest input) and are rendered the same safe way.

## Prompt injection boundaries

Unchanged from Phase 4: `app.orchestration.prompts.builder` already
treats guest message content as untrusted data placed in a clearly
delimited user-turn, never concatenated into the system prompt, and
`app.orchestration.guardrails.validator` still runs on every response
before it's persisted or returned — nothing about the webchat channel
bypasses either.

## Secret leakage

- `apps/website` has no `OPENAI_API_KEY`, `GROQ_API_KEY`,
  `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, or `REDIS_URL` anywhere in
  its own environment — confirmed by inspection of
  `apps/website/.env`-consuming code: only `NEXT_PUBLIC_SITE_URL`,
  `NEXT_PUBLIC_API_BASE_URL`, and `NEXT_PUBLIC_WEBCHAT_ENABLED` are read,
  all intentionally public.
- FastAPI error responses never include exception messages, SQL errors,
  or stack traces to the client (`app/errors.py`'s existing global
  handlers, unchanged) — unhandled exceptions server-side log full detail
  with the correlation id (`app.logging`) but return a generic
  `{"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}`
  to the guest. Verified directly in a real browser: see
  `PHASE_5_COMPLETION_REPORT.md`'s verification section for the actual
  observed alert text after a real backend failure.

## Rate limiting / abuse

Every limit is a `Settings` field (`WEBCHAT_*`), never a hard-coded
number in `app/webchat/router.py`:

| Limit | Setting | Default | Scope |
|---|---|---|---|
| New sessions | `webchat_conversation_limit_per_ip_per_hour` | 5 | per IP |
| Messages | `webchat_rate_limit_per_minute` | 8 | per session |
| Message burst | `webchat_message_limit_per_ip_per_minute` | 20 | per IP (across sessions) |
| Message length | `webchat_max_message_length` | 2000 chars | per message |

Implemented as a Redis fixed-window counter
(`app.webchat.rate_limit.enforce`). **Fails open** if Redis is
unreachable or unconfigured (logs a warning, allows the request) — a
deliberate tradeoff so an optional shared counter store being briefly
down never blocks a guest from chatting; the message-length and
session-auth checks still apply regardless. `x-forwarded-for` is read for
the per-IP key, taking the first hop (the immediate proxy/CDN's own
address is not trusted as the visitor's, matching standard reverse-proxy
convention).

An attacker cannot create unlimited conversations (IP-limited) or trigger
unlimited paid LLM calls (session- and IP-rate-limited on the message
endpoint specifically, independent of session creation).

## Governance / retrieval boundary

Unchanged from Phase 3/4: `app.knowledge.retrieval.service.search(...,
guest_only=True)` is what both the initial context-assembly retrieval and
the LLM's own `search_resort_knowledge` follow-up tool call already use —
this was true before Phase 5 and nothing here weakens it. A webchat guest
can never retrieve staff-only-visibility content through either path.

## Log redaction / PII

- Audit events (`webchat.feedback_submitted`, contact capture, session
  creation) never log the raw session token, phone number, or email in
  plaintext beyond what's already stored on the `Customer`/
  `CustomerContact` rows themselves (existing Customer 360 data
  handling, unchanged).
- Structured logs (`app.logging`) carry a `correlation_id` and (once
  resolved) `user_id` — webchat requests have no `user_id` (anonymous),
  which is expected and not a gap.

## What was not (and could not be) verified against live infrastructure this session

This tool environment could not sustain a raw Postgres TCP connection to
the project's Supabase pooler (confirmed both via `pytest`'s own
DB-reachability skip guard and a direct `Test-NetConnection` probe that
succeeded at the TCP layer but still failed at the application layer —
environment-specific, not a code issue; the identical pre-existing Phase
3/4 test suite skips for the same reason in this same session). This
means:
- The IDOR/ownership tests, rate-limit enforcement, and full message-send
  flow are **structurally reviewed and pattern-consistent** with already-
  passing Phase 4 tests, but were not executed against a live database in
  this session. Real-browser testing (see completion report) did confirm
  the FastAPI server itself starts correctly, reaches Supabase's HTTPS
  API successfully, and returns a safe, generic error (not a stack trace)
  when the database call inside it fails — a real, if partial,
  confirmation of the error-handling path under genuine failure.
- Recommend re-running `cd apps/api && uv run pytest` in an environment
  with confirmed Postgres connectivity before considering this fully
  DB-verified.
