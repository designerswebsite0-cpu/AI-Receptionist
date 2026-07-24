"""Validates that a webhook claiming to be from Twilio actually is — every
inbound Twilio webhook this app exposes must call this before touching the
database, per the 2026-07-24 brief's "Validate every webhook" requirement.
"""

from fastapi import Request
from twilio.request_validator import RequestValidator


def validate_twilio_signature(request: Request, *, auth_token: str, params: dict) -> bool:
    signature = request.headers.get("X-Twilio-Signature", "")
    validator = RequestValidator(auth_token)
    return validator.validate(str(request.url), params, signature)
