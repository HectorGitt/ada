"""Candidate insight + employer-discovery consent.

`GET /candidate/insights` returns Ada's structured read of the candidate, computing
it on first request. `PUT /candidate/discoverable` is the opt-in that lets Uche surface
them to employers — enabling it (re)builds the analysis + search vector.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_user
from ada.db.models import Intro, IntroStatus, User
from ada.db.repositories import (
    IntroRepository,
    JobRepository,
    ProfileRepository,
    RunRepository,
)
from ada.db.session import get_session
from ada.services.insights import refresh_candidate
from ada.services.notify import connect_parties, notify

router = APIRouter(prefix="/candidate", tags=["candidate"])


class DiscoverableIn(BaseModel):
    discoverable: bool


class RespondIn(BaseModel):
    action: str  # "accept" | "decline"


async def _refresh(user_id: str) -> None:
    from ada.db.session import _session_factory

    async with _session_factory() as session:
        await refresh_candidate(user_id, ProfileRepository(session), RunRepository(session))


@router.get("/insights")
async def get_insights(
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    profile = await ProfileRepository(session).get(user.id)
    if profile is None:
        return {"insights": None, "ready": False, "reason": "no_profile"}
    if profile.insights is None:
        # Compute on first view; the client polls until ready.
        background.add_task(_refresh, user.id)
        return {"insights": None, "ready": False, "reason": "computing"}
    return {"insights": profile.insights, "ready": True, "discoverable": profile.discoverable}


@router.put("/discoverable")
async def set_discoverable(
    body: DiscoverableIn,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    profiles = ProfileRepository(session)
    await profiles.set_discoverable(user.id, body.discoverable)
    if body.discoverable:
        # Make sure the analysis + vector exist so Uche can actually find them.
        background.add_task(_refresh, user.id)
    return {"discoverable": body.discoverable}


@router.get("/intros")
async def my_intros(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    rows = await IntroRepository(session).list_for_candidate(user.id)
    return [
        {
            "id": intro.id,
            "status": str(intro.status),
            "message": intro.message,
            "created_at": intro.created_at.isoformat(),
            "role_title": job.title,
            "company": employer.company or job.company,
            "location": job.location,
            "remote": job.remote,
        }
        for intro, job, employer in rows
    ]


@router.post("/intros/{intro_id}/respond")
async def respond_intro(
    intro_id: str,
    body: RespondIn,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    if body.action not in ("accept", "decline"):
        raise HTTPException(422, "action must be 'accept' or 'decline'.")
    status = IntroStatus.ACCEPTED if body.action == "accept" else IntroStatus.DECLINED
    intros = IntroRepository(session)
    intro = await session.get(Intro, intro_id)
    moved = await intros.respond(intro_id, user.id, status)
    if not moved:
        raise HTTPException(404, "Intro not found or already answered.")
    if intro is not None:
        profile = await ProfileRepository(session).get(user.id)
        who = (profile.full_name if profile else None) or "A candidate"
        if body.action == "accept":
            background.add_task(
                notify, intro.employer_id, kind="intro_accepted",
                title=f"{who} accepted your intro",
                body="They're open to talking — their contact is on the intro in your console.",
                link="/hire/intros",
            )
            # Warm two-way introduction email connecting both sides.
            employer = await session.get(User, intro.employer_id)
            job = await JobRepository(session).get(intro.job_id)
            if employer is not None and job is not None:
                background.add_task(
                    connect_parties,
                    candidate_email=user.email,
                    candidate_name=who,
                    employer_email=employer.email,
                    company=employer.company or job.company,
                    role_title=job.title,
                )
        else:
            background.add_task(
                notify, intro.employer_id, kind="intro_declined",
                title=f"{who} passed on this role",
                body="No hard feelings — Uche will keep surfacing better-fit candidates.",
                link="/hire/intros",
            )
    return {"status": str(status)}
