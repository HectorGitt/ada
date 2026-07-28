import os
import uuid

import pytest

from ada.services.insights import CandidateInsight, InsightService
from ada.services.uche import _candidate_brief, _fit

_db = pytest.mark.skipif(not os.getenv("RUN_DB_TESTS"), reason="requires Postgres")


def _insight() -> CandidateInsight:
    return CandidateInsight(
        headline="Sales Manager, FMCG",
        seniority="senior",
        years_experience=8,
        location="Lagos",
        top_skills=["Key account management", "Distribution", "Team leadership"],
        strengths=["Grew territory revenue 40%"],
        growth_areas=["Formal data analysis"],
        market_fit="Strong for commercial leadership roles in consumer goods.",
        readiness_score=82,
        summary="You present as a seasoned commercial leader.",
    )


def test_fit_maps_distance_to_percent():
    assert _fit(0.0) == 100
    assert _fit(1.0) == 0
    assert _fit(0.25) == 75
    assert _fit(2.0) == 0  # clamped, never negative


def test_search_text_is_insight_forward():
    out = InsightService.search_text(_insight(), "profile body", "cv body")
    assert "Sales Manager, FMCG" in out
    assert "Key account management" in out
    assert "cv body" in out  # CV preferred over profile when present


def test_candidate_brief_indexes_and_summarizes():
    class P:
        insights = {
            "headline": "Sales Manager, FMCG", "seniority": "senior",
            "years_experience": 8, "top_skills": ["A", "B"], "market_fit": "FMCG leadership",
        }
        headline = None

    brief = _candidate_brief(P(), 3)
    assert brief.startswith("[3]")
    assert "Sales Manager" in brief and "FMCG leadership" in brief


@_db
async def test_candidate_search_respects_consent_and_exclusion():
    from sqlalchemy import delete

    from ada.db.models import Profile, User
    from ada.db.repositories import ProfileRepository
    from ada.db.session import _session_factory, init_db

    await init_db()
    ids = [uuid.uuid4().hex for _ in range(3)]
    vec = [0.1] * 768
    try:
        async with _session_factory() as s:
            for uid in ids:
                s.add(User(id=uid, email=f"{uid}@ex.com"))
            await s.commit()
            repo = ProfileRepository(s)
            # discoverable + embedded
            await repo.upsert(user_id=ids[0], profile_text="x" * 40, linkedin_url=None)
            await repo.set_discoverable(ids[0], True)
            await repo.set_analysis(
                ids[0], embedding=vec, insights={"headline": "A"}, headline="A", location=None
            )
            # embedded but NOT discoverable -> excluded
            await repo.upsert(user_id=ids[1], profile_text="y" * 40, linkedin_url=None)
            await repo.set_analysis(
                ids[1], embedding=vec, insights={"headline": "B"}, headline="B", location=None
            )
            # discoverable but the searcher themselves -> excluded via exclude=
            await repo.upsert(user_id=ids[2], profile_text="z" * 40, linkedin_url=None)
            await repo.set_discoverable(ids[2], True)
            await repo.set_analysis(
                ids[2], embedding=vec, insights={"headline": "C"}, headline="C", location=None
            )

            found = await repo.search_candidates(vec, 10, exclude=ids[2])
            found_ids = {p.user_id for p, _ in found}
            assert ids[0] in found_ids
            assert ids[1] not in found_ids  # not discoverable
            assert ids[2] not in found_ids  # excluded searcher
    finally:
        async with _session_factory() as s:
            await s.execute(delete(Profile).where(Profile.user_id.in_(ids)))
            await s.execute(delete(User).where(User.id.in_(ids)))
            await s.commit()


@_db
async def test_intro_is_idempotent_and_account_switch_persists():
    from sqlalchemy import delete

    from ada.db.models import Intro, Job, User
    from ada.db.repositories import IntroRepository, JobRepository, UserRepository
    from ada.db.session import _session_factory, init_db

    await init_db()
    emp, cand = uuid.uuid4().hex, uuid.uuid4().hex
    job_id = None
    try:
        async with _session_factory() as s:
            s.add(User(id=emp, email=f"{emp}@ex.com"))
            s.add(User(id=cand, email=f"{cand}@ex.com"))
            await s.commit()
            await UserRepository(s).set_account(emp, account_type="employer", company="Acme")
            job = Job(
                source="employer", external_id=uuid.uuid4().hex, title="Sales Manager",
                company="Acme", location="Lagos", description="desc", posted_by=emp,
            )
            job = await JobRepository(s).create_posting(job)
            job_id = job.id

            repo = IntroRepository(s)
            first, c1 = await repo.create(
                intro_id=uuid.uuid4().hex, employer_id=emp, candidate_id=cand,
                job_id=job_id, message="Hi",
            )
            second, c2 = await repo.create(
                intro_id=uuid.uuid4().hex, employer_id=emp, candidate_id=cand,
                job_id=job_id, message="again",
            )
            assert c1 and not c2
            assert first.id == second.id
            assert await repo.requested_candidate_ids(emp, job_id) == {cand}

            reloaded = await UserRepository(s).get(emp)
            assert reloaded is not None and reloaded.account_type == "employer"
            assert reloaded.company == "Acme"
    finally:
        async with _session_factory() as s:
            await s.execute(delete(Intro).where(Intro.employer_id == emp))
            if job_id is not None:
                await s.execute(delete(Job).where(Job.id == job_id))
            await s.execute(delete(User).where(User.id.in_([emp, cand])))
            await s.commit()
