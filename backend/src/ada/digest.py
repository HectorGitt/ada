"""Proactive digest — Ada reaches out with fresh best-fit roles.

Scheduled as a Cloud Run Job: `python -m ada.digest`. For each candidate who has a
profile vector, KNN the current jobs pool; if there are matches, send a digest across
in-app + email + WhatsApp. Throttled per candidate (a re-run inside the cooldown is a
no-op), so it's safe to schedule liberally. Reads the local jobs table only — never a
live job API.
"""
import asyncio
from datetime import UTC, datetime, timedelta

from ada.auth.mailer import send_email
from ada.config import get_settings
from ada.db.models import Profile
from ada.db.repositories import JobRepository, NotificationRepository, ProfileRepository
from ada.db.session import _session_factory
from ada.observability import configure_logging, log
from ada.services.notify import notify

DIGEST_KIND = "digest"


def _match_pct(distance: float) -> int:
    return max(0, min(100, round((1.0 - distance) * 100)))


def _within_cooldown(last: datetime | None, cooldown_seconds: int) -> bool:
    if last is None:
        return False
    return datetime.now(UTC) - last < timedelta(seconds=cooldown_seconds)


def _role_li(role: dict) -> str:
    parts = [f'<strong>{role["title"]}</strong> · {role["company"]}',
             f' — <span style="color:#4338ca">{role["match"]}% match</span>']
    if role.get("location"):
        parts.append(f' · {role["location"]}')
    if role.get("url"):
        parts.append(f' · <a href="{role["url"]}">view</a>')
    return '<li style="margin:0 0 10px">' + "".join(parts) + "</li>"


def _email_html(name: str, roles: list[dict]) -> str:
    items = "".join(_role_li(r) for r in roles)
    return (
        f"<p>Hi {name},</p>"
        f"<p>I went through this week's roles and found {len(roles)} that fit your "
        "background:</p>"
        f'<ul style="padding-left:18px">{items}</ul>'
        "<p>Open Ada to run any of them — I'll tailor your CV and prep the interview.</p>"
        "<p>— Ada</p>"
    )


async def _digest_for_candidate(profile: Profile) -> bool:
    s = get_settings()
    async with _session_factory() as session:
        notifs = NotificationRepository(session)
        last = await notifs.last_of_kind(profile.user_id, DIGEST_KIND)
        if _within_cooldown(last, s.digest_cooldown_seconds):
            return False
        if profile.embedding is None:
            return False
        rows = await JobRepository(session).knn(list(profile.embedding), s.digest_matches)

    roles = [
        {
            "title": job.title, "company": job.company, "location": job.location,
            "url": job.url, "match": _match_pct(dist),
        }
        for job, dist in rows
    ]
    if not roles:
        return False

    name = (profile.full_name or "there").split()[0]
    top = roles[0]
    summary = (
        f"{len(roles)} new roles fit you — top: {top['title']} at {top['company']} "
        f"({top['match']}% match)."
    )
    # in-app + WhatsApp via notify (short); the rich role list goes out as its own email.
    await notify(
        profile.user_id, kind=DIGEST_KIND, title="Fresh roles that fit you",
        body=summary, link="/app/new", email=False,
    )
    try:
        user_email = await _user_email(profile.user_id)
        if user_email:
            await send_email(user_email, "Your weekly roles from Ada", _email_html(name, roles))
    except Exception as exc:  # noqa: BLE001 — side channel, never blocks the sweep
        log.warning("digest_email_failed", user_id=profile.user_id, error=str(exc))
    return True


async def _user_email(user_id: str) -> str | None:
    from ada.db.models import User

    async with _session_factory() as session:
        user = await session.get(User, user_id)
        return user.email if user else None


async def run_digest(limit: int | None = None) -> int:
    """Send the digest to every eligible candidate; returns how many were sent."""
    async with _session_factory() as session:
        candidates = await ProfileRepository(session).list_embedded_candidates(
            limit=limit or 500
        )
    sent = 0
    for profile in candidates:
        try:
            if await _digest_for_candidate(profile):
                sent += 1
        except Exception as exc:  # noqa: BLE001 — one bad candidate never stops the sweep
            log.warning("digest_candidate_failed", user_id=profile.user_id, error=str(exc))
    return sent


def main() -> None:
    configure_logging()
    n = asyncio.run(run_digest())
    log.info("digest_sweep", sent=n)
    print(f"sent {n} digests")


if __name__ == "__main__":
    main()
