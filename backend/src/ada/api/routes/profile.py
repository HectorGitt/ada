"""Career profile — the structured record Ada's onboarding builds and grounds runs,
chat, and (once discoverable) Uche's ranking."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_user
from ada.db.models import Profile, User
from ada.db.repositories import ProfileRepository
from ada.db.session import get_session

router = APIRouter(prefix="/profile", tags=["profile"])

_WORK_PREFS = {"remote", "hybrid", "onsite", "flexible"}


class ProfileIn(BaseModel):
    profile_text: str = Field(min_length=50, max_length=60_000)
    linkedin_url: str | None = Field(default=None, max_length=512)


class ProfileOut(BaseModel):
    profile_text: str
    linkedin_url: str | None
    full_name: str | None
    phone: str | None
    compensation: str | None
    work_pref: str | None
    updated_at: str


class IdentityIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    compensation: str | None = Field(default=None, max_length=120)
    work_pref: str | None = Field(default=None, max_length=20)


def _out(profile: Profile) -> ProfileOut:
    return ProfileOut(
        profile_text=profile.profile_text,
        linkedin_url=profile.linkedin_url,
        full_name=profile.full_name,
        phone=profile.phone,
        compensation=profile.compensation,
        work_pref=profile.work_pref,
        updated_at=profile.updated_at.isoformat(),
    )


@router.get("", response_model=ProfileOut | None)
async def get_profile(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> ProfileOut | None:
    profile = await ProfileRepository(session).get(user.id)
    return _out(profile) if profile is not None else None


@router.put("/identity", response_model=ProfileOut)
async def put_identity(
    body: IdentityIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> ProfileOut:
    work_pref = body.work_pref if body.work_pref in _WORK_PREFS else None
    profile = await ProfileRepository(session).set_identity(
        user_id=user.id, full_name=body.full_name.strip(), phone=body.phone,
        compensation=(body.compensation or "").strip() or None, work_pref=work_pref,
    )
    return _out(profile)


@router.put("", response_model=ProfileOut)
async def put_profile(
    body: ProfileIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> ProfileOut:
    profile = await ProfileRepository(session).upsert(
        user_id=user.id, profile_text=body.profile_text, linkedin_url=body.linkedin_url
    )
    return _out(profile)
