# Phase 5 — Website Chat Architecture

## Where things live

```
apps/website/                          # the RKPR resort's own Next.js site (imported this phase)
  src/lib/webchat-client.ts            # browser-side client — talks only to this app's own /api/webchat/*
  src/lib/server-webchat.ts            # server-side cookie + FastAPI-proxy helper (Route Handlers only)
  src/app/api/webchat/{session,messages,handoff,feedback,contact}/route.ts
  src/components/ChatWidget.tsx        # top-level widget (state, session lifecycle, polling)
  src/components/webchat/{MessageBubble,CitationList,QuickActions,ContactPrompt,types}.tsx

apps/api/app/webchat/                  # new FastAPI module — the public, anonymous-guest API
  models.py       # WebchatSession
  schemas.py      # request/response Pydantic models (guest-safe shapes only)
  repository.py   # token generation/hashing, session CRUD
  deps.py         # get_webchat_session — resolves identity from an opaque token
  rate_limit.py   # Redis-backed, fail-open fixed-window limiter
  service.py      # business logic — calls app.orchestration.pipeline.orchestrate(), never duplicates it
  router.py       # /api/v1/webchat/* endpoints

apps/api/alembic/versions/0024_webchat_sessions.py   # one new table
```

## Why the browser never talks to FastAPI directly

The website's own Next.js server sits between the browser and FastAPI —
exactly the same shape `apps/dashboard` already uses for its staff-facing
calls (`apps/dashboard/src/lib/server-api.ts` → `fetchFromApi`). This
buys three things simultaneously:

1. **No AI/database credentials ever reach the browser.** `apps/website`
   has zero `OPENAI_API_KEY`/`SUPABASE_SERVICE_ROLE_KEY`/etc. anywhere —
   not even server-side — because it never needs them; it only ever
   forwards a request to FastAPI, which holds all real secrets.
2. **The webchat session token is never readable by browser JavaScript.**
   It lives in an `HttpOnly` cookie set by the Next.js server
   (`apps/website/src/lib/server-webchat.ts`), not in `localStorage` or a
   client-visible cookie.
3. **No CORS/credentials complexity.** The browser only ever calls its
   own origin (`apps/website`'s `/api/webchat/*`); the Next.js server's
   call to FastAPI is a plain server-to-server `fetch`, which isn't
   subject to CORS at all. FastAPI's `cors_allowed_origins` setting
   remains scoped to the dashboard's direct browser calls — the webchat
   path doesn't add a new browser-facing CORS surface.

## Session model

- `POST /api/v1/webchat/sessions` (FastAPI) mints a 256-bit opaque token
  (`secrets.token_urlsafe(32)`), creates an anonymous `Customer` (no
  contacts) + a `Conversation` (`channel="webchat"`), and stores only the
  token's SHA-256 hash in the new `webchat_sessions` table — the same
  principle as storing a password hash, not a password.
- The Next.js route handler (`api/webchat/session/route.ts`) receives the
  raw token in that one response, stores it in an `HttpOnly`/
  `Secure`(prod)/`SameSite=Lax` cookie (`rkpr_wc_token`) plus a second
  cookie for the session id (`rkpr_wc_sid`), and never returns the raw
  token to the browser again.
- Every later call resolves identity purely from that token
  (`app.webchat.deps.get_webchat_session`: hash the token, look up the
  row, reject if missing/revoked/expired) — a path `session_id` is never
  itself trusted as authorization, only checked for consistency against
  the token-resolved session (`app.webchat.router._require_owns_session`),
  responding identically to "not found" either way so it can't be used to
  probe which ids exist.
- `GET /api/webchat/session` (Next.js) restores state after a page
  refresh by re-checking the existing cookies; it never mints a new
  session on its own. A guest who never opens the widget never gets a
  database row.

## Why "webchat" as the channel value, not "website_chat"

`app.conversations.constants.CHANNELS = ("whatsapp", "webchat")` already
existed from Phase 4 (`ProcessMessageRequest.channel` already defaulted to
`"webchat"`). Reusing it avoids a migration and an unnecessary second
value meaning the same thing.

## Why one orchestration pipeline, not two

`app.webchat.service.send_message` persists the guest's message the same
way any channel would (`app.messages.service.send_message`), then calls
`app.orchestration.pipeline.orchestrate()` — the exact function
`app.orchestration.router` (staff/dashboard) also calls. Intent
classification, retrieval, guardrails, the handoff engine, and Customer
360 memory all run identically regardless of channel. Nothing in
`app.webchat` reimplements any of that.

The one exception is guest-initiated handoff
(`POST /sessions/{id}/handoff` — the "Speak to staff" quick action). This
reuses the same deterministic primitives the staff-facing forced-handoff
endpoint already uses (`flow_engine.apply_handoff` +
`conversations_service.change_dialogue_state/change_status`) rather than
routing through free-text intent classification, because a button click
is an unambiguous signal that shouldn't depend on an LLM correctly
inferring intent from typed text. It is a *reuse* of existing primitives
under a different `changed_by` value (`"system"`, since a guest is neither
`"ai"` nor `"human"` staff in `STATE_CHANGED_BY`'s vocabulary), not a
second handoff implementation.

## Guest-safe response shaping

`app.webchat.schemas` deliberately defines narrower types than the
staff-facing `app.orchestration.schemas`:

- `WebchatCitationOut` has no `chunk_id` or `score` — only
  `source_title`, `source_priority`, `authoritative`.
- Feedback/audit events never expose an internal `orchestration_turns.id`
  to the browser; the client sends `turn_id: null` and the service falls
  back to `resource_type="conversation"` for the audit trail.
- Errors are FastAPI's existing `{"success": false, "error": {"code",
  "message"}}` envelope — never a raw exception, SQL error, or stack
  trace (`app/errors.py`'s existing global handlers apply unchanged; nothing
  in `app.webchat` bypasses them).

## Duplicate-submission handling

A client-generated `client_message_id` (a UUID minted before the fetch
call) is threaded through as `Message.external_message_id` (prefixed
`"webchat:"`) — the exact idempotency column Phase 6 WhatsApp webhooks are
already designed around
(`app.messages.repository.find_by_external_id`). A retried/double-clicked
send resolves to the same `Message` row, and `orchestrate()`'s own
`message_id` idempotency (`get_turn_by_message_id`) guarantees the LLM is
never invoked twice for it. No second dedup mechanism was invented.

## Streaming — deliberately not implemented this phase

`orchestrate()` returns one complete result synchronously; there is no
token-level streaming anywhere in the LLM provider layer
(`app.orchestration.llm.*`), and retrofitting it would touch the pipeline
that was just hardened and real-data-validated in Phase 4. Per the Phase 5
brief's own instruction, this is a documented, deliberate deferral, not a
fragile fake-streaming shim: the widget shows a clean typing indicator
("Aranya is thinking…") and renders the complete response once it
arrives. The frontend's `sendMessage` return shape (a single
`WebchatMessageResult`) is designed so a future streaming transport could
be swapped in behind the same call site without changing the widget's
state model.

## Staff replies reaching the guest without a page refresh

There is no websocket/SSE transport in this stack. While the widget panel
is open, it polls `GET /sessions/{id}/messages` every 10 seconds and
appends any non-`customer` messages not already rendered locally — this
is how a staff reply sent from the dashboard shows up in the guest's chat
without them needing to send another message first. This is an explicit,
documented stand-in for real-time delivery (see "Honest open items" in
`PHASE_5_COMPLETION_REPORT.md`), not a permanent design choice.

## Anonymous → known customer conversion

`app.webchat.service.capture_contact` looks up the phone/email via the
existing `app.customers.repository.find_customer_by_contact` before
writing anything. If it already belongs to a *different* customer, this
conversation (and the session row) is re-pointed to that pre-existing
customer id instead of creating a duplicate `Customer`/`CustomerContact` —
the correct Customer 360 outcome, and the guest sees an identical generic
success message either way, so the response itself never reveals whether
the value was already known.
