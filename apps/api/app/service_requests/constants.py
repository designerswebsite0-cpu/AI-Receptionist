"""Pure data — no engine imports, mirrors app.conversations.constants' pattern.

Booking Management (Phase X Stage 5) is a thin, scoped read/update surface
over the existing app.orchestration.models.ServiceRequest table — see
architecture note in app/service_requests/service.py. `BOOKING_STATUSES` is
a staff-facing vocabulary stored inside ServiceRequest.details (JSONB), kept
deliberately separate from ServiceRequest's own generic `status` column
(open/in_progress/resolved/cancelled, shared across every enquiry type) so
neither vocabulary constrains the other.
"""

BOOKING_REQUEST_TYPE = "booking_enquiry"

BOOKING_STATUSES = ("pending_review", "confirmed", "rejected", "completed")
