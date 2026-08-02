"""Candidate insight + employer-discovery consent.

`GET /candidate/insights` returns Ada's structured read of the candidate, computing
it on first request. `PUT /candidate/discoverable` is the opt-in that lets Uche surface
them to employers — enabling it (re)builds the analysis + search vector.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_user
from ada.db.models import Intro, IntroStatus, User
from ada.db.repositories import (
    IntroMessageRepository,
    IntroRepository,
    ProfileRepository,
    RunRepository,
)
from ada.db.session import get_session
from ada.services.insights import refresh_candidate
from ada.services.intros import respond_to_intro
from ada.services.notify import notify

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
    intro = await session.get(Intro, intro_id)
    if intro is None:
        raise HTTPException(404, "Intro not found or already answered.")
    moved = await respond_to_intro(
        intro=intro, responder_id=user.id, status=status, schedule=background.add_task
    )
    if not moved:
        raise HTTPException(404, "Intro not found or already answered.")
    return {"status": str(status)}


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


@router.get("/intros/{intro_id}/messages")
async def intro_thread(
    intro_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    intro = await session.get(Intro, intro_id)
    if intro is None or intro.candidate_id != user.id:
        raise HTTPException(404, "Intro not found.")
    messages = await IntroMessageRepository(session).list_for_intro(intro_id)
    return [
        {"sender": m.sender, "body": m.body, "created_at": m.created_at.isoformat()}
        for m in messages
    ]


@router.post("/intros/{intro_id}/messages", status_code=201)
async def send_intro_message(
    intro_id: str,
    body: MessageIn,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    intro = await session.get(Intro, intro_id)
    if intro is None or intro.candidate_id != user.id:
        raise HTTPException(404, "Intro not found.")
    if str(intro.status) != "accepted":
        raise HTTPException(409, "Accept the intro before replying.")
    msg = await IntroMessageRepository(session).add(
        intro_id=intro_id, sender="candidate", body=body.body
    )
    background.add_task(
        notify, intro.employer_id, kind="intro_message",
        title="New message from a candidate", body=body.body[:200], link="/hire/intros",
    )
    return {"sender": msg.sender, "body": msg.body, "created_at": msg.created_at.isoformat()}
