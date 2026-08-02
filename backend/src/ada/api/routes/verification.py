"""Verification credential — the candidate takes a proctored, role-specific assessment
and (separately) attests identity. The result is the evidence employers see via Uche.

The rubric behind each question stays server-side; the client only ever sees prompts,
then returns answers + proctoring telemetry (tab-switches, blur seconds, paste events,
duration) which the score is gated on.
"""
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_user
from ada.config import get_settings
from ada.db.models import Assessment, AssessmentStatus, User
from ada.db.repositories import AssessmentRepository, ProfileRepository
from ada.db.session import get_session
from ada.services import kyc
from ada.services.ats import split_name
from ada.services.verification import VerificationService, store_proctor_snapshots

router = APIRouter(tags=["verification"])


class StartIn(BaseModel):
    skill: str = Field(min_length=2, max_length=160)


class Integrity(BaseModel):
    tab_switches: int = Field(default=0, ge=0)
    blur_seconds: float = Field(default=0, ge=0)
    paste_events: int = Field(default=0, ge=0)
    # Voice + camera-monitored sessions add liveness signals. mode "written" is the
    # keyboard fallback and ignores the camera gates.
    mode: Literal["written", "voice_video"] = "written"
    camera_present: bool = True
    face_absent_seconds: float = Field(default=0, ge=0)


class SubmitIn(BaseModel):
    assessment_id: str
    answers: list[str] = Field(max_length=20)
    integrity: Integrity = Field(default_factory=Integrity)
    # Liveness snapshots (data URLs) from a voice+camera session — a few frames kept as
    # proctoring evidence, never full video. Capped; oversized frames are dropped server-side.
    snapshots: list[str] = Field(default_factory=list, max_length=8)


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


@router.get("/assessment/active")
async def active_assessment(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """The candidate's in-flight assessment, if any — so a refresh can resume it instead of
    losing the session. Expired (past the time limit) counts as none; the timer is
    server-authoritative, so `seconds_remaining` is always the truth."""
    s = get_settings()
    pending = await AssessmentRepository(session).active_for_user(user.id)
    if pending is None:
        return {"active": None}
    elapsed = (datetime.now(UTC) - _started_at(pending)).total_seconds()
    if elapsed >= s.verify_time_limit_seconds:
        return {"active": None}
    return {"active": _task_out(pending, time_limit=s.verify_time_limit_seconds)}


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

    # Persist a few liveness frames as proctoring evidence (best-effort; GCS-gated).
    snapshot_refs = await store_proctor_snapshots(user.id, assessment.id, body.snapshots)

    score, verdict, evidence = await VerificationService().score(
        skill=assessment.skill, questions=assessment.questions, answers=body.answers,
        integrity=integrity, duration_seconds=duration,
    )
    evidence["snapshots"] = {"captured": len(body.snapshots), "stored": snapshot_refs}
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
    """Self-attestation fallback (candidate affirms their legal identity) — used when KYC
    isn't configured or a candidate has no verifiable government ID on hand."""
    profile = await ProfileRepository(session).get(user.id)
    if profile is None or not (profile.full_name or "").strip():
        raise HTTPException(428, "Add your full name before verifying your identity.")
    await ProfileRepository(session).set_identity_verified(user.id, method="attested")
    return {"identity_verified": True, "method": "attested"}


class IdVerifyIn(BaseModel):
    id_type: str = Field(min_length=2, max_length=32)
    id_number: str = Field(min_length=3, max_length=64)
    dob: str | None = Field(default=None, max_length=10)  # YYYY-MM-DD, when the ID needs it


@router.get("/candidate/identity/methods")
async def identity_methods() -> dict:
    """What the identity step should offer: real KYC when configured, else attestation."""
    return {"kyc_enabled": kyc.is_configured(), "id_types": sorted(kyc.SUPPORTED_ID_TYPES)}


@router.post("/candidate/identity/verify")
async def verify_identity(
    body: IdVerifyIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Real KYC: check a government ID against the candidate's name via Smile Identity.
    On a match, the identity half of the credential flips to verified with the ID type
    recorded. Falls back to attestation (503) when KYC isn't configured."""
    profile = await ProfileRepository(session).get(user.id)
    full_name = (profile.full_name if profile else "") or ""
    if not full_name.strip():
        raise HTTPException(428, "Add your full name before verifying your identity.")
    first, last = split_name(full_name.strip())
    try:
        result = await kyc.verify_id(
            id_type=body.id_type.upper(), id_number=body.id_number.strip(),
            first_name=first, last_name=last, dob=body.dob, user_id=user.id,
        )
    except kyc.KycNotConfigured as exc:
        raise HTTPException(
            503, "ID verification isn't available yet — you can self-attest."
        ) from exc
    except kyc.KycError as exc:
        raise HTTPException(502, str(exc)) from exc

    if not result.verified:
        raise HTTPException(422, result.detail)
    await ProfileRepository(session).set_identity_verified(
        user.id, method=f"smile:{body.id_type.lower()}"
    )
    return {"identity_verified": True, "method": f"smile:{body.id_type.lower()}"}
