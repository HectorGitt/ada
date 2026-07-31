"""Intro responses — the shared accept/decline path.

A candidate can answer an intro from the app (a button) or from WhatsApp (a reply). Both
land here so the consequences — notifying the employer, and, on accept, the warm two-way
introduction email — happen once, identically, wherever the answer came from.
"""
from collections.abc import Callable
from typing import Any

from ada.db.models import Intro, IntroStatus, User
from ada.db.repositories import IntroRepository, JobRepository, ProfileRepository
from ada.db.session import _session_factory
from ada.services.notify import connect_parties, notify

# A scheduler for the side effects — BackgroundTasks.add_task, so they run off the
# response path. Kept abstract so this service never imports FastAPI.
Scheduler = Callable[..., Any]


async def respond_to_intro(
    *, intro: Intro, responder_id: str, status: IntroStatus, schedule: Scheduler
) -> bool:
    """Move the intro (owner-scoped, REQUESTED-only) and fan out the consequences.

    Returns False if it couldn't move — not this candidate's, or already answered — so the
    caller can 404 / reply "already handled". Side effects are handed to `schedule` so they
    run off the response path.
    """
    async with _session_factory() as session:
        moved = await IntroRepository(session).respond(intro.id, responder_id, status)
        if not moved:
            return False
        profile = await ProfileRepository(session).get(responder_id)
        who = (profile.full_name if profile else None) or "A candidate"
        candidate = await session.get(User, responder_id)
        employer = await session.get(User, intro.employer_id)
        job = await JobRepository(session).get(intro.job_id)

    if status == IntroStatus.ACCEPTED:
        schedule(
            notify, intro.employer_id, kind="intro_accepted",
            title=f"{who} accepted your intro",
            body="They're open to talking — their contact is on the intro in your console.",
            link="/hire/intros",
        )
        if candidate is not None and employer is not None and job is not None:
            schedule(
                connect_parties,
                candidate_email=candidate.email,
                candidate_name=who,
                employer_email=employer.email,
                company=employer.company or job.company,
                role_title=job.title,
            )
    else:
        schedule(
            notify, intro.employer_id, kind="intro_declined",
            title=f"{who} passed on this role",
            body="No hard feelings — Uche will keep surfacing better-fit candidates.",
            link="/hire/intros",
        )
    return True
