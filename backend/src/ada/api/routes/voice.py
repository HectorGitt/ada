"""WebSocket relay for the Gemini Live voice conversation.

Grounds the session in what Ada already knows about the signed-in caller (profile,
latest CV, remembered facts) so she opens with recognition. Two modes via the `mode`
query param: an open career "conversation" (default) or a spoken "interview". On
{"type":"end"} the conversation is saved to the caller's memory so Ada remembers it.
If Live is unavailable it returns a clean error frame.

Client frames:  {"type":"audio","data": <base64 pcm16@16k>}
                {"type":"text","data": "..."}
                {"type":"end"}
Server frames:  {"type":"audio","data": <base64 pcm16@24k>} | {"type":"interrupt"}
                {"type":"transcript","data": "..."} | {"type":"ended"}
                | {"type":"error","message": "..."}
"""
import asyncio
import base64

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google.genai import types

from ada.auth.repository import AuthRepository
from ada.auth.tokens import hash_token
from ada.config import get_settings
from ada.db.repositories import (
    ProfileRepository,
    SubscriptionRepository,
    UploadedDocumentRepository,
    UserMemoryRepository,
)
from ada.db.session import _session_factory
from ada.observability import log
from ada.services import entitlements
from ada.services.memory import MemoryService
from ada.services.voice import Mode, VoiceIntake, format_candidate_context

router = APIRouter(tags=["voice"])

_RECALL_QUERY = "career background, current role, key skills, experience, and goals"


async def _resolve_caller(ws: WebSocket) -> tuple[str | None, str | None]:
    """Best-effort: (user_id, grounding_context) from the session cookie.
    Any failure (anonymous, no profile, no creds) -> (None, None)."""
    raw = ws.cookies.get(get_settings().session_cookie)
    if not raw:
        return None, None
    try:
        async with _session_factory() as session:
            user = await AuthRepository(session).user_for_session(hash_token(raw))
            if user is None:
                return None, None
            profile = await ProfileRepository(session).get(user.id)
            uploads = await UploadedDocumentRepository(session).list_for_user(user.id)
            memories = await MemoryService().recall(
                UserMemoryRepository(session), user.id, _RECALL_QUERY
            )
        context = format_candidate_context(
            full_name=profile.full_name if profile else None,
            profile_text=profile.profile_text if profile else None,
            cv_text=uploads[0].cv_text if uploads else None,
            memories=memories,
        )
        return user.id, context
    except Exception as exc:  # noqa: BLE001 — grounding is best-effort; fall back to cold open
        log.warning("voice_context_failed", error=str(exc))
        return None, None


async def _remember(user_id: str, transcript: list[str]) -> None:
    """Save the spoken conversation to the caller's memory. Best-effort."""
    if not transcript:
        return
    try:
        async with _session_factory() as session:
            await MemoryService().remember(
                UserMemoryRepository(session), user_id, "\n".join(transcript)
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("voice_remember_failed", user_id=user_id, error=str(exc))


async def _can_voice(user_id: str | None) -> bool:
    if user_id is None:
        return False
    try:
        async with _session_factory() as session:
            sub = await SubscriptionRepository(session).get(user_id)
        return entitlements.resolve(sub).can_voice
    except Exception:  # noqa: BLE001 — gate defaults to closed on any failure
        return False


@router.websocket("/voice")
async def voice(ws: WebSocket) -> None:
    await ws.accept()
    user_id, context = await _resolve_caller(ws)
    if not await _can_voice(user_id):
        await ws.send_json({
            "type": "error",
            "message": "Live voice is a Premium feature — upgrade to talk with Ada.",
        })
        await ws.close()
        return
    mode: Mode = "interview" if ws.query_params.get("mode") == "interview" else "conversation"
    intake = VoiceIntake()
    transcript: list[str] = []
    try:
        async with intake.connect(context, mode) as session:

            last_speaker = ""

            async def relay(speaker: str, text: str) -> None:
                """Merge consecutive same-speaker fragments; label speaker turns."""
                nonlocal last_speaker
                if speaker == last_speaker:
                    transcript[-1] += text
                    data = text
                else:
                    transcript.append(f"{speaker}: {text}")
                    data = f"\n{speaker}: {text}" if last_speaker else f"{speaker}: {text}"
                    last_speaker = speaker
                await ws.send_json({"type": "transcript", "data": data})

            async def pump_out() -> None:
                async for resp in session.receive():
                    if resp.data:
                        audio = base64.b64encode(resp.data).decode("ascii")
                        await ws.send_json({"type": "audio", "data": audio})
                    sc = resp.server_content
                    if sc is None:
                        continue
                    # Barge-in: the user spoke over Ada — tell the client to cut playback.
                    if sc.interrupted:
                        await ws.send_json({"type": "interrupt"})
                    if sc.input_transcription and sc.input_transcription.text:
                        await relay("You", sc.input_transcription.text)
                    if sc.output_transcription and sc.output_transcription.text:
                        await relay("Ada", sc.output_transcription.text)

            out_task = asyncio.create_task(pump_out())
            # Ada opens the call herself — grounded in context when the caller is known.
            await session.send_client_content(
                turns="The candidate just joined the call. Greet them and begin.",
                turn_complete=True,
            )
            while True:
                msg = await ws.receive_json()
                kind = msg.get("type")
                if kind == "audio":
                    pcm = base64.b64decode(msg["data"])
                    await session.send_realtime_input(
                        media=types.Blob(data=pcm, mime_type="audio/pcm;rate=16000")
                    )
                elif kind == "text":
                    await session.send_client_content(turns=msg["data"], turn_complete=True)
                elif kind == "end":
                    break
            out_task.cancel()

        if user_id:
            await _remember(user_id, transcript)
        await ws.send_json({"type": "ended"})
    except WebSocketDisconnect:
        if user_id:
            await _remember(user_id, transcript)
    except Exception as exc:  # noqa: BLE001 — surface any Live failure to the client
        await ws.send_json({"type": "error", "message": f"voice unavailable: {exc!r}"})
    finally:
        try:
            await ws.close()
        except RuntimeError:
            pass
