"""Verification credential — the candidate takes a proctored, role-specific assessment
and (separately) attests identity. The result is the evidence employers see via Uche.

The rubric behind each question stays server-side; the client only ever sees prompts,
then returns answers + proctoring telemetry (tab-switches, blur seconds, paste events,
duration) which the score is gated on.
"""
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_user
from ada.config import get_settings
from ada.db.models import Assessment, AssessmentStatus, User
from ada.db.repositories import AssessmentRepository, ProfileRepository
from ada.db.session import get_session
from ada.services.verification import VerificationService

router = APIRouter(tags=["verification"])


class StartIn(BaseModel):
    skill: str = Field(min_length=2, max_length=160)


class Integrity(BaseModel):
    tab_switches: int = Field(default=0, ge=0)
    blur_seconds: float = Field(default=0, ge=0)
    paste_events: int = Field(default=0, ge=0)


class SubmitIn(BaseModel):
    assessment_id: str
    answers: list[str] = Field(max_length=20)
    integrity: Integrity = Field(default_factory=Integrity)


def _started_at(a: Assessment) -> datetime:
    started = a.started_at
    return started if started.tzinfo else started.replace(tzinfo=UTC)


def _credential(assessment: Assessment | None, identity_verified: bool) -> dict:
    if assessment is None or assessment.status != AssessmentStatus.SCORED:
        return {"identity_verified": identity_verified, "assessment": None}
    return {
        "identity_verified": identity_verified,
        "assessment": {
            "skill": assessment.skill,
            "score": assessment.score,
            "verdict": str(assessment.verdict) if assessment.verdict else None,
            "method": (assessment.evidence or {}).get("method"),
            "summary": (assessment.evidence or {}).get("summary"),
            "taken_at": assessment.submitted_at.isoformat() if assessment.submitted_at else None,
        },
    }


def _task_out(a: Assessment, *, time_limit: int) -> dict:
    # Only prompts leave the server — never the rubric (looks_for).
    remaining = max(0, time_limit - int((datetime.now(UTC) - _started_at(a)).total_seconds()))
    return {
        "assessment_id": a.id,
        "skill": a.skill,
        "questions": [q.get("prompt", "") for q in a.questions],
        "time_limit_seconds": time_limit,
        "seconds_remaining": remaining,
    }


@router.post("/assessment/start")
async def start_assessment(
    body: StartIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    s = get_settings()
    skill = body.skill.strip()
    repo = AssessmentRepository(session)

    # Resume an in-flight task instead of issuing fresh questions — a candidate can't
    # farm the question bank by hitting start repeatedly.
    pending = await repo.pending_for(user.id, skill)
    if pending is not None:
        if (datetime.now(UTC) - _started_at(pending)).total_seconds() < s.verify_time_limit_seconds:
            return _task_out(pending, time_limit=s.verify_time_limit_seconds)

    # Cooldown between finished attempts.
    last = await repo.last_submitted_at(user.id, skill)
    if last is not None:
        last = last if last.tzinfo else last.replace(tzinfo=UTC)
        if (datetime.now(UTC) - last).total_seconds() < s.verify_retake_cooldown_seconds:
            raise HTTPException(429, "You just took this assessment — try again a bit later.")

    # Rolling attempt cap per skill.
    since = datetime.now(UTC) - timedelta(seconds=s.verify_attempt_window_seconds)
    if await repo.recent_attempt_count(user.id, skill, since) >= s.verify_max_attempts:
        raise HTTPException(429, "You've reached the attempt limit for this skill today.")

    questions = await VerificationService().issue_task(skill)
    assessment = await repo.create(
        Assessment(id=uuid.uuid4().hex, user_id=user.id, skill=skill,
                   questions=questions, status=AssessmentStatus.PENDING)
    )
    return _task_out(assessment, time_limit=s.verify_time_limit_seconds)


@router.post("/assessment/submit")
async def submit_assessment(
    body: SubmitIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    s = get_settings()
    repo = AssessmentRepository(session)
    assessment = await repo.get(body.assessment_id)
    if assessment is None or assessment.user_id != user.id:
        raise HTTPException(404, "Assessment not found.")
    if assessment.status == AssessmentStatus.SCORED:
        raise HTTPException(409, "This assessment was already submitted.")
    if len(body.answers) != len(assessment.questions):
        raise HTTPException(422, "Answer count doesn't match the questions.")

    # Duration is server-authoritative (start→now), never trusted from the client;
    # blowing the limit flags the result as un-certifiable.
    duration = int((datetime.now(UTC) - _started_at(assessment)).total_seconds())
    integrity = {**body.integrity.model_dump(), "over_time": duration > s.verify_time_limit_seconds}

    score, verdict, evidence = await VerificationService().score(
        skill=assessment.skill, questions=assessment.questions, answers=body.answers,
        integrity=integrity, duration_seconds=duration,
    )
    await repo.record_result(
        assessment.id, answers=body.answers, integrity=integrity,
        duration_seconds=duration, score=score, verdict=verdict, evidence=evidence,
    )
    return {"score": score, "verdict": str(verdict), "summary": evidence.get("summary")}


@router.get("/assessment")
async def my_credential(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    assessment = await AssessmentRepository(session).latest_for_user(user.id)
    profile = await ProfileRepository(session).get(user.id)
    return _credential(assessment, bool(profile and profile.identity_verified))


@router.post("/candidate/identity/attest")
async def attest_identity(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """v1 self-attestation (candidate affirms their legal identity). A real KYC provider
    (e.g. Smile Identity for Africa) slots in here later behind the same flag."""
    profile = await ProfileRepository(session).get(user.id)
    if profile is None or not (profile.full_name or "").strip():
        raise HTTPException(428, "Add your full name before verifying your identity.")
    await ProfileRepository(session).set_identity_verified(user.id, method="attested")
    return {"identity_verified": True, "method": "attested"}
