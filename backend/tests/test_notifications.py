import os
import uuid

import pytest

_db = pytest.mark.skipif(not os.getenv("RUN_DB_TESTS"), reason="requires Postgres")


@_db
async def test_notification_repository_lifecycle():
    from sqlalchemy import delete

    from ada.db.models import Notification, User
    from ada.db.repositories import NotificationRepository
    from ada.db.session import _session_factory, init_db

    await init_db()
    uid = uuid.uuid4().hex
    try:
        async with _session_factory() as s:
            s.add(User(id=uid, email=f"{uid}@ex.com"))
            await s.commit()
            repo = NotificationRepository(s)
            n1 = await repo.add(
                notification_id=uuid.uuid4().hex, user_id=uid, kind="welcome",
                title="Welcome", body="hi", link="/app/new",
            )
            await repo.add(
                notification_id=uuid.uuid4().hex, user_id=uid, kind="run_complete",
                title="Run ready", body=None, link="/app/runs/1",
            )
            assert await repo.unread_count(uid) == 2
            assert len(await repo.list_for_user(uid)) == 2

            await repo.mark_read(uid, n1.id)           # one
            assert await repo.unread_count(uid) == 1
            await repo.mark_read(uid, None)            # all
            assert await repo.unread_count(uid) == 0
    finally:
        async with _session_factory() as s:
            await s.execute(delete(Notification).where(Notification.user_id == uid))
            await s.execute(delete(User).where(User.id == uid))
            await s.commit()


@_db
async def test_notify_writes_inapp_and_tolerates_missing_channels():
    """notify() always records the in-app row; email logs locally and WhatsApp is
    skipped without a phone — neither should raise."""
    from sqlalchemy import delete

    from ada.db.models import Notification, User
    from ada.db.repositories import NotificationRepository
    from ada.db.session import _session_factory, init_db
    from ada.services.notify import notify

    await init_db()
    uid = uuid.uuid4().hex
    try:
        async with _session_factory() as s:
            s.add(User(id=uid, email=f"{uid}@ex.com"))
            await s.commit()

        await notify(uid, kind="intro_request", title="An employer wants to connect",
                     body="Acme is hiring", link="/app/intros")

        async with _session_factory() as s:
            items = await NotificationRepository(s).list_for_user(uid)
            assert len(items) == 1
            assert items[0].kind == "intro_request"
            assert items[0].link == "/app/intros"
    finally:
        async with _session_factory() as s:
            from ada.db.models import NotificationPref

            await s.execute(delete(Notification).where(Notification.user_id == uid))
            await s.execute(delete(NotificationPref).where(NotificationPref.user_id == uid))
            await s.execute(delete(User).where(User.id == uid))
            await s.commit()


@_db
async def test_notification_prefs_and_unsubscribe():
    from sqlalchemy import delete

    from ada.db.models import NotificationPref, User
    from ada.db.repositories import NotificationPrefRepository
    from ada.db.session import _session_factory, init_db

    await init_db()
    uid = uuid.uuid4().hex
    try:
        async with _session_factory() as s:
            s.add(User(id=uid, email=f"{uid}@ex.com"))
            await s.commit()
            repo = NotificationPrefRepository(s)
            pref = await repo.get_or_create(uid)
            assert pref.email_enabled and pref.whatsapp_enabled and pref.digest_enabled
            assert pref.unsubscribe_token
            token = pref.unsubscribe_token
            assert (await repo.get_or_create(uid)).unsubscribe_token == token

            updated = await repo.update(uid, email=False, whatsapp=True, digest=False)
            assert updated.email_enabled is False and updated.digest_enabled is False

            assert (await repo.by_token(token)).user_id == uid
            assert await repo.unsubscribe_all(token) is True
            after = await repo.get_or_create(uid)
            assert not (after.email_enabled or after.whatsapp_enabled or after.digest_enabled)
            assert await repo.unsubscribe_all("nope") is False
    finally:
        async with _session_factory() as s:
            await s.execute(delete(NotificationPref).where(NotificationPref.user_id == uid))
            await s.execute(delete(User).where(User.id == uid))
            await s.commit()
