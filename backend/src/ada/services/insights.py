"""Ada's structured read of a candidate — the analysis that makes a profile
elaborate for the candidate and searchable for Uche.

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
    experience: list[str] = Field(
        default_factory=list, description="Up to 5 recent roles as 'Title — Company (dates)'"
    )
    education: str = Field(default="", description="Highest/most relevant qualification, if stated")
    top_skills: list[str] = Field(default_factory=list, description="5-10 concrete skills")
    strengths: list[str] = Field(default_factory=list, description="2-4 evidence-backed strengths")
    growth_areas: list[str] = Field(default_factory=list, description="1-3 development areas")
    compensation: str = Field(default="", description="Pay expectation, only if explicitly stated")
    work_pref: str = Field(default="", description="remote, hybrid, onsite, or empty if unstated")
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
        pref = f" Prefers {insight.work_pref} work." if insight.work_pref else ""
        return (
            f"{insight.headline}. {insight.seniority}, {insight.years_experience} years. "
            f"Skills: {', '.join(insight.top_skills)}.{pref} {insight.market_fit}\n\n"
            f"{cv_text or profile_text}"
        )


async def refresh_candidate(user_id: str, profiles: ProfileRepository, runs: RunRepository) -> bool:
    """Recompute Ada's analysis + the search vector for one candidate. Returns False
    (logged, not raised) if there's nothing to analyse or model creds are missing."""
    profile = await profiles.get(user_id)
    if profile is None or len((profile.profile_text or "").strip()) < 30:
        return False
    # The first time Ada forms a read is the moment to reach out (email + WhatsApp) with
    # what she sees — the "she gets me" hello. Recomputes after that stay silent.
    first_read = profile.insights is None
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
    if insight is not None and first_read:
        await _greet_with_read(user_id, insight)
    return True


async def _greet_with_read(user_id: str, insight: CandidateInsight) -> None:
    """Ada's first hello: message the candidate (email + WhatsApp) with what she sees, and
    seed a few durable memories so she remembers them in chat. All best-effort — a reach-out
    must never break the analysis that triggered it."""
    from ada.services.notify import notify

    body = insight.summary.strip()
    if insight.experience:
        body += "\n\nWhat I noted: " + "; ".join(insight.experience[:2]) + "."
    try:
        await notify(
            user_id, kind="ada_read",
            title=f"Ada here — I read your profile: {insight.headline}",
            body=body, link="/app/profile",
        )
    except Exception as exc:  # noqa: BLE001 — reach-out is best-effort
        log.warning("ada_read_notify_failed", user_id=user_id, error=str(exc))

    await _remember_experience(user_id, insight)


def _experience_facts(insight: CandidateInsight) -> list[str]:
    """A few durable facts about the candidate's background, for Ada's long-term memory."""
    facts: list[str] = []
    if insight.years_experience:
        facts.append(f"{insight.years_experience} years' experience as {insight.headline}.")
    facts.extend(f"Experience: {role}" for role in insight.experience[:2])
    if insight.top_skills:
        facts.append("Key skills: " + ", ".join(insight.top_skills[:6]) + ".")
    return facts


async def _remember_experience(user_id: str, insight: CandidateInsight) -> None:
    """Persist Ada's read as long-term memory so 'Ask Ada' recalls their background."""
    from ada.db.repositories import UserMemoryRepository
    from ada.db.session import _session_factory

    facts = _experience_facts(insight)
    if not facts:
        return
    try:
        vectors = await SearchService().embed_many(facts)
        async with _session_factory() as session:
            await UserMemoryRepository(session).add_many(
                user_id, list(zip(facts, vectors, strict=True)), source="onboarding"
            )
    except Exception as exc:  # noqa: BLE001 — embeddings may be unavailable; memory is optional
        log.warning("ada_read_memory_skipped", user_id=user_id, error=str(exc))
