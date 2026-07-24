"""Guest SMS confirmation — sent only from app.bookings.service.confirm_booking,
never from the AI turn itself (the brief requires a human to double-check
before any message goes out). Twilio is optional infrastructure: if the
three settings aren't all present (e.g. TWILIO_FROM_NUMBER not yet
provisioned), send_booking_confirmation_sms logs and returns a
"skipped_not_configured" result instead of raising, so staff can still
confirm a booking in the dashboard before SMS is fully wired up.
"""

from dataclasses import dataclass

from app.config import get_settings
from app.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class SmsResult:
    status: str  # "sent" | "failed" | "skipped_not_configured"
    error: str | None = None


def _build_message(*, guest_name: str, room_type_name: str, check_in_date: str, check_out_date: str) -> str:
    first_name = guest_name.split(" ")[0] if guest_name else "there"
    return (
        f"Hi {first_name}, this is RKPR Resort. Your {room_type_name} booking for "
        f"{check_in_date} to {check_out_date} is confirmed. We look forward to hosting you!"
    )


def send_booking_confirmation_sms(
    *, guest_phone: str, guest_name: str, room_type_name: str, check_in_date: str, check_out_date: str
) -> SmsResult:
    settings = get_settings()
    if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number):
        logger.warning("booking_confirmation_sms_skipped_not_configured", extra={"guest_phone": guest_phone})
        return SmsResult(status="skipped_not_configured")

    try:
        from twilio.base.exceptions import TwilioRestException
        from twilio.rest import Client
    except ImportError:
        logger.exception("twilio_sdk_not_installed")
        return SmsResult(status="failed", error="Twilio SDK not installed")

    body = _build_message(
        guest_name=guest_name,
        room_type_name=room_type_name,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
    )
    try:
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(to=guest_phone, from_=settings.twilio_from_number, body=body)
        return SmsResult(status="sent")
    except TwilioRestException as exc:
        logger.exception("booking_confirmation_sms_failed", extra={"guest_phone": guest_phone})
        return SmsResult(status="failed", error=str(exc))
