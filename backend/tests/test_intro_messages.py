import os
import uuid

import pytest

_db = pytest.mark.skipif(not os.getenv("RUN_DB_TESTS"), reason="requires Postgres")


@_db
async def test_intro_thread_add_and_list_in_order():
    from sqlalchemy import delete

    from ada.db.models import Intro, IntroMessage, IntroStatus, Job, User
    from ada.db.repositories import IntroMessageRepository
    from ada.db.session import _session_factory, init_db

    await init_db()
    emp, cand = uuid.uuid4().hex, uuid.uuid4().hex
    intro_id = uuid.uuid4().hex
    job_id: int | None = None
    try:
        async with _session_factory() as s:
            s.add(User(id=emp, email=f"{emp}@co.com", account_type="employer", company="Acme"))
            s.add(User(id=cand, email=f"{cand}@ex.com"))
            await s.commit()
            job = Job(source="test", external_id=uuid.uuid4().hex, title="Engineer",
                      company="Acme", location="Remote", description="build")
            s.add(job)
            await s.commit()
            job_id = job.id
            s.add(Intro(id=intro_id, employer_id=emp, candidate_id=cand, job_id=job_id,
                        message="hi", status=IntroStatus.ACCEPTED))
            await s.commit()

        async with _session_factory() as s:
            repo = IntroMessageRepository(s)
            await repo.add(intro_id=intro_id, sender="employer", body="Hello, keen to talk?")
            await repo.add(intro_id=intro_id, sender="candidate", body="Yes — Tuesday works.")
            thread = await repo.list_for_intro(intro_id)
            assert [m.sender for m in thread] == ["employer", "candidate"]  # chronological
            assert thread[1].body == "Yes — Tuesday works."
    finally:
        async with _session_factory() as s:
            await s.execute(delete(IntroMessage).where(IntroMessage.intro_id == intro_id))
            await s.execute(delete(Intro).where(Intro.id == intro_id))
            if job_id is not None:
                await s.execute(delete(Job).where(Job.id == job_id))
            await s.execute(delete(User).where(User.id.in_([emp, cand])))
            await s.commit()
