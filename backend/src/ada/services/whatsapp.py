"""Inbound WhatsApp helpers — verify it's really Twilio, read the candidate's reply.

Pure functions (no FastAPI, no DB) so they're trivially testable and the webhook route
stays thin.
"""
import base64
import hashlib
import hmac
import re

# Words that mean "yes, connect me" / "no, pass" — matched on the first token so
# "YES please" and "no thanks" both read correctly.
_ACCEPT = {"yes", "y", "accept", "ok", "okay", "sure", "connect", "1"}
_DECLINE = {"no", "n", "decline", "pass", "stop", "2"}


def verify_twilio_signature(
    *, auth_token: str, url: str, params: dict[str, str], signature: str
) -> bool:
    """Twilio signs each webhook: HMAC-SHA1 over the full URL with POST params appended
    in key-sorted order, base64-encoded. Recompute and compare in constant time."""
    if not (auth_token and signature):
        return False
    data = url + "".join(k + params[k] for k in sorted(params))
    digest = hmac.new(auth_token.encode(), data.encode("utf-8"), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, signature)


def parse_reply(body: str) -> str | None:
    """'accept' / 'decline' from a free-text reply, or None if it's neither."""
    first = re.sub(r"[^a-z0-9]", "", body.strip().lower().split()[0]) if body.strip() else ""
    if first in _ACCEPT:
        return "accept"
    if first in _DECLINE:
        return "decline"
    return None


def phone_digits(raw: str) -> str:
    """Trailing national digits of a phone number, for matching a stored profile phone
    against Twilio's E.164 `From` regardless of '+', country code, or formatting."""
    digits = re.sub(r"\D", "", raw)
    return digits[-10:] if len(digits) >= 10 else digits
