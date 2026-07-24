# Phase 9 — Call Flow

## Happy path (inbound call, AI handles it end to end)

1. **PSTN → Twilio.** A guest dials the resort's Twilio phone number.
2. **Twilio → LiveKit (SIP).** Twilio's Elastic SIP Trunk origination URI
   points at LiveKit Cloud's SIP endpoint. Audio flows Twilio → LiveKit
   directly — this backend is never in the audio path.
3. **Twilio status callback → `POST /api/v1/voice/twilio/status`.**
   Independently of the SIP audio path, Twilio calls this webhook on state
   changes (`ringing`, `in-progress`, `completed`, ...) with `CallSid`,
   `From`, `To`, `CallStatus`. Signature-validated
   (`app.voice.twilio_utils.validate_twilio_signature`). On the first
   `ringing` event, `app.voice.service.handle_incoming_call` resolves/
   creates the `Customer` by phone, creates a `Conversation`
   (`channel="voice"`), and creates a `VoiceCall` row — so the dashboard's
   Active Calls view shows the call immediately, even before LiveKit's
   agent has joined.
4. **LiveKit dispatches the agent.** LiveKit's SIP dispatch rule (console
   config) starts an `app.voice.agent` worker job for the new room.
5. **Agent connects, resolves call identity.** `entrypoint()` calls
   `ctx.connect()`, then `ctx.wait_for_participant()` for the SIP
   participant, and reads `sip.phoneNumber`/`sip.trunkPhoneNumber`/
   `sip.twilio.callSid` (or equivalent) off its `attributes` to match the
   `VoiceCall` row Twilio's status callback already created (falls back to
   creating one if no match — e.g. local testing without a real SIP call).
6. **Per-turn loop.** Deepgram Flux (`STTv2`) transcribes the caller's
   speech with its own end-of-turn detection
   (`AgentSession(turn_detection="stt")`). Each finalized utterance reaches
   `ResortVoiceAgent.llm_node`, which:
   - Persists the utterance via `app.messages.service.send_message`
     (`sender_type="customer"`) — same call every channel's turn makes.
   - Calls `app.orchestration.pipeline.orchestrate(..., channel="voice")`
     — RAG retrieval, intent/entity extraction, tool execution, response
     validation, handoff evaluation, all identical to text channels.
   - Returns `result.response_text`, which ElevenLabs Flash (`TTS`)
     speaks back to the caller.
7. **Call ends.** Either side hangs up → Twilio fires a `completed` status
   callback (`app.voice.service.mark_call_status` sets `status="completed"`,
   computes `duration_seconds`) and LiveKit's `add_shutdown_callback` in
   the agent does the same as a second, redundant write path (idempotent —
   both target the same row via `twilio_call_sid`).

## Escalation path (handoff required mid-call)

Same as above through step 6, except `orchestrate()`'s own handoff
evaluation (mandatory intents, tool-signaled handoff, repeated low
confidence, provider failure, etc.) calls
`app.conversations.service.change_status(new_status="escalated")`, which
flips `Conversation.ai_active` to `False`. On the next turn,
`ResortVoiceAgent.llm_node` sees `ai_active is False`: it speaks one
"let me get a team member for you" line, then goes silent on every
subsequent turn (never speaks again) until a human either takes over or
ends the call.

Meanwhile, the existing notification pipeline (`app.notifications.service.
notify`, called from inside `orchestrate()`'s handoff branch) puts a
"Guest needs human help" item in the dashboard exactly like it already does
for webchat.

## Staff takeover path

1. Staff opens the call in `/voice-calls/{id}` and clicks **Take over**.
2. `POST /api/v1/voice/calls/{id}/takeover` → `app.voice.service.
   takeover_call` forces the same escalation transition as above (so the
   agent goes silent even if no automatic handoff had triggered yet), then
   mints a LiveKit access token scoped to that call's room
   (`app.voice.livekit_client.mint_staff_token`).
3. The dashboard's `CallActionsPanel` (client component) uses
   `livekit-client` to connect the staff browser directly into the LiveKit
   room with that token and enables the staff member's microphone — from
   this point, the staff member's voice streams to the caller directly
   over WebRTC, with no involvement from the agent process.
4. Staff clicks **End call** →
   `POST /api/v1/voice/calls/{id}/end` → `app.voice.service.end_call` best-
   effort deletes the LiveKit room (`app.voice.livekit_client.end_room`,
   which also disconnects the caller's SIP leg) and marks the `VoiceCall`
   `completed`.

## Failure paths

See TROUBLESHOOTING.md for what each provider outage looks like from the
caller's side — the short version is: every provider call in
`ResortVoiceAgent.llm_node` is wrapped so a failure returns a plain
"Sorry, could you say that again?" line, never a raw error, matching the
existing `orchestrate()` guarantee for text channels
(`AllProvidersFailedError` → `_PROVIDER_FAILURE_ACKNOWLEDGMENT`).
