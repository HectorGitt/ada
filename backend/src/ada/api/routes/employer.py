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
from ada.db.models import Job, User
from ada.db.repositories import (
    AssessmentRepository,
    IntroRepository,
    JobRepository,
    ProfileRepository,
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
        company = employer.company or job.company
        background.add_task(
            notify, body.candidate_id, kind="intro_request",
            title=f"{company} wants to connect",
            body=f"{company} is hiring for {job.title} and would like to talk. "
                 "Open your intros to accept or decline.",
            link="/app/intros",
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
