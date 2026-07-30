"""Notification fan-out: one durable in-app row + best-effort email and WhatsApp.

The in-app Notification is the source of truth every user sees in their notification
centre. Email (Resend) and WhatsApp (Twilio) are side channels: each is attempted only
when configured and never blocks or fails the caller — a dead channel is logged, not
raised. Notifications are always dispatched in the background off the request path.
"""
import uuid

import httpx

from ada.auth.mailer import send_email
from ada.config import get_settings
from ada.db.models import User
from ada.db.repositories import NotificationRepository, ProfileRepository
from ada.db.session import _session_factory
from ada.observability import log

_TWILIO_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


async def _send_whatsapp(phone: str, text: str) -> None:
    s = get_settings()
    if not (s.twilio_account_sid and s.twilio_auth_token and s.twilio_whatsapp_from):
        log.info("whatsapp_skipped_no_creds", to=phone)
        return
    to = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            _TWILIO_URL.format(sid=s.twilio_account_sid),
            data={"From": s.twilio_whatsapp_from, "To": to, "Body": text},
            auth=(s.twilio_account_sid, s.twilio_auth_token),
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"twilio {resp.status_code}: {resp.text[:160]}")


async def notify(
    user_id: str,
    *,
    kind: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
    email: bool = True,
    whatsapp: bool = True,
) -> None:
    """Record an in-app notification and fan out to email/WhatsApp. Best-effort:
    each channel is independent and its failure is logged, never propagated."""
    async with _session_factory() as session:
        await NotificationRepository(session).add(
            notification_id=uuid.uuid4().hex, user_id=user_id, kind=kind,
            title=title, body=body, link=link,
        )
        user = await session.get(User, user_id)
        profile = await ProfileRepository(session).get(user_id)

    if user is None:
        return
    full_link = _absolute(link)
    if email and user.email:
        try:
            await send_email(user.email, title, _email_html(title, body, full_link))
        except Exception as exc:  # noqa: BLE001 — side channel, never blocks
            log.warning("notify_email_failed", user_id=user_id, error=str(exc))
    phone = (profile.phone if profile else None) or None
    if whatsapp and phone:
        try:
            msg = f"{title}\n\n{body or ''}".strip()
            if full_link:
                msg += f"\n\n{full_link}"
            await _send_whatsapp(phone, msg)
        except Exception as exc:  # noqa: BLE001 — side channel, never blocks
            log.warning("notify_whatsapp_failed", user_id=user_id, error=str(exc))


async def connect_parties(
    *,
    candidate_email: str,
    candidate_name: str,
    employer_email: str,
    company: str,
    role_title: str,
) -> None:
    """Once a candidate accepts, send a warm two-way introduction email to both sides —
    the handoff that turns an accepted intro into an actual conversation. Best-effort;
    each side is independent and failures are logged, not raised."""
    to_candidate = (
        f"<p>Good news — you accepted <strong>{company}</strong>'s intro for "
        f"<strong>{role_title}</strong>.</p>"
        f"<p>You can reach them directly at <a href=\"mailto:{employer_email}\">"
        f"{employer_email}</a>. Just reply to say hello — they're expecting you.</p>"
        "<p>— Ada</p>"
    )
    to_employer = (
        f"<p><strong>{candidate_name}</strong> accepted your intro for "
        f"<strong>{role_title}</strong>.</p>"
        f"<p>Reach them at <a href=\"mailto:{candidate_email}\">{candidate_email}</a>. "
        "They've opted in and are happy to talk.</p>"
        "<p>— Uche</p>"
    )
    for to, subject, html in (
        (candidate_email, f"You're connected with {company}", to_candidate),
        (employer_email, f"{candidate_name} is ready to talk", to_employer),
    ):
        try:
            await send_email(to, subject, html)
        except Exception as exc:  # noqa: BLE001 — side channel, never blocks
            log.warning("connect_email_failed", to=to, error=str(exc))


def _absolute(link: str | None) -> str | None:
    if not link:
        return None
    if link.startswith("http"):
        return link
    return get_settings().frontend_base_url.rstrip("/") + link


def _email_html(title: str, body: str | None, link: str | None) -> str:
    parts = [f"<p><strong>{title}</strong></p>"]
    if body:
        parts.append(f"<p>{body}</p>")
    if link:
        parts.append(f'<p><a href="{link}">Open in Ada</a></p>')
    return "".join(parts)
