"""Free CV assessment — the public, no-auth top-of-funnel hook.

One Gemini call returns a readiness score, a headline, and the three highest-impact
fixes, each citing a real line from the submitted CV. Degrades to a transparent
heuristic when generation is unavailable, so the endpoint always returns something
useful. The CTA converts into the paid rewrite.
"""
import json

from pydantic import BaseModel, Field

from ada.config import get_settings
from ada.observability import log
from ada.resilience import retry_async
from ada.vertex import vertex_client

_SYSTEM = """You are Ada, giving a sharp, free first read of a CV. Return an honest \
readiness score (0-100), a one-line headline, and EXACTLY three highest-impact fixes. \
Each fix names the problem, gives a concrete instruction, and quotes the specific CV line \
it refers to (verbatim, short). Be specific and useful — this is a taste of the paid \
rewrite, not generic advice. Return JSON: {"score": int, "headline": str, "fixes": \
[{"title": str, "detail": str, "quote": str}]}."""


class Fix(BaseModel):
    title: str
    detail: str
    quote: str = ""


class Assessment(BaseModel):
    score: int = Field(ge=0, le=100)
    headline: str
    fixes: list[Fix] = Field(default_factory=list)
    method: str = "ai"


async def assess_cv(cv_text: str, target_role: str | None) -> Assessment:
    s = get_settings()
    role = (target_role or "").strip()
    prompt = f"TARGET ROLE: {role or '(not specified)'}\n\nCV:\n{cv_text.strip()[:12_000]}"
    try:
        resp = await retry_async(
            lambda: vertex_client().aio.models.generate_content(
                model=s.vertex_model,
                contents=prompt,
                config={
                    "system_instruction": _SYSTEM,
                    "temperature": 0.3,
                    "response_mime_type": "application/json",
                    "response_schema": Assessment,
                },
            ),
            attempts=s.llm_max_attempts,
        )
        data = json.loads(resp.text or "{}")
        return Assessment(
            score=max(0, min(100, int(data.get("score", 0)))),
            headline=data.get("headline", ""),
            fixes=[Fix(**f) for f in data.get("fixes", [])][:3],
            method="ai",
        )
    except Exception as exc:  # noqa: BLE001 — no creds/quota: transparent heuristic
        log.warning("assess_fallback", error=str(exc))
        return _heuristic_assessment(cv_text)


def _heuristic_assessment(cv_text: str) -> Assessment:
    text = cv_text.strip()
    low = text.lower()
    has_metrics = any(ch.isdigit() for ch in text)
    has_education = "education" in low or "degree" in low or "university" in low
    has_experience = "experience" in low or "worked" in low or "manage" in low
    length_ok = len(text) > 600

    score = 40 + 15 * has_metrics + 10 * has_education + 10 * has_experience + 10 * length_ok
    fixes = [
        Fix(title="Lead with quantified impact",
            detail="Recruiters scan for outcomes. Add a number to your top bullets — "
                   "revenue, %, headcount, time saved.",
            quote=""),
        Fix(title="Tailor to the target role",
            detail="Mirror the role's language and put the most relevant experience first, "
                   "not just the most recent.",
            quote=""),
        Fix(title="Cut the filler",
            detail="Replace duties ('responsible for…') with achievements ('grew…', 'shipped…').",
            quote=""),
    ]
    return Assessment(
        score=min(100, score),
        headline="A solid base — a few sharp fixes will make it land." if length_ok
                 else "There's a real gap here we can close fast.",
        fixes=fixes,
        method="heuristic",
    )
