import os
import uuid

import pytest

_db = pytest.mark.skipif(not os.getenv("RUN_DB_TESTS"), reason="requires Postgres")


@_db
async def test_outcome_pipeline_lifecycle():
    """Seed is idempotent per (user, job); the candidate advances a stage; the funnel
    counts each stage; and one user can't touch another's outcome."""
    from sqlalchemy import delete

    from ada.db.models import Job, Outcome, OutcomeStage, User
    from ada.db.repositories import OutcomeRepository
    from ada.db.session import _session_factory, init_db

    await init_db()
    uid = uuid.uuid4().hex
    other = uuid.uuid4().hex
    job_id: int | None = None
    try:
        async with _session_factory() as s:
            s.add(User(id=uid, email=f"{uid}@ex.com"))
            s.add(User(id=other, email=f"{other}@ex.com"))
            job = Job(source="test", external_id=uuid.uuid4().hex, title="Staff Engineer",
                      company="Acme", location="Remote", description="build things")
            s.add(job)
            await s.commit()
            job_id = job.id

        async with _session_factory() as s:
            repo = OutcomeRepository(s)
            # First seed creates; second is a no-op (idempotent).
            await repo.seed(user_id=uid, job_id=job_id, company="Acme",
                            role_title="Staff Engineer", source="one_click")
            await repo.seed(user_id=uid, job_id=job_id, company="Acme",
                            role_title="Staff Engineer", source="one_click")
            rows = await repo.list_by_user(uid)
            assert len(rows) == 1
            assert rows[0].stage == OutcomeStage.APPLIED
            outcome_id = rows[0].id

            # A manual add for a role tracked elsewhere.
            await repo.create_manual(user_id=uid, company="Globex",
                                     role_title="Director", stage=OutcomeStage.INTERVIEWING)

            # Advance the seeded one to hired.
            updated = await repo.set_stage(outcome_id=outcome_id, user_id=uid,
                                           stage=OutcomeStage.HIRED)
            assert updated is not None and updated.stage == OutcomeStage.HIRED

            # A different user cannot move it.
            assert await repo.set_stage(outcome_id=outcome_id, user_id=other,
                                        stage=OutcomeStage.APPLIED) is None

            funnel = await repo.funnel(uid)
            assert funnel.get("hired") == 1
            assert funnel.get("interviewing") == 1
    finally:
        async with _session_factory() as s:
            await s.execute(delete(Outcome).where(Outcome.user_id.in_([uid, other])))
            if job_id is not None:
                await s.execute(delete(Job).where(Job.id == job_id))
            await s.execute(delete(User).where(User.id.in_([uid, other])))
            await s.commit()
