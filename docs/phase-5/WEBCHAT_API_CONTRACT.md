# Phase 5 — Website Chat API Contract

Two layers exist. **Guest-facing code only ever calls layer 1.**

- **Layer 1 — same-origin, browser-facing**: `apps/website`'s own Next.js
  Route Handlers under `/api/webchat/*`. No auth header required (session
  state is an `HttpOnly` cookie the browser can't read but automatically
  resends).
- **Layer 2 — server-to-server, FastAPI**: `/api/v1/webchat/*`, called only
  by `apps/website`'s own server code
  (`apps/api/app/webchat/router.py`). Documented here for completeness and
  for anyone deploying a different frontend against the same backend.

All responses use this platform's existing envelope
(`docs/api.md`): `{"success": true, "data": ...}` or
`{"success": false, "error": {"code": "...", "message": "..."}}`.

## Layer 1 — `apps/website` Route Handlers (what the widget actually calls)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/webchat/session` | Restore an existing session from cookies, or `{exists: false}` |
| POST | `/api/webchat/session` | Create a new anonymous session; sets cookies |
| DELETE | `/api/webchat/session` | End the session; clears cookies |
| POST | `/api/webchat/messages` | Send a guest message, get the AI/handoff response |
| GET | `/api/webchat/messages?page=&page_size=` | Transcript (restore-after-refresh, polling) |
| POST | `/api/webchat/handoff` | Guest-initiated "speak to staff" |
| POST | `/api/webchat/feedback` | Thumbs up/down on a reply |
| POST | `/api/webchat/contact` | Optional contact capture |

A request made before a session cookie exists returns HTTP `440`
(a widely-used, if non-standard, "session required" convention) with
`error.code = "SESSION_REQUIRED"` — the widget's client
(`webchat-client.ts`) treats this as a signal to call
`POST /api/webchat/session` first, then retry.

### `POST /api/webchat/session` response

```json
{
  "success": true,
  "data": {
    "session_id": "b3f5...",
    "conversation_id": "9e21...",
    "current_state": "greeting",
    "flow_state": null,
    "status": "open",
    "ai_active": true,
    "human_active": false
  }
}
```

(The raw session token is never in this body — only in the `HttpOnly`
cookie the Next.js server just set.)

### `POST /api/webchat/messages` request / response

Request:
```json
{ "message": "What time is check-in?", "client_message_id": "b1b6b6d2-..." }
```

`client_message_id` is optional but recommended — a client-generated UUID
that makes a retried/double-clicked send idempotent (see
`WEBCHAT_ARCHITECTURE.md`).

Response:
```json
{
  "success": true,
  "data": {
    "message_id": "1a2b...",
    "response_text": "Check-in begins at 2:00 PM.",
    "citations": [
      { "source_title": "RKPR Resort Guest Policies", "source_priority": "verified", "authoritative": true }
    ],
    "handoff": { "required": false, "status": "none", "department": null },
    "ai_active": true,
    "human_active": false,
    "flow_state": "general_enquiry",
    "error_code": null
  }
}
```

`handoff.status` is one of `"none" | "requested" | "active"`. `citations`
never includes an internal chunk id, vector id, or relevance score.

### `POST /api/webchat/handoff`

Request: `{ "reason": "Guest requested to speak with a staff member." }`
(optional — defaults to a generic reason). Response mirrors the session
state shape, with `status: "escalated"`.

### `POST /api/webchat/contact`

Request:
```json
{ "full_name": "Asha Guest", "phone": "+91 90000 11111", "email": null, "marketing_consent": true }
```
At least one of `phone`/`email` is required. Response is always the same
generic success message regardless of whether the contact was new or
already belonged to an existing guest (brief §8 — never confirms/denies
existence).

### `POST /api/webchat/feedback`

Request: `{ "turn_id": null, "rating": "up", "comment": "Great!" }`.
`rating` is `"up" | "down"`.

## Layer 2 — FastAPI `/api/v1/webchat/*` (server-to-server only)

Identical resource shapes to layer 1, but:
- Auth is a header, not a cookie: `X-Webchat-Session-Token: <raw token>`
  (a cookie named `rkpr_webchat_session` is also accepted, for a
  same-origin deployment that skips the Next.js proxy layer entirely).
- `POST /api/v1/webchat/sessions` returns the raw `token` once in the
  response body — the caller (the website's server) is responsible for
  turning that into a cookie; this endpoint itself sets no cookie meant
  for a cross-origin browser.

| Method | Path |
|---|---|
| POST | `/api/v1/webchat/sessions` |
| GET | `/api/v1/webchat/sessions/{session_id}` |
| DELETE | `/api/v1/webchat/sessions/{session_id}` |
| POST | `/api/v1/webchat/sessions/{session_id}/messages` |
| GET | `/api/v1/webchat/sessions/{session_id}/messages` |
| POST | `/api/v1/webchat/sessions/{session_id}/handoff` |
| POST | `/api/v1/webchat/sessions/{session_id}/feedback` |
| POST | `/api/v1/webchat/sessions/{session_id}/contact` |

`{session_id}` in the path is never itself an authorization check — see
`WEBCHAT_ARCHITECTURE.md`'s "Session model" section.

## Error codes a guest-facing client should handle

| HTTP | `error.code` | Meaning | Suggested guest-facing copy |
|---|---|---|---|
| 401 | `UNAUTHORIZED` | Missing/invalid/expired/revoked session token | Silently start a new session and retry once |
| 404 | `NOT_FOUND` | Webchat disabled, or session/path mismatch | "This chat isn't available right now" |
| 422 | `VALIDATION_ERROR` | Message too long, malformed contact fields, etc. | Field-specific message already in `error.message` |
| 429 | `RATE_LIMITED` | Per-session or per-IP limit hit | "You're sending messages a little quickly — please wait a moment" |
| 440 (layer 1 only) | `SESSION_REQUIRED` | No session cookie yet | Handled transparently by `ensureSession()` |
| 500 | `INTERNAL_ERROR` | Anything unexpected (including DB/provider failures) | "Something went wrong — please try again, or call reception at &lt;phone&gt;" |

Rate limits are configuration, not magic numbers in code — see
`WEBCHAT_DEPLOYMENT.md` for the `WEBCHAT_*` environment variables.

## Updates to existing documentation

`docs/api.md` gained a "Website Chat (Phase 5)" section pointing back to
this file rather than duplicating it in full.
