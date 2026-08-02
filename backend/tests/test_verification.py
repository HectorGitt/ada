import os
import uuid

import pytest

from ada.db.models import AssessmentVerdict
from ada.services.verification import VerificationService, _heuristic, integrity_ok

_db = pytest.mark.skipif(not os.getenv("RUN_DB_TESTS"), reason="requires Postgres")

CLEAN = {"paste_events": 0, "tab_switches": 0, "blur_seconds": 0, "over_time": False}


def test_integrity_gate():
    assert integrity_ok(CLEAN) is True
    assert integrity_ok({**CLEAN, "paste_events": 1}) is False       # any paste
    assert integrity_ok({**CLEAN, "tab_switches": 5}) is False       # too many switches
    assert integrity_ok({**CLEAN, "blur_seconds": 45}) is False      # long off-tab
    assert integrity_ok({**CLEAN, "over_time": True}) is False       # blew the clock


def test_integrity_gate_camera_for_voice_video():
    """Camera gates apply only to voice+camera sessions, not the written fallback."""
    written = {**CLEAN, "mode": "written", "camera_present": False}
    assert integrity_ok(written) is True  # written mode ignores the camera

    live = {**CLEAN, "mode": "voice_video", "camera_present": True, "face_absent_seconds": 0}
    assert integrity_ok(live) is True
    assert integrity_ok({**live, "camera_present": False}) is False      # camera off
    assert integrity_ok({**live, "face_absent_seconds": 60}) is False    # face out of frame


def test_heuristic_rewards_substance():
    assert _heuristic("") == 20
    assert _heuristic("too short") == 20
    substantial = "I led the migration over 6 weeks, cutting p95 latency by 40% across 3 services."
    assert _heuristic(substantial) >= 40
    assert _heuristic(substantial) > _heuristic("too short")


def _svc(pass_mark: int = 60) -> VerificationService:
    svc = VerificationService.__new__(VerificationService)  # skip __init__ (no vertex client)
    svc._pass_mark = pass_mark
    return svc


async def test_verdict_requires_clean_proctoring_and_pass():
    svc = _svc()

    async def grade_high(skill, questions, answers):
        return 82, [], "strong", "heuristic"

    svc._grade = grade_high  # type: ignore[method-assign]

    # clean + above the bar -> verified
    score, verdict, ev = await svc.score(
        skill="x", questions=[], answers=[], integrity=CLEAN, duration_seconds=120
    )
    assert score == 82 and verdict == AssessmentVerdict.VERIFIED and ev["integrity_clean"] is True

    # a high score with a proctoring flag is never certified
    _, dirty, _ = await svc.score(
        skill="x", questions=[], answers=[],
        integrity={**CLEAN, "paste_events": 1}, duration_seconds=120,
    )
    assert dirty == AssessmentVerdict.NEEDS_REVIEW

    # clean but below the bar -> failed
    async def grade_low(skill, questions, answers):
        return 40, [], "thin", "heuristic"

    svc._grade = grade_low  # type: ignore[method-assign]
    _, low, _ = await svc.score(
        skill="x", questions=[], answers=[], integrity=CLEAN, duration_seconds=120
    )
    assert low == AssessmentVerdict.FAILED


@_db
async def test_assessment_repo_lifecycle_and_antifarm():
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import delete

    from ada.db.models import Assessment, AssessmentStatus, User
    from ada.db.repositories import AssessmentRepository
    from ada.db.session import _session_factory, init_db

    await init_db()
    uid = uuid.uuid4().hex
    try:
        async with _session_factory() as s:
            s.add(User(id=uid, email=f"{uid}@ex.com"))
            await s.commit()
            repo = AssessmentRepository(s)
            a = await repo.create(
                Assessment(id=uuid.uuid4().hex, user_id=uid, skill="Python",
                           questions=[{"prompt": "q", "looks_for": "x"}],
                           status=AssessmentStatus.PENDING)
            )
            # anti-farm: a pending assessment is found + reused, not re-issued
            assert (await repo.pending_for(uid, "Python")).id == a.id
            assert await repo.pending_for(uid, "Sales") is None
            assert await repo.latest_scored(uid) is None

            await repo.record_result(
                a.id, answers=["real answer"], integrity=CLEAN, duration_seconds=90,
                score=75, verdict=AssessmentVerdict.VERIFIED, evidence={"method": "heuristic"},
            )
            scored = await repo.latest_scored(uid)
            assert scored is not None and scored.score == 75
            assert await repo.pending_for(uid, "Python") is None   # no longer pending
            assert await repo.last_submitted_at(uid, "Python") is not None

            since = datetime.now(UTC) - timedelta(hours=1)
            assert await repo.recent_attempt_count(uid, "Python", since) == 1
        # cleanup
        async with _session_factory() as s:
            await s.execute(delete(Assessment).where(Assessment.user_id == uid))
            await s.execute(delete(User).where(User.id == uid))
            await s.commit()
    except Exception:
        async with _session_factory() as s:
            await s.execute(delete(Assessment).where(Assessment.user_id == uid))
            await s.execute(delete(User).where(User.id == uid))
            await s.commit()
        raise
