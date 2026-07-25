"""What Ada remembers about the user — visible and deletable, for trust and control."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_user
from ada.db.models import User
from ada.db.repositories import UserMemoryRepository
from ada.db.session import get_session

router = APIRouter(prefix="/memories", tags=["memories"])


class MemoryOut(BaseModel):
    id: int
    content: str
    created_at: str


@router.get("", response_model=list[MemoryOut])
async def list_memories(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> list[MemoryOut]:
    memories = await UserMemoryRepository(session).list_for_user(user.id)
    return [
        MemoryOut(id=m.id, content=m.content, created_at=m.created_at.isoformat())
        for m in memories
    ]


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> None:
    if not await UserMemoryRepository(session).delete_for_user(memory_id, user.id):
        raise HTTPException(404, "Memory not found.")
