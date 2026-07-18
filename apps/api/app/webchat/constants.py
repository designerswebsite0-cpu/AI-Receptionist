"""Pure data — see app.conversations.constants for the same pattern."""

SESSION_COOKIE_NAME = "rkpr_webchat_session"
SESSION_HEADER_NAME = "x-webchat-session-token"

# Bytes of entropy in the raw opaque session token before base64url encoding
# — 32 bytes (256 bits) is comfortably beyond brute-force range.
TOKEN_BYTES = 32

RATING_VALUES = ("up", "down")
