"""Uche — the employer's agent (Igbo: "wisdom / discernment"). Given a role, she
ranks *consented* candidates (pgvector KNN over their vectors) and explains each fit.

The employer-side mirror of Ada: same embedding infra, pointed at candidates instead
of jobs. Reads only discoverable candidates — the channel-conflict wall. Ranking is
vector-first (cheap, deterministic); the rationale is one structured Gemini call over
the whole shortlist, not one call per candidate.
"""
from typing import Any

from pydantic import BaseModel, Field

from ada.config import get_settings
from ada.db.models import Job, Profile
from ada.db.repositories import ProfileRepository
from ada.observability import log
from ada.resilience import retry_async
from ada.services.search import SearchService
from ada.vertex import vertex_client

_SYSTEM = """You are Uche, an expert technical recruiter helping an employer hire. \
Given a role and a ranked shortlist of candidates (already matched by vector search), \
write one honest sentence per candidate on why they fit this specific role, grounded \
only in their provided profile. Then a two-sentence summary of the shortlist for the \
hiring manager. Be direct and specific; never invent credentials."""


class _Verdict(BaseModel):
    index: int
    verdict: str = Field(description="strong | good | stretch")
    rationale: str = Field(description="One sentence, specific to this role")


class _Shortlist(BaseModel):
    summary: str
    candidates: list[_Verdict] = Field(default_factory=list)


def _fit(distance: float) -> int:
    return max(0, min(100, round((1.0 - distance) * 100)))


def _candidate_brief(profile: Profile, index: int) -> str:
    ins: dict[str, Any] = profile.insights or {}
    skills = ", ".join(ins.get("top_skills", [])[:8])
    return (
        f"[{index}] {ins.get('headline') or profile.headline or 'Candidate'} — "
        f"{ins.get('seniority', '?')}, {ins.get('years_experience', '?')}y. "
        f"Skills: {skills}. Fit: {ins.get('market_fit', '')}"
    )


class UcheService:
    def __init__(self) -> None:
        self._client = vertex_client()
        self._model = get_settings().vertex_model
        self._attempts = get_settings().llm_max_attempts
        self._search = SearchService()

    async def curate(
        self, *, job: Job, profiles: ProfileRepository, k: int = 8
    ) -> dict[str, Any]:
        """Return {summary, candidates:[{user_id, match, verdict, rationale, ...}]}."""
        query = f"{job.title} at {job.company}. {job.description}"
        try:
            vector = await self._search.embed(query)
        except Exception as exc:  # noqa: BLE001 — no creds: return an honest empty shortlist
            log.warning("uche_embed_skipped", job_id=job.id, error=str(exc))
            return {"summary": "", "candidates": [], "unavailable": True}

        ranked = await profiles.search_candidates(vector, k, exclude=job.posted_by)
        if not ranked:
            return {"summary": "No consented candidates match this role yet.", "candidates": []}

        cards = [
            {
                "user_id": p.user_id,
                "headline": (p.insights or {}).get("headline") or p.headline,
                "location": p.location,
                "seniority": (p.insights or {}).get("seniority"),
                "years_experience": (p.insights or {}).get("years_experience"),
                "top_skills": (p.insights or {}).get("top_skills", [])[:8],
                "match": _fit(dist),
                "verdict": "good",
                "rationale": "",
            }
            for p, dist in ranked
        ]

        briefs = "\n".join(_candidate_brief(p, i) for i, (p, _) in enumerate(ranked))
        prompt = f"ROLE: {job.title} at {job.company}\n{job.description}\n\nCANDIDATES:\n{briefs}"
        try:
            resp = await retry_async(
                lambda: self._client.aio.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config={
                        "system_instruction": _SYSTEM,
                        "temperature": 0.3,
                        "response_mime_type": "application/json",
                        "response_schema": _Shortlist,
                    },
                ),
                attempts=self._attempts,
            )
            shortlist = _Shortlist.model_validate_json(resp.text or "{}")
        except Exception as exc:  # noqa: BLE001 — vector ranking still stands without rationale
            log.warning("uche_rationale_skipped", job_id=job.id, error=str(exc))
            return {"summary": "", "candidates": cards}

        for verdict in shortlist.candidates:
            if 0 <= verdict.index < len(cards):
                cards[verdict.index]["verdict"] = verdict.verdict
                cards[verdict.index]["rationale"] = verdict.rationale
        return {"summary": shortlist.summary, "candidates": cards}
