"""Pure data — no engine imports, mirrors app.conversations.constants' pattern.

Notifications (Phase X Stage 6) are a resort-wide shared feed, not
per-recipient — matching the rest of this single-resort deployment (no
tenant/role scoping anywhere else either): any staff member sees every
notification, and any staff member can mark one read for everyone, the
same way any staff member can pick up any conversation in the Inbox.
"""

NOTIFICATION_TYPES = (
    "handoff_required",
    "booking_enquiry_received",
    "knowledge_ingestion_failed",
    "feedback_received",
    "room_booking_received",
)
