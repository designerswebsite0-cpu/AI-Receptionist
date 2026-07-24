# Phase 9 — Troubleshooting

## `ValidationErrorApp: GROQ_API_KEY is not configured — the voice agent needs a real primary LLM.`

**Expected** with placeholder credentials — this is
`app.voice.providers.get_voice_llm_provider()` failing loudly on purpose,
the same way `app.orchestration.providers.get_llm_provider()` already does
for `OPENAI_API_KEY` on text channels. Set a real `GROQ_API_KEY` (and
ideally `OPENAI_API_KEY` as fallback) to resolve.

## Call rings but the dashboard never shows it

Check that the Twilio phone number's **Voice → Status Callback URL** is
actually set to `https://<your-api-host>/api/v1/voice/twilio/status` and
that the method is `POST`. `handle_incoming_call` only runs on the first
`ringing` status callback — if that webhook never arrives, no
`Conversation`/`VoiceCall` row is created, regardless of whether the SIP
audio path (Twilio → LiveKit) is working.

## Call connects but the AI never speaks

1. Check the agent worker's own logs for
   `livekit_agents` job-assignment/connection errors first — if the
   worker never picked up the job, confirm the LiveKit dispatch rule
   actually targets `agent_name="rkpr-voice-receptionist"` (must match
   `WorkerOptions(agent_name=...)` in `app.voice.agent` exactly).
2. If the worker did connect: check for a `voice_orchestrate_failed`
   log line — this means `orchestrate()` raised and the caller heard the
   generic fallback line instead. The real exception is in that log
   entry's traceback, not spoken to the caller (by design — see
   SECURITY.md).
3. Confirm `DEEPGRAM_API_KEY`/`ELEVENLABS_API_KEY` are set — a missing
   key surfaces as a provider connection error from the plugin itself,
   visible in the worker's logs, not as a Python exception from our code.

## Caller isn't recognized as a returning guest

Voice identity resolution depends on the SIP participant actually
carrying `sip.phoneNumber` in its `attributes` — this is set by LiveKit's
SIP integration based on the trunk/dispatch rule configuration. If the
attribute key differs from what `app.voice.agent._extract_sip_metadata`
reads (`sip.phoneNumber`, `sip.trunkPhoneNumber`, `sip.twilio.callSid`/
`sip.callID`), the call still works but is logged under an
`unknown:<participant-identity>` placeholder number and a **new** customer
record instead of the caller's real one — check the actual attribute keys
LiveKit populates for your specific SIP trunk/dispatch rule configuration
(these can vary by exact console setup) and adjust `_extract_sip_metadata`
if they differ.

## Staff "Take over" button doesn't connect audio

`CallActionsPanel` requires `configured: true` in the takeover response,
which requires **all** of: `LIVEKIT_URL`/`LIVEKIT_API_KEY`/
`LIVEKIT_API_SECRET` set, and the call's `VoiceCall.livekit_room_name`
already populated (only true once the agent has actually joined a room —
a call still in `ringing` status, before the agent connects, has no room
yet). The panel surfaces this exact reason in its error message rather
than failing silently.

## LiveKit/Twilio webhook returns 401

Check `X-Twilio-Signature` (Twilio) or `Authorization` (LiveKit) headers
are reaching the app unmodified — a reverse proxy or load balancer that
strips or rewrites these headers will break signature validation even
with correct secrets configured. Confirm the exact public URL configured
in Twilio/LiveKit consoles matches what the app sees as `request.url`
(the signature covers the full URL, so a mismatched scheme/host — e.g.
`http` vs `https` behind a proxy — breaks validation).

## Local development without any real credentials

Everything up through `import app.voice.agent` and `import app.main`
works with zero Phase 9 env vars set — use this to catch import/syntax
regressions without needing any account. Actually invoking
`ResortVoiceAgent(...)` or running the worker (`python -m app.voice.agent
dev`) requires at least `GROQ_API_KEY` to get past construction.
