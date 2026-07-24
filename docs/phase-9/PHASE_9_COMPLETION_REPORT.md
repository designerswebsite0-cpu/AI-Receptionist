# Phase 9 — Completion Report

Global inbound voice call system. India-specific voice work was not
designed, mentioned, or prepared for anywhere in this phase, per the
brief.

## What was built

**Backend (`apps/api/app/voice/`)**
- `models.py` — `VoiceCall` (call-specific metadata; transcript reuses the
  existing `conversations`/`messages` tables via a new `'voice'` channel).
- `constants.py`, `schemas.py`, `repository.py`, `service.py` — full CRUD
  + lifecycle (`handle_incoming_call`, `mark_call_status`, `takeover_call`,
  `end_call`).
- `providers.py` — Groq-primary/OpenAI-fallback LLM ordering for voice
  (reverse of text channels), reusing Phase 4's existing provider classes.
- `livekit_client.py` — token minting, room teardown, webhook
  verification, all via LiveKit's own official SDK (`livekit.api`).
- `twilio_utils.py` — Twilio webhook signature validation via Twilio's
  own official SDK.
- `router.py` — Twilio status-callback webhook, LiveKit webhook, and a
  staff REST surface (list/detail/active/takeover/end), all under
  `/api/v1/voice`.
- `agent.py` — the actual LiveKit Agents worker process. `ResortVoiceAgent`
  overrides `llm_node()` to call `app.orchestration.pipeline.orchestrate()`
  directly — the same function webchat/WhatsApp already call — instead of
  wiring a LiveKit LLM plugin. This is the concrete implementation of
  "voice must become another channel that enters the existing
  orchestration pipeline."
- Migration `0030_voice_calls` — adds `'voice'` to
  `conversations.channel`, creates `voice_calls` with RLS. **Applied to
  the real production database** during this build.
- `app.conversations.constants.CHANNELS`, `app.orchestration.prompts.
  templates.channel_block` (new voice-specific phrasing: short, spoken,
  no markdown), `alembic/env.py`/`tests/conftest.py` model registration —
  all updated.

**Dashboard (`apps/dashboard`)**
- `/voice-calls` — active + historical calls list.
- `/voice-calls/[id]` — call detail: metadata, status, link to the full
  transcript (the existing `/conversations/{id}` page — not duplicated),
  and a `CallActionsPanel` client component using `livekit-client` for
  real browser-based audio takeover.
- New nav item ("Voice Calls"), 4 new API proxy routes.

**Dependencies added:** `twilio`, `livekit-agents`, `livekit-plugins-
deepgram`, `livekit-plugins-elevenlabs`, `livekit-plugins-openai`,
`livekit-client` (dashboard).

## Verified for real (see TESTING.md for the full list)

- Full voice-call lifecycle (`ringing` → `in_progress` → `completed`,
  with real `Customer`/`Conversation`/`VoiceCall` rows and duration
  computation) — run against the real production Supabase project, then
  cleaned up.
- Full FastAPI app import + OpenAPI schema includes all 7 new voice
  routes.
- `app.voice.agent` imports cleanly; `ResortVoiceAgent` constructs and
  reaches its intended, correct fail point without real credentials.
- Migration applied cleanly to production.
- Dashboard lint + build clean with the new pages and `livekit-client`.

## Explicit scope boundary (per the brief)

Built: incoming calls, AI receptionist, human handoff (reusing the
existing engine), existing RAG, existing orchestration, existing Customer
360, existing dashboard, existing audit logs, transcripts, interruption/
barge-in support (via LiveKit's own turn-taking + `allow_interruptions`),
graceful failure handling for every provider.

Not built (out of scope by explicit instruction): outbound calls, auto-
dialing, call campaigns, call blasting, cold calling, SMS, voicemail
drops, WhatsApp voice, India voice stack, multi-language voice routing,
CRM dialer.

## Known limitations / what genuinely requires real credentials

- No real inbound call has been placed — there are no Twilio/LiveKit/
  Deepgram/ElevenLabs accounts to test against yet. Every layer that
  doesn't need one has been verified for real; the parts that do (SIP
  audio path, live STT/TTS, live webhook signatures, live browser
  takeover audio) are built and structurally correct but unexercised.
- The exact SIP participant attribute keys LiveKit populates
  (`sip.phoneNumber` etc.) are based on LiveKit's documented SIP
  integration conventions, not verified against this specific project's
  eventual trunk/dispatch rule configuration — see TROUBLESHOOTING.md for
  how to confirm/adjust once real infra exists.
- `VOICE_ENABLED` exists as a settings field but nothing currently gates
  on it — there's no live traffic source until the Twilio/LiveKit console
  configuration in DEPLOYMENT.md is done, so it's documentation-only for
  now. Wire an explicit check before going live if a hard kill switch
  independent of provider configuration is wanted.

## Production readiness

Code-complete and structurally verified. Requires: real Twilio/LiveKit/
Deepgram/ElevenLabs accounts, the console configuration in
DEPLOYMENT.md, and one real end-to-end call test before this is actually
serving guests.
