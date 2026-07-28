"""ATS CV rewrite via Gemini on Vertex — first node of the agent graph.

Uses the shared Vertex client (request timeout) and retries transient failures.
"""
from google.genai import types

from ada.config import get_settings
from ada.resilience import retry_async
from ada.services.persona import CV_CRAFT, IDENTITY
from ada.vertex import vertex_client

_SYSTEM = f"""{IDENTITY}

{CV_CRAFT}

Task: rewrite the candidate's CV so it is tightly targeted to the stated role.
- Lead with a 2-3 line professional summary aimed at the target role.
- Use standard ATS-safe section headers (Summary, Skills, Experience, Education).
- Never invent facts, numbers, employers, or dates.
- Mirror the vocabulary a recruiter for this role would search for.
- Output clean Markdown only — no commentary, no code fences."""


class CVService:
    def __init__(self) -> None:
        self._client = vertex_client()
        self._model = get_settings().vertex_model
        self._attempts = get_settings().llm_max_attempts

    async def rewrite(self, *, cv_text: str, target_role: str) -> str:
        prompt = f"TARGET ROLE: {target_role}\n\nCURRENT CV:\n{cv_text}"
        resp = await retry_async(
            lambda: self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=_SYSTEM, temperature=0.4),
            ),
            attempts=self._attempts,
        )
        return (resp.text or "").strip()
