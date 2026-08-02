"""Employer surface — Uche posts roles, curates consented candidates, sends intros.

Gated to employer accounts. Job postings join the shared `jobs` pool (source=employer),
so they also become matchable for candidates. Candidate discovery reads only opted-in
profiles (the channel-conflict wall).
"""
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_employer
from ada.config import get_settings
from ada.db.models import Job, ShortlistStage, User
from ada.db.repositories import (
    AssessmentRepository,
    CompanyRepository,
    IntroRepository,
    JobRepository,
    ProfileRepository,
    ShortlistRepository,
    SubscriptionRepository,
)
from ada.db.session import get_session
from ada.observability import log
from ada.payments import plans as plan_catalog
from ada.services import entitlements
from ada.services.notify import notify
from ada.services.search import SearchService
from ada.services.uche import UcheService

router = APIRouter(prefix="/employer", tags=["employer"])


async def _employer_entitlement(
    session: AsyncSession, user_id: str
) -> entitlements.EmployerEntitlement:
    sub = await SubscriptionRepository(session).get(user_id)
    return entitlements.resolve_employer(sub)


class JobIn(BaseModel):
    title: str = Field(min_length=2, max_length=256)
    company: str = Field(min_length=1, max_length=256)
    location: str = Field(default="Remote", max_length=256)
    description: str = Field(min_length=20, max_length=20_000)
    remote: bool = False
    url: str | None = Field(default=None, max_length=1024)


class JobOut(BaseModel):
    id: int
    title: str
    company: str
    location: str
    remote: bool
    description: str


class IntroIn(BaseModel):
    job_id: int
    candidate_id: str
    message: str | None = Field(default=None, max_length=2_000)


async def _embed_job(job_id: int, text: str) -> None:
    from ada.db.session import _session_factory

    try:
        vector = await SearchService().embed(text)
    except Exception as exc:  # noqa: BLE001 — no creds: posting still lands, unembedded
        log.warning("employer_job_embed_skipped", job_id=job_id, error=str(exc))
        return
    async with _session_factory() as session:
        await JobRepository(session).set_embedding(job_id, vector)


@router.post("/jobs", response_model=JobOut, status_code=201)
async def post_job(
    body: JobIn,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    employer: User = Depends(current_employer),
) -> JobOut:
    jobs = JobRepository(session)
    entitlement = await _employer_entitlement(session, employer.id)
    if entitlement.role_limit_reached(len(await jobs.list_by_poster(employer.id))):
        raise HTTPException(
            402,
            f"Your {entitlement.tier} plan covers {entitlement.max_roles} open role — "
            "upgrade to Growth for unlimited roles.",
        )
    job = Job(
        source="employer",
        external_id=uuid.uuid4().hex,
        title=body.title,
        company=body.company or (employer.company or "Company"),
        location=body.location,
        remote=body.remote,
        url=body.url,
        description=body.description,
        posted_by=employer.id,
    )
    job = await jobs.create_posting(job)
    background.add_task(_embed_job, job.id, f"{job.title} at {job.company}. {job.description}")
    return JobOut(
        id=job.id, title=job.title, company=job.company, location=job.location,
        remote=job.remote, description=job.description,
    )


@router.get("/jobs", response_model=list[JobOut])
async def my_jobs(
    session: AsyncSession = Depends(get_session),
    employer: User = Depends(current_employer),
) -> list[JobOut]:
    jobs = await JobRepository(session).list_by_poster(employer.id)
    return [
        JobOut(
            id=j.id, title=j.title, company=j.company, location=j.location,
            remote=j.remote, description=j.description,
        )
        for j in jobs
    ]


@router.get("/jobs/{job_id}/candidates")
async def curated_candidates(
    job_id: int,
    session: AsyncSession = Depends(get_session),
    employer: User = Depends(current_employer),
) -> dict:
    jobs = JobRepository(session)
    job = await jobs.get(job_id)
    if job is None or job.posted_by != employer.id:
        raise HTTPException(404, "Job not found.")
    result = await UcheService().curate(
        job=job, profiles=ProfileRepository(session),
        assessments=AssessmentRepository(session),
    )
    already = await IntroRepository(session).requested_candidate_ids(employer.id, job_id)
    for card in result["candidates"]:
        card["intro_requested"] = card["user_id"] in already
    return result


@router.post("/intros", status_code=201)
async def request_intro(
    body: IntroIn,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    employer: User = Depends(current_employer),
) -> dict:
    jobs = JobRepository(session)
    job = await jobs.get(body.job_id)
    if job is None or job.posted_by != employer.id:
        raise HTTPException(404, "Job not found.")
    candidate = await ProfileRepository(session).get(body.candidate_id)
    if candidate is None or not candidate.discoverable:
        raise HTTPException(404, "Candidate is not available.")
    intros = IntroRepository(session)
    entitlement = await _employer_entitlement(session, employer.id)
    if entitlement.intro_limit_reached(len(await intros.list_for_employer(employer.id))):
        raise HTTPException(
            402,
            f"Your {entitlement.tier} plan includes {entitlement.max_intros} intro — "
            "upgrade to Growth for unlimited intros.",
        )
    intro, created = await intros.create(
        intro_id=uuid.uuid4().hex, employer_id=employer.id, candidate_id=body.candidate_id,
        job_id=body.job_id, message=body.message,
    )
    if created:
        cprofile = await CompanyRepository(session).get(employer.id)
        company = (cprofile.name if cprofile else None) or employer.company or job.company
        page = get_settings().frontend_base_url.rstrip("/") + f"/company/{employer.id}"
        recruiter = (
            f" {cprofile.contact_name} reached out."
            if cprofile and cprofile.contact_name else ""
        )
        body_text = (
            f"{company} is hiring for {job.title} and would like to talk.{recruiter} "
            f"See who they are: {page}\n\nOpen your intros to accept or decline."
        )
        background.add_task(
            notify, body.candidate_id, kind="intro_request",
            title=f"{company} wants to connect", body=body_text,
            link="/app/intros", whatsapp_suffix="Reply YES to connect or NO to pass.",
        )
    return {"intro_id": intro.id, "status": str(intro.status), "already_requested": not created}


@router.get("/intros")
async def my_intros(
    session: AsyncSession = Depends(get_session),
    employer: User = Depends(current_employer),
) -> list[dict]:
    intros = await IntroRepository(session).list_for_employer(employer.id)
    profiles = ProfileRepository(session)
    out = []
    for intro in intros:
        candidate = await profiles.get(intro.candidate_id)
        accepted = str(intro.status) == "accepted"
        # Contact is shared only once the candidate accepts — the handoff that turns
        # an intro into a real conversation, gated by the candidate's own consent.
        contact = None
        if accepted:
            user = await session.get(User, intro.candidate_id)
            contact = {
                "email": user.email if user else None,
                "phone": candidate.phone if candidate else None,
            }
        out.append({
            "id": intro.id,
            "job_id": intro.job_id,
            "candidate_id": intro.candidate_id,
            "candidate_headline": (candidate.insights or {}).get("headline")
            if candidate else None,
            "status": str(intro.status),
            "message": intro.message,
            "created_at": intro.created_at.isoformat(),
            "contact": contact,
        })
    return out


@router.get("/plans")
async def employer_plans() -> list[dict]:
    """The billable employer tiers (Growth, Scale) for the /hire billing page."""
    return [
        {
            "tier": p.tier,
            "name": p.name,
            "tagline": p.tagline,
            "features": list(p.features),
            "monthly": {"ngn_kobo": p.monthly.ngn_kobo, "usd_cents": p.monthly.usd_cents},
            "annual": {"ngn_kobo": p.annual.ngn_kobo, "usd_cents": p.annual.usd_cents},
        }
        for p in plan_catalog.EMPLOYER_CATALOG.values()
    ]


@router.get("/plan")
async def my_plan(
    session: AsyncSession = Depends(get_session),
    employer: User = Depends(current_employer),
) -> dict:
    """Current plan + usage, so the console can show '1 / 1 roles' and gate the UI."""
    ent = await _employer_entitlement(session, employer.id)
    roles_used = len(await JobRepository(session).list_by_poster(employer.id))
    intros_used = len(await IntroRepository(session).list_for_employer(employer.id))
    return {
        "tier": ent.tier,
        "max_roles": ent.max_roles,
        "max_intros": ent.max_intros,
        "placement_support": ent.placement_support,
        "roles_used": roles_used,
        "intros_used": intros_used,
    }


# ── company profile ──────────────────────────────────────────────────────────
_COMPANY_FIELDS = (
    "name", "website", "industry", "size", "location", "about", "logo_url",
    "contact_name", "contact_title",
)


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    website: str | None = Field(default=None, max_length=512)
    industry: str | None = Field(default=None, max_length=120)
    size: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=160)
    about: str | None = Field(default=None, max_length=5000)
    logo_url: str | None = Field(default=None, max_length=1024)
    contact_name: str | None = Field(default=None, max_length=160)
    contact_title: str | None = Field(default=None, max_length=160)


def _company_out(c: object) -> dict:
    return {f: getattr(c, f) for f in _COMPANY_FIELDS}


@router.get("/company")
async def get_company(
    session: AsyncSession = Depends(get_session),
    employer: User = Depends(current_employer),
) -> dict | None:
    c = await CompanyRepository(session).get(employer.id)
    return _company_out(c) if c else None


@router.put("/company")
async def put_company(
    body: CompanyIn,
    session: AsyncSession = Depends(get_session),
    employer: User = Depends(current_employer),
) -> dict:
    c = await CompanyRepository(session).upsert(employer.id, body.model_dump())
    return _company_out(c)


# ── overview (the employer's hiring funnel) ──────────────────────────────────
@router.get("/overview")
async def employer_overview(
    session: AsyncSession = Depends(get_session),
    employer: User = Depends(current_employer),
) -> dict:
    roles = await JobRepository(session).list_by_poster(employer.id)
    intros = await IntroRepository(session).list_for_employer(employer.id)
    funnel = await ShortlistRepository(session).funnel(employer.id)
    ent = await _employer_entitlement(session, employer.id)
    return {
        "roles": len(roles),
        "intros_sent": len(intros),
        "intros_accepted": sum(1 for i in intros if str(i.status) == "accepted"),
        "shortlist_total": sum(funnel.values()),
        "shortlist_funnel": funnel,
        "hires": funnel.get("hired", 0),
        "tier": ent.tier,
    }


# ── talent search (across the consented pool, not just one role) ─────────────
def _talent_card(p: object) -> dict:
    ins = getattr(p, "insights", None) or {}
    return {
        "user_id": p.user_id,  # type: ignore[attr-defined]
        "headline": ins.get("headline") or getattr(p, "headline", None),
        "location": getattr(p, "location", None),
        "seniority": ins.get("seniority"),
        "years_experience": ins.get("years_experience"),
        "top_skills": (ins.get("top_skills") or [])[:8],
        "compensation": getattr(p, "compensation", None) or ins.get("compensation"),
        "work_pref": getattr(p, "work_pref", None) or ins.get("work_pref"),
        "identity_verified": bool(getattr(p, "identity_verified", False)),
    }


@router.get("/candidates")
async def talent_search(
    q: str | None = None,
    location: str | None = None,
    seniority: str | None = None,
    verified: bool = False,
    limit: int = 40,
    session: AsyncSession = Depends(get_session),
    employer: User = Depends(current_employer),
) -> dict:
    profiles = await ProfileRepository(session).search_talent(
        q=q, location=location, seniority=seniority, verified_only=verified,
        exclude=employer.id, limit=min(limit, 100),
    )
    saved = await ShortlistRepository(session).saved_candidate_ids(employer.id)
    return {
        "candidates": [{**_talent_card(p), "saved": p.user_id in saved} for p in profiles]
    }


# ── shortlist (the employer's talent pipeline) ───────────────────────────────
class SaveIn(BaseModel):
    candidate_id: str
    job_id: int | None = None
    note: str | None = Field(default=None, max_length=2_000)


class ShortlistUpdateIn(BaseModel):
    stage: ShortlistStage | None = None
    note: str | None = Field(default=None, max_length=2_000)


@router.post("/shortlist", status_code=201)
async def add_to_shortlist(
    body: SaveIn,
    session: AsyncSession = Depends(get_session),
    employer: User = Depends(current_employer),
) -> dict:
    candidate = await ProfileRepository(session).get(body.candidate_id)
    if candidate is None or not candidate.discoverable:
        raise HTTPException(404, "Candidate is not available.")
    entry = await ShortlistRepository(session).save(
        entry_id=uuid.uuid4().hex, employer_id=employer.id,
        candidate_id=body.candidate_id, job_id=body.job_id, note=body.note,
    )
    return {"ok": True, "stage": str(entry.stage)}


@router.get("/shortlist")
async def get_shortlist(
    session: AsyncSession = Depends(get_session),
    employer: User = Depends(current_employer),
) -> dict:
    repo = ShortlistRepository(session)
    rows = await repo.list_for_employer(employer.id)
    return {
        "funnel": await repo.funnel(employer.id),
        "candidates": [
            {**_talent_card(p), "stage": str(s.stage), "note": s.note,
             "saved_at": s.created_at.isoformat()}
            for s, p in rows
        ],
    }


@router.put("/shortlist/{candidate_id}")
async def update_shortlist(
    candidate_id: str,
    body: ShortlistUpdateIn,
    session: AsyncSession = Depends(get_session),
    employer: User = Depends(current_employer),
) -> dict:
    ok = await ShortlistRepository(session).update(
        employer_id=employer.id, candidate_id=candidate_id, stage=body.stage, note=body.note,
    )
    if not ok:
        raise HTTPException(404, "That candidate isn't in your shortlist.")
    return {"ok": True}


@router.delete("/shortlist/{candidate_id}")
async def remove_from_shortlist(
    candidate_id: str,
    session: AsyncSession = Depends(get_session),
    employer: User = Depends(current_employer),
) -> dict:
    await ShortlistRepository(session).remove(employer_id=employer.id, candidate_id=candidate_id)
    return {"ok": True}
