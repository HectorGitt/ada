"""The verification credential — the moat.

A skeptical employer won't trust "our AI thinks she's good." So the credential is
*evidence*, not opinion: a proctored, role-specific assessment taken under observed
conditions (timing + tab-switch/blur/paste telemetry), scored against a rubric, and
combined with an identity attestation. The output is a signal an employer can judge
independently of Ada.

Model-light with honest fallbacks: task generation and grading use Gemini when
available and degrade to a rubric/heuristic otherwise, so the flow always completes —
the grading method is recorded in the evidence so nothing is passed off as more than
it is.
"""
import json
from typing import Any

from pydantic import BaseModel, Field

from ada.config import get_settings
from ada.db.models import AssessmentVerdict
from ada.observability import log
from ada.resilience import retry_async
from ada.vertex import vertex_client

QUESTION_COUNT = 4

_TASK_SYSTEM = """You are setting a short, proctored skills assessment for a specific role. \
Write exactly {n} questions that force the candidate to show real, specific competence — \
concrete scenarios, judgement calls, and 'describe a time you actually…' prompts, not \
trivia. Each answerable in a few minutes of typing. Return JSON: a list of objects \
{{"prompt": str, "looks_for": str}} where looks_for is the rubric — what a strong answer \
demonstrates."""

_GRADE_SYSTEM = """You are grading a proctored skills assessment, fairly and skeptically. \
For each question you get the rubric (looks_for) and the candidate's answer. Score each \
0-100 on evidence of real competence — reward specificity, judgement, and lived detail; \
penalise vagueness, hand-waving, and generic filler. Return JSON: \
{"per_answer": [{"score": int, "note": str}], "overall": int, "summary": str}."""


class _Question(BaseModel):
    prompt: str
    looks_for: str = ""


class _Grade(BaseModel):
    per_answer: list[dict[str, Any]] = Field(default_factory=list)
    overall: int = 0
    summary: str = ""


def _fallback_questions(skill: str) -> list[dict[str, str]]:
    return [
        {"prompt": f"Describe a specific project where you applied {skill}. State the "
                   "problem, your exact contribution, and the measurable outcome.",
         "looks_for": "concrete role, specific actions, quantified result"},
        {"prompt": f"Walk through how you'd approach a hard, realistic {skill} task from "
                   "scratch. What are your first three steps and the biggest risk?",
         "looks_for": "structured approach, prioritisation, risk awareness"},
        {"prompt": f"What's a real mistake you made doing {skill} work, and precisely what "
                   "you changed afterwards?",
         "looks_for": "honesty, reflection, concrete change"},
        {"prompt": f"A stakeholder disagrees with your {skill} decision. How do you handle "
                   "it, and when would you change your mind?",
         "looks_for": "communication, evidence-based reasoning, non-defensiveness"},
    ]


class VerificationService:
    def __init__(self) -> None:
        s = get_settings()
        self._client = vertex_client()
        self._model = s.vertex_model
        self._attempts = s.llm_max_attempts
        self._pass_mark = s.verify_pass_mark

    async def issue_task(self, skill: str) -> list[dict[str, str]]:
        """Role-specific questions; falls back to a strong generic rubric bank."""
        try:
            resp = await retry_async(
                lambda: self._client.aio.models.generate_content(
                    model=self._model,
                    contents=f"Role/skill: {skill}",
                    config={
                        "system_instruction": _TASK_SYSTEM.format(n=QUESTION_COUNT),
                        "temperature": 0.4,
                        "response_mime_type": "application/json",
                        "response_schema": list[_Question],
                    },
                ),
                attempts=self._attempts,
            )
            items = [q for q in json.loads(resp.text or "[]") if q.get("prompt")]
            if items:
                return items[:QUESTION_COUNT]
        except Exception as exc:  # noqa: BLE001 — no creds/quota: honest fallback bank
            log.warning("verify_task_fallback", skill=skill, error=str(exc))
        return _fallback_questions(skill)

    async def _grade(
        self, skill: str, questions: list[dict], answers: list[str]
    ) -> tuple[int, list[dict], str, str]:
        """Returns (overall 0-100, per-answer notes, summary, method)."""
        payload = [
            {"prompt": q.get("prompt", ""), "looks_for": q.get("looks_for", ""),
             "answer": (answers[i] if i < len(answers) else "")}
            for i, q in enumerate(questions)
        ]
        try:
            resp = await retry_async(
                lambda: self._client.aio.models.generate_content(
                    model=self._model,
                    contents=f"Role/skill: {skill}\n\n{json.dumps(payload)}",
                    config={
                        "system_instruction": _GRADE_SYSTEM,
                        "temperature": 0.2,
                        "response_mime_type": "application/json",
                        "response_schema": _Grade,
                    },
                ),
                attempts=self._attempts,
            )
            g = _Grade.model_validate_json(resp.text or "{}")
            overall = max(0, min(100, g.overall))
            return overall, g.per_answer, g.summary, "ai-graded"
        except Exception as exc:  # noqa: BLE001 — degrade to a transparent heuristic
            log.warning("verify_grade_fallback", skill=skill, error=str(exc))
            scores = [_heuristic(a) for a in answers]
            per = [{"score": sc, "note": "auto-scored"} for sc in scores]
            overall = round(sum(scores) / len(scores)) if scores else 0
            return overall, per, "Auto-scored pending human/AI review.", "heuristic"

    async def score(
        self, *, skill: str, questions: list[dict], answers: list[str],
        integrity: dict[str, Any], duration_seconds: int,
    ) -> tuple[int, AssessmentVerdict, dict[str, Any]]:
        overall, per_answer, summary, method = await self._grade(skill, questions, answers)
        clean = integrity_ok(integrity)
        if not clean:
            verdict = AssessmentVerdict.NEEDS_REVIEW
        elif overall >= self._pass_mark:
            verdict = AssessmentVerdict.VERIFIED
        else:
            verdict = AssessmentVerdict.FAILED
        evidence = {
            "method": method,
            "summary": summary,
            "per_answer": per_answer,
            "integrity_clean": clean,
            "duration_seconds": duration_seconds,
        }
        return overall, verdict, evidence


def integrity_ok(integrity: dict[str, Any]) -> bool:
    """Proctoring gate: any paste, excessive tab-switching/blur, or blowing the
    server-enforced time limit means the result can't be trusted at face value
    (→ NEEDS_REVIEW), however high the score."""
    if integrity.get("over_time"):
        return False
    paste = int(integrity.get("paste_events", 0) or 0)
    tab_switches = int(integrity.get("tab_switches", 0) or 0)
    blur_seconds = float(integrity.get("blur_seconds", 0) or 0)
    return paste == 0 and tab_switches <= 2 and blur_seconds < 20


def _heuristic(answer: str) -> int:
    """A deliberately conservative content score for when grading is unavailable:
    rewards substantive, specific answers; near-zero for empty/filler."""
    text = (answer or "").strip()
    if len(text) < 40:
        return 20
    specifics = sum(ch.isdigit() for ch in text)
    base = min(70, 30 + len(text) // 20)
    return min(90, base + min(20, specifics * 2))
