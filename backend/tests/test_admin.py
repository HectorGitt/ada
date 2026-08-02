import os
import uuid

import pytest
from fastapi import HTTPException

_db = pytest.mark.skipif(not os.getenv("RUN_DB_TESTS"), reason="requires Postgres")


async def test_require_admin_allows_allowlisted_and_rejects_others(monkeypatch):
    from ada.auth import admin as adm
    from ada.db.models import User

    class _S:
        admin_email_set = {"boss@ada.dev"}

    monkeypatch.setattr(adm, "get_settings", lambda: _S())

    # Case-insensitive match on the allowlist.
    ok = await adm.require_admin(User(id="1", email="Boss@ada.dev"))
    assert ok.id == "1"

    with pytest.raises(HTTPException) as exc:
        await adm.require_admin(User(id="2", email="rando@example.com"))
    assert exc.value.status_code == 403


@_db
async def test_audit_survives_user_deletion_and_overview_shape():
    from sqlalchemy import delete

    from ada.db.models import AdminAudit, Profile, User
    from ada.db.repositories import AdminRepository
    from ada.db.session import _session_factory, init_db

    await init_db()
    uid = uuid.uuid4().hex
    try:
        async with _session_factory() as s:
            s.add(User(id=uid, email=f"{uid}@ex.com"))
            await s.commit()
            s.add(Profile(user_id=uid, profile_text="cv", full_name="Test User"))
            await s.commit()

        async with _session_factory() as s:
            repo = AdminRepository(s)
            await repo.record_audit(
                admin_email="boss@ada.dev", action="delete_user", target_user_id=uid,
                detail={"email": f"{uid}@ex.com"},
            )
            # Delete the user; the child Profile must go, the audit row must remain.
            await repo.delete_user(uid)

        async with _session_factory() as s:
            assert await s.get(User, uid) is None
            assert await s.get(Profile, uid) is None
            repo = AdminRepository(s)
            trail = await repo.list_audit(limit=50)
            mine = [a for a in trail if a.target_user_id == uid]
            assert mine and mine[0].action == "delete_user"  # audit outlives the deletion

            ov = await repo.overview()
            for key in ("users_total", "runs_by_status", "subscriptions_by_tier", "revenue"):
                assert key in ov
    finally:
        async with _session_factory() as s:
            await s.execute(delete(AdminAudit).where(AdminAudit.target_user_id == uid))
            await s.execute(delete(Profile).where(Profile.user_id == uid))
            await s.execute(delete(User).where(User.id == uid))
            await s.commit()
