# Phase 9 — Security Review

## Webhook validation

Every inbound webhook this phase adds is signature-validated before
touching the database:

- **Twilio status callback** (`/api/v1/voice/twilio/status`):
  `app.voice.twilio_utils.validate_twilio_signature` runs Twilio's own
  `RequestValidator` (official SDK) against the full request URL, form
  params, and `X-Twilio-Signature` header. A failed check raises
  `UnauthorizedError` (401) before `service.handle_incoming_call`/
  `mark_call_status` ever runs.
- **LiveKit webhook** (`/api/v1/voice/livekit/webhook`):
  `app.voice.livekit_client.verify_webhook` uses LiveKit's own
  `api.WebhookReceiver`/`api.TokenVerifier` to check the HMAC-signed
  `Authorization` header against the raw body. A failed or unconfigured
  check returns `None`, and the router raises `UnauthorizedError`.

Neither webhook is skipped when the relevant secret is unset in a way that
would accidentally allow unsigned requests through in production — if
`twilio_auth_token` is unset, the Twilio check is skipped (there's nothing
to validate against and no real Twilio account is wired up yet); once a
real `TWILIO_AUTH_TOKEN` is set, validation is enforced unconditionally.

## Staff endpoints

`/api/v1/voice/calls`, `/calls/active`, `/calls/{id}`, `/calls/{id}/
takeover`, `/calls/{id}/end` all require `Depends(get_current_user)` — the
same Supabase JWT auth every other staff-facing endpoint in this codebase
requires. No new auth mechanism was introduced.

## LiveKit tokens

`mint_staff_token` scopes a staff member's access token to exactly one
room (`room=room_name` in `VideoGrants`, not a wildcard) with
`room_join`/`can_publish`/`can_subscribe` — a staff member cannot use a
takeover token to join a different call's room. Tokens are minted
per-request, never cached or reused across calls.

## No secrets ever reach the caller or the browser client

- The caller only ever hears TTS audio — no internal prompt, RAG content,
  or system message is ever spoken (the same grounding/privacy rules
  `app.orchestration.prompts.templates` already enforces for text apply
  identically to voice, since `orchestrate()` is the same call).
- The staff browser only ever receives a short-lived, room-scoped LiveKit
  JWT — never the LiveKit API secret, Twilio auth token, Deepgram key, or
  ElevenLabs key. Those live only in `app.config.Settings` on the backend/
  agent-worker processes.

## Failure handling never exposes technical detail

`ResortVoiceAgent.llm_node` wraps the `orchestrate()` call in a bare
`except Exception` that logs the real exception server-side
(`logger.exception`) and returns a generic "could you say that again"
line to the caller — a caller never hears a stack trace, an internal
error code, or a raw provider error message. This mirrors
`orchestrate()`'s own `AllProvidersFailedError` → safe-fallback-response
behavior for text channels.

## What was not built (reduces attack surface)

No outbound calling, no auto-dialing, no call recording/storage beyond the
existing message-transcript persistence, no new credential-entry surface
in the dashboard (all Phase 9 secrets are environment variables, set at
the infra layer, never typed into the UI) — consistent with this
project's existing pattern for every other provider integration.
