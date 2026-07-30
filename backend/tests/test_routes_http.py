"""Route-layer tests: real HTTP through the ASGI app against Postgres.

Exercises the wiring the unit tests can't — auth/DI, the employer-account gate,
the entitlement caps (402), and status codes — end to end.
"""
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

_db = pytest.mark.skipif(not os.getenv("RUN_DB_TESTS"), reason="requires Postgres")

ROLE = {
    "title": "Regional Sales Manager",
    "company": "Acme Foods",
    "location": "Lagos",
    "description": "Lead the commercial team across the region. " + "context " * 6,
    "remote": False,
}


def _client() -> AsyncClient:
    from ada.main import create_app

    return AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test")


async def _cleanup(user_id: str) -> None:
    from sqlalchemy import delete, text

    from ada.db.models import Job, Profile, Session, Subscription, User
    from ada.db.session import _session_factory

    async with _session_factory() as s:
        await s.execute(text("DELETE FROM notifications WHERE user_id = :u"), {"u": user_id})
        await s.execute(text("DELETE FROM intros WHERE employer_id = :u"), {"u": user_id})
        await s.execute(delete(Job).where(Job.posted_by == user_id))
        await s.execute(delete(Session).where(Session.user_id == user_id))
        await s.execute(delete(Subscription).where(Subscription.user_id == user_id))
        await s.execute(delete(Profile).where(Profile.user_id == user_id))
        await s.execute(delete(User).where(User.id == user_id))
        await s.commit()


@_db
async def test_unauthenticated_routes_401():
    async with _client() as c:
        assert (await c.get("/api/employer/jobs")).status_code == 401
        assert (await c.get("/api/candidate/intros")).status_code == 401
        assert (await c.get("/api/auth/me")).status_code == 401
        assert (await c.get("/api/healthz")).status_code == 200  # open


@_db
async def test_account_gate_and_employer_role_cap():
    user_id = ""
    async with _client() as c:
        email = f"{uuid.uuid4().hex}@example.com"
        signup = await c.post("/api/auth/signup", json={"email": email, "password": "password123"})
        assert signup.status_code == 201

        me = (await c.get("/api/auth/me")).json()
        user_id = None  # resolved below via DB
        assert me["account_type"] == "candidate"

        # candidate cannot reach the employer surface
        assert (await c.get("/api/employer/jobs")).status_code == 403

        # become an employer
        switch = await c.put(
            "/api/account", json={"account_type": "employer", "company": "Acme Foods"}
        )
        assert switch.status_code == 200
        assert (await c.get("/api/auth/me")).json()["account_type"] == "employer"

        # first role on the free Pilot tier: allowed
        first = await c.post("/api/employer/jobs", json=ROLE)
        assert first.status_code == 201

        # second role hits the Pilot cap (max_roles=1) -> 402 upgrade
        second = await c.post("/api/employer/jobs", json=ROLE)
        assert second.status_code == 402
        assert "upgrade" in second.json()["detail"].lower()

        plan = (await c.get("/api/employer/plan")).json()
        assert plan["tier"] == "pilot"
        assert plan["roles_used"] == 1
        assert plan["max_roles"] == 1

        # resolve the user id for cleanup
        from sqlalchemy import select

        from ada.db.models import User
        from ada.db.session import _session_factory

        async with _session_factory() as s:
            user_id = (await s.execute(select(User.id).where(User.email == email))).scalar_one()
    await _cleanup(user_id)


@_db
async def test_candidate_intro_respond_validation():
    user_id = ""
    async with _client() as c:
        email = f"{uuid.uuid4().hex}@example.com"
        await c.post("/api/auth/signup", json={"email": email, "password": "password123"})

        # empty inbox
        assert (await c.get("/api/candidate/intros")).json() == []
        # responding to a non-existent intro is a clean 404
        r = await c.post("/api/candidate/intros/nope/respond", json={"action": "accept"})
        assert r.status_code == 404
        # bad action is a 422
        r = await c.post("/api/candidate/intros/nope/respond", json={"action": "maybe"})
        assert r.status_code == 422

        from sqlalchemy import select

        from ada.db.models import User
        from ada.db.session import _session_factory

        async with _session_factory() as s:
            user_id = (await s.execute(select(User.id).where(User.email == email))).scalar_one()
    await _cleanup(user_id)
