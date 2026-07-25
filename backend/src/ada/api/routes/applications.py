"""One-click apply and application tracking."""
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_user
from ada.config import get_settings
from ada.db.models import ApplicationStatus, RunStatus, User
from ada.db.repositories import (
    ApplicationRepository,
    JobRepository,
    ProfileRepository,
    RunRepository,
)
from ada.db.session import get_session
from ada.services.apply import (
    ApplyPrecondition,
    build_answers,
    is_supported,
    latest_cv_markdown,
    run_submission,
)

router = APIRouter(tags=["applications"])


class ApplicationOut(BaseModel):
    id: str
    job_id: int
    title: str
    company: str
    location: str
    status: str
    detail: str | None
    submitted_at: str | None
    created_at: str


class ApplyIn(BaseModel):
    run_id: str | None = None


class ApplyOut(BaseModel):
    application_id: str
    status: str
    already_applied: bool


async def _cv_for_apply(
    runs: RunRepository, user_id: str, run_id: str | None
) -> tuple[str, str] | None:
    if run_id is not None:
        run = await runs.get(run_id)
        if (
            run is not None
            and run.user_id == user_id
            and run.status == RunStatus.COMPLETE
            and run.rewritten_cv
        ):
            return run.rewritten_cv, run.id
    return await latest_cv_markdown(runs, user_id)


@router.post("/jobs/{job_id}/apply", response_model=ApplyOut, status_code=202)
async def apply_to_job(
    job_id: int,
    background: BackgroundTasks,
    body: ApplyIn | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> ApplyOut:
    applications = ApplicationRepository(session)
    job = await JobRepository(session).get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found.")
    if not is_supported(job):
        raise HTTPException(422, "This listing has no application page on file.")
    in_flight = await applications.count_in_flight(user.id)
    if in_flight >= get_settings().apply_max_in_flight_per_user:
        raise HTTPException(
            429, "A few applications are still in progress — let those finish first."
        )
    cv = await _cv_for_apply(RunRepository(session), user.id, body.run_id if body else None)
    if cv is None:
        raise HTTPException(409, "Complete a run first — Ada applies with your rewritten CV.")
    profile = await ProfileRepository(session).get(user.id)
    try:
        build_answers(user, profile, cv[0])
    except ApplyPrecondition as exc:
        raise HTTPException(428, str(exc)) from exc

    application, created = await applications.create_or_get(
        application_id=uuid.uuid4().hex, user_id=user.id, job_id=job_id, run_id=cv[1]
    )
    dispatch = created
    if not created and application.status in (
        ApplicationStatus.NEEDS_ATTENTION,
        ApplicationStatus.FAILED,
    ):
        dispatch = await applications.claim_for_retry(application.id)
    if dispatch:
        background.add_task(run_submission, application.id)
    return ApplyOut(
        application_id=application.id,
        status="preparing" if dispatch else str(application.status),
        already_applied=not dispatch,
    )


@router.get("/applications", response_model=list[ApplicationOut])
async def list_applications(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> list[ApplicationOut]:
    rows = await ApplicationRepository(session).list_by_user(user.id)
    return [
        ApplicationOut(
            id=application.id,
            job_id=job.id,
            title=job.title,
            company=job.company,
            location=job.location,
            status=str(application.status),
            detail=application.detail,
            submitted_at=application.submitted_at.isoformat()
            if application.submitted_at
            else None,
            created_at=application.created_at.isoformat(),
        )
        for application, job in rows
    ]
