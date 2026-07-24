# Phase 9 — Testing Guide

No real Twilio/LiveKit/Deepgram/ElevenLabs credentials exist, so "testing"
here means: every layer that doesn't require a live phone call is
verified for real; the live-call path is verified structurally (imports,
constructs, routes registered) and left ready for a real end-to-end test
the moment credentials exist.

## What was actually run and passed (against the real Supabase project, in a
disposable schema per `tests/conftest.py`'s safety boundary where DB tests
apply, or directly with cleanup for one-off verification scripts)

- `app.voice.service.handle_incoming_call` → creates a real `Customer` +
  `Conversation` (`channel="voice"`) + `VoiceCall` (`status="ringing"`).
- `app.voice.service.mark_call_status` → transitions `ringing` →
  `in_progress` (attaches `livekit_room_name`) → `completed` (computes
  `duration_seconds`, sets `outcome`).
- Full FastAPI app import (`app.main`) succeeds with the new `voice`
  router mounted — `/api/v1/voice/calls`, `/api/v1/voice/calls/active`,
  `/api/v1/voice/calls/{id}`, `/api/v1/voice/calls/{id}/takeover`,
  `/api/v1/voice/calls/{id}/end`, `/api/v1/voice/twilio/status`,
  `/api/v1/voice/livekit/webhook` all present in the OpenAPI schema.
- `app.voice.agent` imports cleanly; `ResortVoiceAgent` constructs
  correctly and reaches its intended fail point
  (`get_voice_llm_provider()` raising a clear `ValidationErrorApp` because
  `GROQ_API_KEY` is genuinely unset) — the correct behavior with
  placeholder credentials, not a bug (see PROVIDER_INTEGRATION.md).
- `alembic upgrade head` applied `0030_voice_calls` to the real production
  database cleanly: `conversations.channel` now accepts `'voice'`,
  `voice_calls` exists with RLS enabled.
- Dashboard: `npm run lint` and `npm run build` both clean with the new
  `/voice-calls`, `/voice-calls/[id]` pages and `livekit-client` dependency.

## What requires real credentials and could not be run

- An actual inbound PSTN call through Twilio → LiveKit SIP → the agent
  worker → Deepgram/ElevenLabs → back to the caller.
- The LiveKit webhook receiver's signature verification against a real
  LiveKit-signed request (verified structurally: `api.WebhookReceiver`/
  `api.TokenVerifier` construct correctly; the actual HMAC check needs a
  live signed payload).
- The Twilio webhook signature check against a real Twilio-signed request
  (same situation — `twilio.request_validator.RequestValidator` is the
  real, official SDK class, just untested against a live signature here).
- Staff browser takeover audio (`livekit-client` connecting into a live
  room) — needs an actual LiveKit room with a live SIP participant in it.

## How to actually test once credentials exist

1. Point a real phone at the configured Twilio number, call it.
2. Watch `/voice-calls` in the dashboard — a row should appear within a
   few seconds (from the Twilio status callback) even before the agent
   fully connects.
3. Speak; confirm the AI responds and the underlying `Conversation`'s
   messages match what was said in each direction (check via
   `/conversations/{id}`, linked from the call detail page).
4. Say something that should trigger handoff (e.g. "let me speak to a
   person") — confirm the AI stops talking and a notification appears.
5. Click **Take over** on the call — confirm your browser mic connects and
   the caller can hear you.
6. Click **End call** — confirm the call actually disconnects and the row
   moves to `completed` with a populated duration.

## Regression check

Re-run the existing suites unaffected by this phase to confirm no
regressions: `tests/test_orchestration_tool_handlers.py` and
`tests/test_orchestration_prompt_builder.py` (the `channel_block("voice")`
addition is additive — the `"whatsapp"`/`"webchat"` branches are
untouched) still pass.
