"""Mock interview, two-phase.

Phase 1 (questions) runs inside the agent graph. Phase 2 (score) is a follow-up endpoint
that scores the candidate's typed answers. Both enforce a response schema, retry
transient errors, and parse defensively so malformed output degrades rather than raises.
"""
import json

from google.genai import types
from pydantic import BaseModel

from ada.config import get_settings
from ada.resilience import retry_async
from ada.services.persona import IDENTITY, SCORING_RUBRIC
from ada.vertex import vertex_client

_Q_SYSTEM = (
    IDENTITY
    + """

Task: as a senior interviewer hiring for the candidate's target role, generate \
exactly {n} incisive interview questions tailored to THIS candidate's CV and the \
target role. Mix behavioural, role-specific technical, and — where the role \
warrants it — system-design, leadership, or problem-solving questions. Never \
fabricate details about the candidate. Return a JSON array of question strings only."""
)

_SCORE_SYSTEM = (
    IDENTITY
    + "\n\n"
    + SCORING_RUBRIC
    + """

Task: score the candidate's mock-interview answers for their target role. For \
each question/answer pair give an integer score 0-10 plus one or two sentences \
of concrete, actionable feedback. Judge ONLY what the candidate actually wrote \
— never invent facts or credit experience they did not state. An empty or \
evasive answer scores low."""
)

# Response schemas (pydantic models are converted by the SDK) force well-formed JSON.
class AnswerScore(BaseModel):
    question: str
    answer: str
    score: int
    feedback: str


class InterviewScorecard(BaseModel):
    scores: list[AnswerScore]
    overall_score: float
    summary: str


class InterviewService:
    def __init__(self) -> None:
        self._client = vertex_client()
        self._model = get_settings().vertex_model
        self._attempts = get_settings().llm_max_attempts

    async def questions(self, *, target_role: str, cv_text: str, n: int = 5) -> list[str]:
        prompt = f"TARGET ROLE: {target_role}\n\nCANDIDATE CV:\n{cv_text}"
        resp = await retry_async(
            lambda: self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_Q_SYSTEM.format(n=n),
                    temperature=0.6,
                    response_mime_type="application/json",
                    response_schema=list[str],
                ),
            ),
            attempts=self._attempts,
        )
        data = _safe_json(resp.text, default=[])
        return [str(q) for q in data][:n]

    async def score(
        self, *, target_role: str, questions: list[str], answers: list[str]
    ) -> dict:
        pairs = [{"question": q, "answer": a} for q, a in zip(questions, answers, strict=True)]
        prompt = (
            f"TARGET ROLE: {target_role}\n\n"
            f"QUESTION/ANSWER PAIRS:\n{json.dumps(pairs, ensure_ascii=False)}"
        )
        resp = await retry_async(
            lambda: self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SCORE_SYSTEM,
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=InterviewScorecard,
                ),
            ),
            attempts=self._attempts,
        )
        return _safe_json(resp.text, default={})


def _safe_json(text: str | None, *, default):
    try:
        return json.loads(text or "")
    except (json.JSONDecodeError, TypeError):
        return default
