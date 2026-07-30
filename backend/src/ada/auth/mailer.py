"""Password-reset email delivery via the Resend HTTP API.

In local dev the link is logged instead of sent, so the flow works without a
provider account.
"""
import httpx

from ada.config import get_settings
from ada.observability import log

_RESEND_URL = "https://api.resend.com/emails"


async def send_email(to: str, subject: str, html: str) -> None:
    """Generic Resend delivery. Local dev logs instead of sending; a missing key
    logs and returns (callers that must guarantee delivery check status themselves)."""
    s = get_settings()
    if s.app_env == "local" or not s.resend_api_key:
        log.info("email_local", to=to, subject=subject)
        return
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            _RESEND_URL,
            json={"from": s.email_from, "to": [to], "subject": subject, "html": html},
            headers={"Authorization": f"Bearer {s.resend_api_key}"},
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"resend delivery failed: {resp.status_code} {resp.text[:200]}")


async def send_reset_link(email: str, link: str) -> None:
    s = get_settings()
    if s.app_env == "local":
        log.info("reset_link_local", email=email, link=link)
        return
    payload = {
        "from": s.email_from,
        "to": [email],
        "subject": "Reset your Ada password",
        "html": (
            "<p>We received a request to reset your Ada password. This link works once "
            "and expires in 30 minutes.</p>"
            f'<p><a href="{link}">Reset your password</a></p>'
            "<p>If you didn't request this, you can safely ignore this email — your "
            "password won't change.</p>"
        ),
    }
    headers = {"Authorization": f"Bearer {s.resend_api_key}"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(_RESEND_URL, json=payload, headers=headers)
    if resp.status_code >= 400:
        # Surface delivery failure to the caller; the route converts it to a 502.
        raise RuntimeError(f"resend delivery failed: {resp.status_code} {resp.text[:200]}")
