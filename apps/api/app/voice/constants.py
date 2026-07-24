"""Pure data — no engine imports, mirrors app.bookings.constants' pattern.

Phase 9: Global Voice Call System (inbound only). A VoiceCall row is
call-specific metadata (Twilio/LiveKit identifiers, timing, outcome) that
doesn't belong on Conversation/Message — the actual conversation content
(what was said) stays in the existing conversations/messages tables with
channel='voice', exactly like every other channel, per the 2026-07-24
brief's "do not duplicate the conversation system" requirement.
"""

VOICE_CALL_STATUSES = ("ringing", "in_progress", "completed", "failed", "no_answer")

# Free-form-ish outcome bucket for reporting — set once, at call end, by
# whichever of app.voice.service's ending paths actually applies.
VOICE_CALL_OUTCOMES = ("ai_handled", "escalated", "staff_handled", "failed", "abandoned")

# Inbound only in this phase (2026-07-24 brief: "Do NOT build outbound
# calls"). The column still exists so a later phase can add "outbound"
# without a schema change — see docs/phase-9/ARCHITECTURE.md.
VOICE_CALL_DIRECTIONS = ("inbound",)
