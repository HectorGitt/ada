import os
import uuid

import pytest

_db = pytest.mark.skipif(not os.getenv("RUN_DB_TESTS"), reason="requires Postgres")


@_db
async def test_one_user_cannot_delete_anothers_push_subscription():
    """Ownership guard (audit #2): delete is scoped to (user_id, endpoint), so knowing a
    victim's endpoint isn't enough to unsubscribe them."""
    from sqlalchemy import delete

    from ada.db.models import PushSubscription, User
    from ada.db.repositories import PushSubscriptionRepository
    from ada.db.session import _session_factory, init_db

    await init_db()
    victim, attacker = uuid.uuid4().hex, uuid.uuid4().hex
    endpoint = f"https://fcm.googleapis.com/{uuid.uuid4().hex}"
    try:
        async with _session_factory() as s:
            s.add(User(id=victim, email=f"{victim}@ex.com"))
            s.add(User(id=attacker, email=f"{attacker}@ex.com"))
            await s.commit()

        async with _session_factory() as s:
            repo = PushSubscriptionRepository(s)
            await repo.upsert(user_id=victim, endpoint=endpoint, p256dh="k" * 60, auth="a" * 20)

            # Attacker knows the endpoint but not the owner — delete must be a no-op.
            await repo.delete(user_id=attacker, endpoint=endpoint)
            assert len(await repo.list_for_user(victim)) == 1

            # The real owner can remove it.
            await repo.delete(user_id=victim, endpoint=endpoint)
            assert len(await repo.list_for_user(victim)) == 0
    finally:
        async with _session_factory() as s:
            await s.execute(
                delete(PushSubscription).where(PushSubscription.user_id.in_([victim, attacker]))
            )
            await s.execute(delete(User).where(User.id.in_([victim, attacker])))
            await s.commit()
