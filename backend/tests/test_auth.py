"""Auth unit tests (no DB) + Postgres-gated integration tests for the auth lifecycle."""
import os
import uuid

import pytest

from ada.auth.passwords import hash_password, verify_password
from ada.auth.tokens import hash_token, mint


def test_mint_returns_distinct_raw_and_hash():
    raw, token_hash = mint()
    assert raw != token_hash
    assert hash_token(raw) == token_hash
    assert len(token_hash) == 64  # sha256 hex


def test_mint_is_unique():
    assert mint()[0] != mint()[0]


def test_password_hash_round_trip():
    h = hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"
    assert verify_password("correct horse battery staple", h)
    assert not verify_password("wrong password", h)


def test_password_hash_is_salted():
    # Same password hashes differently each time; both still verify.
    a = hash_password("hunter2hunter2")
    b = hash_password("hunter2hunter2")
    assert a != b
    assert verify_password("hunter2hunter2", a)
    assert verify_password("hunter2hunter2", b)


def test_verify_rejects_malformed_hash():
    assert not verify_password("anything", "not-a-bcrypt-hash")


_db = pytest.mark.skipif(not os.getenv("RUN_DB_TESTS"), reason="requires Postgres")


@_db
async def test_signup_is_unique_per_email():
    from ada.auth.repository import AuthRepository
    from ada.db.session import _session_factory, init_db

    await init_db()
    email = f"{uuid.uuid4().hex}@example.com"
    async with _session_factory() as s:
        repo = AuthRepository(s)
        first = await repo.create_user_with_password(email, hash_password("pw-one-123"))
        assert first is not None
        # Same email (case-insensitive) can't create a second account.
        dup = await repo.create_user_with_password(email.upper(), hash_password("pw-two-456"))
        assert dup is None


@_db
async def test_login_lookup_and_password_verify():
    from ada.auth.repository import AuthRepository
    from ada.db.session import _session_factory, init_db

    await init_db()
    email = f"{uuid.uuid4().hex}@example.com"
    async with _session_factory() as s:
        repo = AuthRepository(s)
        await repo.create_user_with_password(email, hash_password("s3cret-password"))
        user = await repo.get_user_by_email(email.upper())  # case-insensitive lookup
        assert user is not None and user.password_hash is not None
        assert verify_password("s3cret-password", user.password_hash)
        assert not verify_password("nope", user.password_hash)


@_db
async def test_reset_token_single_use_and_sets_password():
    from ada.auth.repository import AuthRepository
    from ada.db.session import _session_factory, init_db

    await init_db()
    email = f"{uuid.uuid4().hex}@example.com"
    async with _session_factory() as s:
        repo = AuthRepository(s)
        user = await repo.create_user_with_password(email, hash_password("old-password-1"))
        assert user is not None
        raw, token_hash = mint()
        await repo.create_reset_token(user.id, token_hash)
        assert await repo.consume_reset_token(token_hash) == user.id
        assert await repo.consume_reset_token(token_hash) is None  # single-use

        await repo.set_password(user.id, hash_password("new-password-2"))
        refreshed = await repo.get_user_by_email(email)
        assert refreshed is not None and refreshed.password_hash is not None
        assert verify_password("new-password-2", refreshed.password_hash)
        assert not verify_password("old-password-1", refreshed.password_hash)


@_db
async def test_session_round_trip_and_destroy():
    from ada.auth.repository import AuthRepository
    from ada.db.session import _session_factory, init_db

    await init_db()
    email = f"{uuid.uuid4().hex}@example.com"
    async with _session_factory() as s:
        repo = AuthRepository(s)
        user = await repo.create_user_with_password(email, hash_password("session-pw-1"))
        assert user is not None
        raw, token_hash = mint()
        await repo.create_session(user.id, token_hash)
        found = await repo.user_for_session(token_hash)
        assert found is not None and found.email == email
        await repo.destroy_session(token_hash)
        assert await repo.user_for_session(token_hash) is None


@_db
async def test_session_slides_on_use_but_not_when_expired():
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select, update

    from ada.auth.repository import AuthRepository, _session_ttl
    from ada.db.models import Session
    from ada.db.session import _session_factory, init_db

    await init_db()
    email = f"{uuid.uuid4().hex}@example.com"
    async with _session_factory() as s:
        repo = AuthRepository(s)
        user = await repo.create_user_with_password(email, hash_password("pw"))
        assert user is not None
        raw, token_hash = mint()
        await repo.create_session(user.id, token_hash)

        # Age it past the halfway mark → a use should slide the expiry back to ~full TTL.
        await s.execute(
            update(Session)
            .where(Session.token_hash == token_hash)
            .values(expires_at=datetime.now(UTC) + timedelta(minutes=1))
        )
        await s.commit()
        assert await repo.user_for_session(token_hash) is not None
        slid = (
            await s.execute(select(Session).where(Session.token_hash == token_hash))
        ).scalar_one()
        assert slid.expires_at > datetime.now(UTC) + _session_ttl() / 2

        # An already-expired session is never resurrected.
        await s.execute(
            update(Session)
            .where(Session.token_hash == token_hash)
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await s.commit()
        assert await repo.user_for_session(token_hash) is None


@_db
async def test_reset_revokes_all_sessions():
    from ada.auth.repository import AuthRepository
    from ada.db.session import _session_factory, init_db

    await init_db()
    email = f"{uuid.uuid4().hex}@example.com"
    async with _session_factory() as s:
        repo = AuthRepository(s)
        user = await repo.create_user_with_password(email, hash_password("multi-device-1"))
        assert user is not None
        tokens = [mint() for _ in range(2)]
        for _raw, th in tokens:
            await repo.create_session(user.id, th)
        await repo.destroy_user_sessions(user.id)
        for _raw, th in tokens:
            assert await repo.user_for_session(th) is None
