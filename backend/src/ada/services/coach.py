"""Conversational career coach, grounded in the user's imported profile and run history.

stream() yields plain text deltas from Gemini; the chat route wraps them as SSE.
Grounding context is assembled per request — profile text plus a compact summary of
recent runs — so answers reference the user's actual history rather than generic advice.
"""
from collections.abc import AsyncIterator

from google.genai import types

from ada.config import get_settings
from ada.db.models import Profile, Run
from ada.services.persona import COACHING, IDENTITY
from ada.vertex import vertex_client

_SYSTEM = (
    IDENTITY
    + "\n\n"
    + COACHING
    + """

You know this candidate from their imported profile and their history with you \
(CV rewrites, job matches, interview scores) — use it, cite it, and be specific \
to them. If their profile lacks something important, say what to add. Keep \
answers tight."""
)

_MAX_TURNS = 30


class CoachService:
    def __init__(self) -> None:
        self._client = vertex_client()
        self._model = get_settings().vertex_model

    async def stream(
        self,
        *,
        messages: list[dict[str, str]],
        profile: Profile | None,
        runs: list[Run],
        memories: list[str] | None = None,
    ) -> AsyncIterator[str]:
        contents = [
            types.Content(
                role="user" if m["role"] == "user" else "model",
                parts=[types.Part.from_text(text=m["content"])],
            )
            for m in messages[-_MAX_TURNS:]
        ]
        system = _SYSTEM + self._grounding(profile, runs, memories or [])
        stream = await self._client.aio.models.generate_content_stream(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system, temperature=0.7),
        )
        async for chunk in stream:
            if chunk.text:
                yield chunk.text

    @staticmethod
    def _grounding(profile: Profile | None, runs: list[Run], memories: list[str]) -> str:
        parts: list[str] = []
        if memories:
            facts = "\n".join(f"- {m}" for m in memories)
            parts.append(
                f"\n\nTHINGS YOU REMEMBER ABOUT THIS CANDIDATE (from past conversations):\n{facts}"
            )
        if profile:
            parts.append(f"\n\nCANDIDATE PROFILE (imported):\n{profile.profile_text[:8000]}")
            if profile.linkedin_url:
                parts.append(f"\nLinkedIn: {profile.linkedin_url}")
        if runs:
            lines = []
            for r in runs[:5]:
                score = ""
                if r.interview_json and "overall_score" in r.interview_json:
                    score = f", interview score {r.interview_json['overall_score']}/10"
                lines.append(
                    f"- {r.created_at:%Y-%m-%d}: targeted '{r.target_role}' "
                    f"({r.status}{score})"
                )
            parts.append("\n\nRUN HISTORY WITH ADA:\n" + "\n".join(lines))
        if not parts:
            parts.append(
                "\n\nThe candidate has no imported profile or runs yet; invite them to "
                "import their LinkedIn profile or start a run so you can be specific."
            )
        return "".join(parts)
