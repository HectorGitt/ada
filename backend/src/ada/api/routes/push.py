"""Web Push subscription management.

The browser subscribes with our VAPID public key, then registers the resulting endpoint
here so Ada can push to a closed tab. `notify()` sends to every registered browser.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_user
from ada.config import get_settings
from ada.db.models import User
from ada.db.repositories import PushSubscriptionRepository
from ada.db.session import get_session

router = APIRouter(prefix="/push", tags=["push"])


class Keys(BaseModel):
    p256dh: str = Field(min_length=40, max_length=200)
    auth: str = Field(min_length=16, max_length=100)


class SubscribeIn(BaseModel):
    endpoint: AnyHttpUrl
    keys: Keys

    @field_validator("endpoint")
    @classmethod
    def https_only(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.scheme != "https":
            raise ValueError("Push endpoints must use HTTPS.")
        if value.username or value.password or value.fragment:
            raise ValueError("Push endpoints must not contain credentials or fragments.")
        return value


class UnsubscribeIn(BaseModel):
    endpoint: str


@router.get("/vapid-public-key")
async def vapid_public_key() -> dict[str, str]:
    """The applicationServerKey the browser subscribes with. Empty string ⇒ push disabled."""
    return {"key": get_settings().vapid_public_key}


@router.post("/subscribe", status_code=201)
async def subscribe(
    body: SubscribeIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict[str, str]:
    if not get_settings().vapid_public_key:
        raise HTTPException(503, "Push notifications aren't configured.")
    await PushSubscriptionRepository(session).upsert(
        user_id=user.id, endpoint=str(body.endpoint), p256dh=body.keys.p256dh, auth=body.keys.auth
    )
    return {"status": "subscribed"}


@router.post("/unsubscribe")
async def unsubscribe(
    body: UnsubscribeIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict[str, str]:
    await PushSubscriptionRepository(session).delete(user_id=user.id, endpoint=str(body.endpoint))
    return {"status": "unsubscribed"}
