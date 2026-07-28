"""Candidate insight + employer-discovery consent.

`GET /candidate/insights` returns Ada's structured read of the candidate, computing
it on first request. `PUT /candidate/discoverable` is the opt-in that lets Uche surface
them to employers — enabling it (re)builds the analysis + search vector.
"""
from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_user
from ada.db.models import User
from ada.db.repositories import ProfileRepository, RunRepository
from ada.db.session import get_session
from ada.services.insights import refresh_candidate

router = APIRouter(prefix="/candidate", tags=["candidate"])


class DiscoverableIn(BaseModel):
    discoverable: bool


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
