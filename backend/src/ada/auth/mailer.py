"""Email delivery over SMTP (e.g. Namecheap Private Email).

In local dev — or when SMTP credentials are missing — links and messages are
logged instead of sent, so every flow works without a mail account. smtplib is
synchronous; sends run in a worker thread to keep the event loop free.
"""
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr, parseaddr

from ada.config import get_settings
from ada.observability import log


def _send_sync(to: str, subject: str, html: str) -> None:
    s = get_settings()
    msg = MIMEText(html, "html", "utf-8")
    name, addr = parseaddr(s.email_from)
    msg["From"] = formataddr((name or None, addr or s.smtp_username))
    msg["To"] = to
    msg["Subject"] = subject
    if s.smtp_port == 465:
        server: smtplib.SMTP = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=20)
    else:
        server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20)
        server.starttls()
    try:
        server.login(s.smtp_username, s.smtp_password)
        server.sendmail(addr or s.smtp_username, [to], msg.as_string())
    finally:
        server.quit()


async def send_email(to: str, subject: str, html: str) -> None:
    """Generic SMTP delivery. Local dev (or missing creds) logs instead of sending;
    callers that must guarantee delivery let the raised error propagate."""
    s = get_settings()
    if s.app_env == "local" or not (s.smtp_username and s.smtp_password):
        log.info("email_local", to=to, subject=subject)
        return
    try:
        await asyncio.to_thread(_send_sync, to, subject, html)
    except Exception as exc:
        raise RuntimeError(f"smtp delivery failed: {exc}") from exc


async def send_reset_link(email: str, link: str) -> None:
    s = get_settings()
    if s.app_env == "local":
        log.info("reset_link_local", email=email, link=link)
        return
    await send_email(
        email,
        "Reset your Ada password",
        (
            "<p>We received a request to reset your Ada password. This link works once "
            "and expires in 30 minutes.</p>"
            f'<p><a href="{link}">Reset your password</a></p>'
            "<p>If you didn't request this, you can safely ignore this email — your "
            "password won't change.</p>"
        ),
    )
