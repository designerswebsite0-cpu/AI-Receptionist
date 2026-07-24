# Phase 9 — Global Voice Call System: Architecture

Global inbound-only voice receptionist. India-specific voice work is out of
scope entirely — this phase never designs, mentions, or prepares for it.

## Design principle

Voice is another **channel**, not a second AI system. Every other channel
(webchat, WhatsApp) calls one shared entrypoint —
`app.orchestration.pipeline.orchestrate()` — for intent detection, RAG
retrieval, prompt building, tool execution, response validation, and
handoff decisions. Voice calls the exact same function. Nothing about RAG,
the prompt architecture, tool registry, or handoff engine is duplicated or
reimplemented for voice.

Concretely: `app.voice.agent.ResortVoiceAgent` (a LiveKit `Agent` subclass)
overrides `llm_node()` — the extension point LiveKit Agents exposes for
replacing its default STT→LLM→TTS wiring — to call `orchestrate()` with
`channel="voice"` and return `result.response_text` as plain text, which
LiveKit's TTS stage then speaks. No LiveKit LLM plugin is used; Groq/OpenAI
selection, RAG, and tool execution all happen exactly where they already
happen for text channels.

## Data model

- **Conversation** (existing table): gets a new allowed `channel` value,
  `'voice'`. A voice call's turn-by-turn content lives here and in
  **Message** exactly like every other channel — never duplicated.
- **VoiceCall** (new table, `app.voice.models.VoiceCall`): call-specific
  metadata that doesn't belong on Conversation/Message — Twilio CallSid,
  LiveKit room name, from/to numbers, status, timing, duration, outcome.
  One row per call, FK to the Conversation it drove.

## Components

| Component | Role | Package |
|---|---|---|
| Twilio Elastic SIP Trunk | Carries call audio from the PSTN to LiveKit | n/a (Twilio console config) |
| LiveKit Cloud (SIP + Agents) | Receives the SIP call, dispatches the agent worker into a room | `livekit`, `livekit-agents` |
| `app.voice.agent` | The agent worker process — STT→(orchestrate)→TTS per turn | `livekit-agents`, `livekit-plugins-deepgram`, `livekit-plugins-elevenlabs` |
| Deepgram Flux | Speech-to-text, with built-in end-of-turn/endpointing detection | `livekit-plugins-deepgram` (`STTv2`, model `flux-general-en`) |
| ElevenLabs Flash | Text-to-speech | `livekit-plugins-elevenlabs` (`TTS`, model `eleven_flash_v2_5`) |
| Groq (primary) / OpenAI 4o-mini (fallback) | The LLM `orchestrate()` itself calls | `app.voice.providers.get_voice_llm_provider` |
| FastAPI `app.voice.router` | Twilio status-callback + LiveKit webhook receivers, staff REST API | part of the main API process |
| Dashboard `/voice-calls` | Active/completed calls, transcript link, takeover, end | `apps/dashboard` |

The agent worker (`app.voice.agent`) is a **separate process** from the
FastAPI app — see DEPLOYMENT.md. It imports `app` package modules directly
(same DB, same orchestration pipeline) rather than calling the API over
HTTP, since it runs inside the same deployment.

## Why no VAD plugin

`livekit-plugins-silero` (LiveKit's usual local VAD) depends on
`onnxruntime`, which has no wheel for this dev environment's Python 3.14
(production runs 3.12, where it would resolve fine). Rather than take that
dependency, `AgentSession(turn_detection="stt", ...)` is used instead —
Deepgram Flux does end-of-turn detection server-side (`eot_threshold`/
`eot_timeout_ms` on `STTv2`), which is both simpler and avoids the
dependency entirely. This is a deliberate simplification, not a missing
feature; a local VAD can be added later without touching orchestration.

## Human handoff

Zero new logic. `orchestrate()` already flips a conversation's `ai_active`
to `False` via `app.conversations.service.change_status` the moment
handoff is required (mandatory intents, tool-signaled handoff, provider
failure, etc.) — the exact same path text channels use. `ResortVoiceAgent.
llm_node` checks `conversation.ai_active` before generating a reply on
every turn; once false, it goes silent (after one "let me get a team
member" line) instead of speaking. `app.voice.service.takeover_call` also
lets staff force this directly from the dashboard, reusing the identical
`change_status`/`change_dialogue_state` calls
`app.orchestration.router.force_handoff` already uses for text.

Staff audio join is real-time, browser-based: `takeover_call` mints a
scoped LiveKit access token (`app.voice.livekit_client.mint_staff_token`)
for the specific call's room, and the dashboard's `CallActionsPanel`
component uses `livekit-client` (the JS SDK) to connect the staff member's
browser microphone directly into the same LiveKit room the caller is in.

## Conversation memory / Customer 360

A caller is resolved via `app.customers.repository.find_customer_by_contact`
against their `from_number` — the same phone-based identity resolution
Customer 360 already uses — so a repeat caller is recognized exactly like
a repeat webchat guest who provided a phone number. No second identity
system.

## What this phase deliberately does not build

Outbound calls, auto-dialing, call campaigns, cold calling, voicemail
drops, SMS (that's Phase 7), WhatsApp voice, multi-language voice routing,
a CRM dialer, or anything India-specific. See PHASE_9_COMPLETION_REPORT.md
for the explicit scope boundary this was verified against.
