"""In-app notification centre — list, unread count, mark read, delivery preferences."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_user
from ada.db.models import User
from ada.db.repositories import NotificationPrefRepository, NotificationRepository
from ada.db.session import get_session

router = APIRouter(prefix="/notifications", tags=["notifications"])


class ReadIn(BaseModel):
    id: str | None = None  # None = mark all read


class PrefsIn(BaseModel):
    email: bool
    whatsapp: bool
    digest: bool


@router.get("")
async def list_notifications(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    repo = NotificationRepository(session)
    items = await repo.list_for_user(user.id)
    return {
        "unread": await repo.unread_count(user.id),
        "items": [
            {
                "id": n.id,
                "kind": n.kind,
                "title": n.title,
                "body": n.body,
                "link": n.link,
                "read": n.read,
                "created_at": n.created_at.isoformat(),
            }
            for n in items
        ],
    }


@router.post("/read")
async def mark_read(
    body: ReadIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    await NotificationRepository(session).mark_read(user.id, body.id)
    return {"ok": True}


@router.get("/preferences")
async def get_preferences(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    p = await NotificationPrefRepository(session).get_or_create(user.id)
    return {"email": p.email_enabled, "whatsapp": p.whatsapp_enabled, "digest": p.digest_enabled}


@router.put("/preferences")
async def set_preferences(
    body: PrefsIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    p = await NotificationPrefRepository(session).update(
        user.id, email=body.email, whatsapp=body.whatsapp, digest=body.digest
    )
    return {"email": p.email_enabled, "whatsapp": p.whatsapp_enabled, "digest": p.digest_enabled}


class UnsubIn(BaseModel):
    token: str


@router.post("/unsubscribe")
async def unsubscribe(
    body: UnsubIn, session: AsyncSession = Depends(get_session)
) -> dict:
    """Public one-click unsubscribe from the email footer — no auth, token-scoped.
    Always reports success so the token can't be probed for validity."""
    await NotificationPrefRepository(session).unsubscribe_all(body.token)
    return {"ok": True}
