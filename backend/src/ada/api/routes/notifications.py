"""In-app notification centre — list, unread count, mark read."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_user
from ada.db.models import User
from ada.db.repositories import NotificationRepository
from ada.db.session import get_session

router = APIRouter(prefix="/notifications", tags=["notifications"])


class ReadIn(BaseModel):
    id: str | None = None  # None = mark all read


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
