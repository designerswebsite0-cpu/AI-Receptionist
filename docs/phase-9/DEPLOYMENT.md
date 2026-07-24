# Phase 9 — Deployment Guide

## Two processes, one codebase

Phase 9 adds a **second deployable process** alongside the existing
FastAPI API: the LiveKit Agents worker (`app.voice.agent`). It lives in the
same `apps/api` package (same `pyproject.toml`, same DB connection, same
`app.orchestration` pipeline) but must run as its own process — LiveKit
Agents workers use their own long-lived connection to LiveKit Cloud to
receive job dispatches, separate from FastAPI's request/response model.

```bash
# FastAPI API (existing, unchanged)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Voice agent worker (new)
python -m app.voice.agent start   # production
python -m app.voice.agent dev     # local dev, hot-reload
```

On Railway (or any platform-as-a-service host), this means **two
services** pointed at the same repo/image: the existing web service
(unchanged `uvicorn` start command) and a new worker service running the
`python -m app.voice.agent start` command, sharing the same environment
variables (including `DATABASE_URL`).

## Rollout order (once real credentials exist)

1. Set all Phase 9 env vars (ENVIRONMENT.md) on both services.
2. Deploy the worker service first, confirm it registers with LiveKit
   (`livekit.agents.cli`'s own startup logs show a successful worker
   registration) — no traffic reaches it yet since no SIP trunk points at
   it.
3. In LiveKit Cloud console: create the SIP inbound trunk, note its SIP
   URI, create the dispatch rule targeting `agent_name=
   "rkpr-voice-receptionist"`.
4. In Twilio console: create the Elastic SIP Trunk with that SIP URI as
   its Origination URI; set the phone number's Voice Status Callback URL
   to the deployed API's `/api/v1/voice/twilio/status`.
5. In LiveKit console: set the project webhook URL to the deployed API's
   `/api/v1/voice/livekit/webhook`.
6. Flip `VOICE_ENABLED=true` (currently only a documentation/intent flag —
   nothing in the router gates on it yet, since there's no real traffic
   source until the console config above exists; wire an explicit gate
   before going live if you want a hard kill switch independent of
   provider config).
7. Call the number. Watch `/voice-calls` in the dashboard.

## Scaling notes

- `WorkerOptions` defaults (`num_idle_processes`, `job_executor_type`) are
  left at LiveKit's own production defaults — tune only if call volume
  data says to.
- The worker process is stateless between calls (each job gets a fresh
  `ResortVoiceAgent` instance) — horizontal scaling is just running more
  worker instances/replicas.

## Rollback

Both migrations (`0030_voice_calls`, and the `conversations.channel`
constraint change it includes) have real `downgrade()` implementations —
`alembic downgrade 0029` cleanly removes the `voice_calls` table and
reverts the channel constraint, with no impact on existing whatsapp/
webchat conversations.
