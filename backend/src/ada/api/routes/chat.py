"""Streaming chat with Ada (SSE), grounded in the user's profile and run history."""
import json
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_user
from ada.db.models import User
from ada.db.repositories import (
    ChatMessageRepository,
    ProfileRepository,
    RunRepository,
    UserMemoryRepository,
)
from ada.db.session import get_session
from ada.services.coach import CoachService
from ada.services.memory import MemoryService

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8_000)


class ChatIn(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=60)


@router.post("")
async def chat(
    body: ChatIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> StreamingResponse:
    profile = await ProfileRepository(session).get(user.id)
    runs = await RunRepository(session).list_by_user(user.id, limit=5)
    memory = MemoryService()
    memories_repo = UserMemoryRepository(session)
    last_user_message = body.messages[-1].content
    memories = await memory.recall(memories_repo, user.id, last_user_message)

    async def events():
        reply_parts: list[str] = []
        try:
            async for delta in CoachService().stream(
                messages=[m.model_dump() for m in body.messages],
                profile=profile,
                runs=runs,
                memories=memories,
            ):
                reply_parts.append(delta)
                yield f"data: {json.dumps({'delta': delta})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:  # noqa: BLE001 — stream errors must reach the client
            yield f"data: {json.dumps({'error': repr(exc)})}\n\n"
            return
        # Persist the exchange and learn from it; best-effort, never surfaces to the client.
        reply = "".join(reply_parts)
        try:
            history = ChatMessageRepository(session)
            await history.append(user.id, "user", last_user_message)
            if reply:
                await history.append(user.id, "assistant", reply)
            await history.prune(user.id)
        except Exception:  # noqa: BLE001 — history must not break the stream
            pass
        exchange = f"Candidate: {last_user_message}\nAda: {reply}"
        await memory.remember(memories_repo, user.id, exchange)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class HistoryMessage(BaseModel):
    role: str
    content: str


@router.get("/history", response_model=list[HistoryMessage])
async def chat_history(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> list[HistoryMessage]:
    turns = await ChatMessageRepository(session).list_recent(user.id)
    return [HistoryMessage(role=t.role, content=t.content) for t in turns]


@router.delete("/history", status_code=204)
async def clear_chat_history(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> None:
    await ChatMessageRepository(session).clear(user.id)
