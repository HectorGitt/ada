import os
import uuid

import pytest

_db = pytest.mark.skipif(not os.getenv("RUN_DB_TESTS"), reason="requires Postgres")


def test_match_pct_pure():
    from ada.digest import _match_pct, _within_cooldown

    assert _match_pct(0.0) == 100
    assert _match_pct(1.0) == 0
    assert _match_pct(0.2) == 80
    assert _within_cooldown(None, 100) is False


@_db
async def test_digest_sends_once_then_respects_cooldown():
    from sqlalchemy import delete

    from ada.db.models import Job, Notification, NotificationPref, Profile, User
    from ada.db.repositories import JobRepository, NotificationRepository, ProfileRepository
    from ada.db.session import _session_factory, init_db
    from ada.digest import DIGEST_KIND, run_digest

    await init_db()
    uid = uuid.uuid4().hex
    vec = [0.1] * 768
    job_id = None
    try:
        async with _session_factory() as s:
            s.add(User(id=uid, email=f"{uid}@ex.com", account_type="candidate"))
            await s.commit()
            repo = ProfileRepository(s)
            await repo.upsert(user_id=uid, profile_text="x" * 40, linkedin_url=None)
            await repo.set_identity(user_id=uid, full_name="Ada Tester", phone=None)
            await repo.set_analysis(
                uid, embedding=vec, insights={"headline": "Engineer"},
                headline="Engineer", location="Lagos",
            )
            job = Job(
                source="seed", external_id=uuid.uuid4().hex, title="Backend Engineer",
                company="Acme", location="Lagos", description="build things", embedding=vec,
            )
            await JobRepository(s).add_many([job])
            job_id = job.id

        # first sweep sends the digest to our candidate
        await run_digest()
        async with _session_factory() as s:
            notifs = NotificationRepository(s)
            first = await notifs.last_of_kind(uid, DIGEST_KIND)
            assert first is not None
            digests = [n for n in await notifs.list_for_user(uid) if n.kind == DIGEST_KIND]
            assert len(digests) == 1

        # second sweep inside the cooldown is a no-op
        await run_digest()
        async with _session_factory() as s:
            notifs = NotificationRepository(s)
            digests = [n for n in await notifs.list_for_user(uid) if n.kind == DIGEST_KIND]
            assert len(digests) == 1
    finally:
        async with _session_factory() as s:
            await s.execute(delete(Notification).where(Notification.user_id == uid))
            await s.execute(delete(NotificationPref).where(NotificationPref.user_id == uid))
            if job_id is not None:
                await s.execute(delete(Job).where(Job.id == job_id))
            await s.execute(delete(Profile).where(Profile.user_id == uid))
            await s.execute(delete(User).where(User.id == uid))
            await s.commit()
