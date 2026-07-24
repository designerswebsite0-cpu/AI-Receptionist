# Phase 9 — Environment Variables

All optional. The app (both the FastAPI process and the separate voice
agent worker process) boots fine with every one of these blank; only
actually placing/receiving a real call requires them. See
PROVIDER_INTEGRATION.md for what each one is used for and how to obtain it.

```env
# Feature flag — kept False until a real deployment is ready to receive calls.
VOICE_ENABLED=false

# Twilio — telephony (Elastic SIP Trunking carries audio to LiveKit directly)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=

# LiveKit Cloud — realtime media + SIP + Agents framework
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=

# Deepgram — speech-to-text (Flux model, built-in turn detection)
DEEPGRAM_API_KEY=

# ElevenLabs — text-to-speech (Flash model, lowest latency)
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=

# LLM — reuses GROQ_API_KEY/OPENAI_API_KEY from Phase 4 (app.config.Settings)
# already present in .env.example; voice orders them Groq-primary/OpenAI-
# fallback (the reverse of text channels — see PROVIDER_INTEGRATION.md).
```

## Where these live in code

All of the above are fields on `app.config.Settings` (see the "Phase 9:
Global Voice Call System" section of `apps/api/app/config.py`) — every
field is `str | None = None` (or `bool = False` for `VOICE_ENABLED`), so
`Settings()` constructs successfully with none of them set. Nothing in
`app.voice` reads `os.environ` directly; everything goes through
`get_settings()`, matching the rest of the codebase.

## Safety caps (not credentials, but configured alongside them)

- `voice_max_call_duration_seconds` (default 1800 / 30 min)
- `voice_silence_timeout_seconds` (default 30)
- `booking_max_advance_days` (Phase 7, unrelated but adjacent in
  `config.py`) is not a voice setting — listed here only to avoid
  confusion since it's nearby in the file.
