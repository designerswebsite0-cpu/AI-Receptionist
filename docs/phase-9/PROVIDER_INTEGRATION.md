# Phase 9 — Provider Integration

No production credentials exist for any provider below (2026-07-24 brief).
Every integration point is optional at the `Settings` level and every code
path degrades to a clear, loud, non-crashing error (never a silent
fallback, never a raw stack trace to a caller) when unconfigured — this
document is what to fill in once real accounts exist.

## Twilio (telephony)

- **What it's for:** carries the PSTN call in; Elastic SIP Trunking hands
  audio to LiveKit directly (see ARCHITECTURE.md) — this app never proxies
  audio.
- **Settings:** `twilio_account_sid`, `twilio_auth_token`,
  `twilio_phone_number` (the number callers dial — distinct from
  `twilio_from_number`, Phase 7's SMS sender number).
- **Console setup (once real credentials exist):**
  1. Buy/port a phone number.
  2. Create an Elastic SIP Trunk; set its Origination URI to LiveKit
     Cloud's SIP endpoint for your project (LiveKit console provides this
     once a SIP inbound trunk is created there — see LiveKit below).
  3. On the phone number, set **Voice → Status Callback URL** to
     `https://<your-api-host>/api/v1/voice/twilio/status` (method `POST`).
- **Code:** `app.voice.twilio_utils.validate_twilio_signature` (every
  webhook validated), `app.voice.router.twilio_status_callback`.

## LiveKit Cloud (realtime + SIP + Agents)

- **What it's for:** the actual WebRTC/SIP media server, and the framework
  the agent worker (`app.voice.agent`) runs on.
- **Settings:** `livekit_url`, `livekit_api_key`, `livekit_api_secret`.
- **Console setup:**
  1. Create a project; note its WS URL and an API key/secret pair.
  2. Create a **SIP inbound trunk** (LiveKit console) — this is what
     produces the SIP URI to give Twilio's Elastic SIP Trunk as its
     Origination URI.
  3. Create a **dispatch rule** pointing inbound SIP calls at the agent
     registered under `agent_name="rkpr-voice-receptionist"`
     (`app.voice.agent`'s `WorkerOptions`).
  4. Set the project's webhook URL to
     `https://<your-api-host>/api/v1/voice/livekit/webhook`.
- **Code:** `app.voice.livekit_client` (token minting, room teardown,
  webhook signature verification via `livekit.api.WebhookReceiver`),
  `app.voice.agent` (the worker itself, via `livekit.agents.cli`).

## Deepgram (speech-to-text — Flux)

- **Settings:** `deepgram_api_key`.
- **Model:** `flux-general-en` via `livekit.plugins.deepgram.STTv2` — Flux
  is Deepgram's turn-detection-aware realtime model, used specifically so
  end-of-turn detection doesn't require a separate VAD plugin (see
  ARCHITECTURE.md's "Why no VAD plugin").
- **Code:** `app.voice.agent.entrypoint` constructs the `STTv2` instance.

## ElevenLabs (text-to-speech — Flash)

- **Settings:** `elevenlabs_api_key`, `elevenlabs_voice_id` (a real voice
  ID from your ElevenLabs account — falls back to a public sample voice
  ID if unset, purely so the code path doesn't crash without one).
- **Model:** `eleven_flash_v2_5` via `livekit.plugins.elevenlabs.TTS` —
  ElevenLabs' lowest-latency model, matching "Flash" in the brief.
- **Code:** `app.voice.agent.entrypoint` constructs the `TTS` instance.

## Groq (primary LLM) / OpenAI 4o-mini (fallback LLM)

- **Settings:** reuses `groq_api_key`/`groq_model` and `openai_api_key`/
  `openai_model` from Phase 4 — no new settings.
- **Ordering:** voice is Groq-primary/OpenAI-fallback, the **reverse** of
  webchat/WhatsApp's OpenAI-primary/Groq-fallback (architecture.md §4.4) —
  the brief specifies this explicitly, presumably for Groq's lower
  inference latency mattering more on a live call than in chat.
- **Code:** `app.voice.providers.get_voice_llm_provider` — reuses the same
  `GroqLLMProvider`/`OpenAILLMProvider`/`FallbackLLMProvider` classes
  Phase 4 already built, just constructed in the opposite order.
- **Fails loudly, not silently:** if `GROQ_API_KEY` is unset,
  `get_voice_llm_provider()` raises `ValidationErrorApp` immediately on
  agent construction — mirrors `app.orchestration.providers.
  get_llm_provider`'s own precedent for text channels. This is the
  expected, correct behavior with placeholder credentials, not a bug.

## What "compiles cleanly without credentials" actually means here

`import app.voice.agent`, every class definition, and the full FastAPI app
(`import app.main`) all succeed today with every Phase 9 setting unset.
Actually **running** a call requires real Groq/Deepgram/ElevenLabs/LiveKit
credentials, same as running a real webchat conversation has always
required a real `OPENAI_API_KEY` — that's a runtime configuration
requirement, not a code defect.
