"""Pure data — no engine imports, mirrors app.service_requests.constants'
pattern. This is the real Phase 7 room-booking domain: a dedicated
room_types + room_bookings pair of tables (per the 2026-07-24 brief's
explicit "enter into a different table" requirement), replacing the old
Stage 5 ServiceRequest-based booking_enquiry triage — that generic table
still exists and still serves dining/spa/activity/transfer/complaint
enquiries (app.service_requests), just no longer room bookings.
"""

BOOKING_STATUSES = ("pending_review", "confirmed", "rejected", "cancelled")

# Only statuses that actually hold a room count against inventory — a
# rejected/cancelled booking must not block a later guest from booking the
# same room/dates.
ACTIVE_BOOKING_STATUSES = ("pending_review", "confirmed")

SMS_STATUSES = ("sent", "failed", "skipped_not_configured")
