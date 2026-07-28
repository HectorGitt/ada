"""Ada's structured read of a candidate — the analysis that makes a profile
elaborate for the candidate and searchable for Grace.

From the candidate's profile text + latest rewritten CV, produce a typed insight
(seniority, years, skills, strengths, market fit, readiness) and the candidate
embedding employers are ranked against. Model-light: one structured call + one
embed, both on the cheap models.
"""
import json

from pydantic import BaseModel, Field

from ada.config import get_settings
from ada.db.repositories import ProfileRepository, RunRepository
from ada.observability import log
from ada.resilience import retry_async
from ada.services.search import SearchService
from ada.vertex import vertex_client

_SYSTEM = """You are Ada, analysing a candidate for their own career dashboard and to \
help employers find them. From the profile and CV, produce an honest, specific read. \
Never invent facts; infer only what the text supports. Skills are concrete and \
role-relevant. Strengths cite evidence. market_fit names the kinds of roles/industries \
they're competitive for. readiness_score (0-100) reflects how job-ready the materials \
are (clarity, achievements, coherence), not the person's worth."""


class CandidateInsight(BaseModel):
    headline: str = Field(description="One-line professional headline, e.g. 'Sales Manager, FMCG'")
    seniority: str = Field(description="One of: entry, junior, mid, senior, lead, executive")
    years_experience: int = Field(ge=0, le=60)
    location: str = Field(default="", description="City/region if stated, else empty")
    top_skills: list[str] = Field(default_factory=list, description="5-10 concrete skills")
    strengths: list[str] = Field(default_factory=list, description="2-4 evidence-backed strengths")
    growth_areas: list[str] = Field(default_factory=list, description="1-3 development areas")
    market_fit: str = Field(description="2-3 sentences: the roles/industries they fit and why")
    readiness_score: int = Field(ge=0, le=100)
    summary: str = Field(description="A warm 2-3 sentence summary addressed to the candidate")


class InsightService:
    def __init__(self) -> None:
        self._client = vertex_client()
        self._model = get_settings().vertex_model
        self._attempts = get_settings().llm_max_attempts
        self._search = SearchService()

    async def analyze(self, *, profile_text: str, cv_text: str) -> CandidateInsight:
        prompt = f"PROFILE:\n{profile_text}\n\nLATEST CV:\n{cv_text or '(none yet)'}"
        resp = await retry_async(
            lambda: self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config={
                    "system_instruction": _SYSTEM,
                    "temperature": 0.3,
                    "response_mime_type": "application/json",
                    "response_schema": CandidateInsight,
                },
            ),
            attempts=self._attempts,
        )
        return CandidateInsight.model_validate_json(resp.text or "{}")

    @staticmethod
    def search_text(insight: CandidateInsight, profile_text: str, cv_text: str) -> str:
        """The text embedded as the candidate's search vector — insight-forward so
        employer role queries land near the right people."""
        return (
            f"{insight.headline}. {insight.seniority}, {insight.years_experience} years. "
            f"Skills: {', '.join(insight.top_skills)}. {insight.market_fit}\n\n"
            f"{cv_text or profile_text}"
        )


async def refresh_candidate(user_id: str, profiles: ProfileRepository, runs: RunRepository) -> bool:
    """Recompute Ada's analysis + the search vector for one candidate. Returns False
    (logged, not raised) if there's nothing to analyse or model creds are missing."""
    profile = await profiles.get(user_id)
    if profile is None or len((profile.profile_text or "").strip()) < 30:
        return False
    cv_text = ""
    for run in await runs.list_by_user(user_id):
        if run.rewritten_cv:
            cv_text = run.rewritten_cv
            break

    service = InsightService()
    insight: CandidateInsight | None = None
    try:
        insight = await service.analyze(profile_text=profile.profile_text, cv_text=cv_text)
    except Exception as exc:  # noqa: BLE001 — generation blocked/absent: fall back to raw embed
        log.warning("insight_analyze_skipped", user_id=user_id, error=str(exc))

    # Embed the insight-forward text when we have it, else the raw profile/CV — so the
    # candidate is still discoverable by Uche even when generation is unavailable.
    embed_text = (
        service.search_text(insight, profile.profile_text, cv_text)
        if insight
        else f"{profile.headline or ''}\n{cv_text or profile.profile_text}"
    )
    vector: list[float] | None = None
    try:
        vector = await service._search.embed(embed_text)
    except Exception as exc:  # noqa: BLE001 — embeddings unavailable too: nothing to store
        log.warning("insight_embed_skipped", user_id=user_id, error=str(exc))

    if insight is None and vector is None:
        return False
    await profiles.set_analysis(
        user_id,
        embedding=vector,
        insights=json.loads(insight.model_dump_json()) if insight else None,
        headline=insight.headline if insight else None,
        location=(insight.location or None) if insight else None,
    )
    return True
