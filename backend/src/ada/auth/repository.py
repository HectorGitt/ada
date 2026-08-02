"""Auth data access: users, password-reset tokens, sessions.

create_user_with_password inserts atomically and returns None if the email is taken,
so signup can't create duplicate accounts under a race. consume_reset_token is atomic
(UPDATE ... WHERE used_at IS NULL) so a reset link clicked twice resets at most once.
"""
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ada.config import get_settings
from ada.db.models import AuthToken, Session, User

RESET_TOKEN_TTL = timedelta(minutes=30)


def _session_ttl() -> timedelta:
    return timedelta(days=get_settings().session_ttl_days)


def _now() -> datetime:
    return datetime.now(UTC)


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create_user_with_password(
        self, email: str, password_hash: str
    ) -> User | None:
        """Insert a new user. Returns None if the email is already registered."""
        email = email.lower().strip()
        stmt = (
            insert(User)
            .values(id=uuid.uuid4().hex, email=email, password_hash=password_hash)
            .on_conflict_do_nothing(index_elements=["email"])
            .returning(User.id)
        )
        inserted_id = (await self._s.execute(stmt)).scalar_one_or_none()
        if inserted_id is None:
            await self._s.rollback()
            return None
        await self._s.commit()
        return await self._s.get(User, inserted_id)

    async def get_user(self, user_id: str) -> User | None:
        return await self._s.get(User, user_id)

    async def get_user_by_email(self, email: str) -> User | None:
        email = email.lower().strip()
        return (
            await self._s.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

    async def set_password(self, user_id: str, password_hash: str) -> None:
        await self._s.execute(
            update(User).where(User.id == user_id).values(password_hash=password_hash)
        )
        await self._s.commit()

    async def create_reset_token(self, user_id: str, token_hash: str) -> None:
        # One outstanding reset per user: minting invalidates earlier unused tokens.
        await self._s.execute(
            delete(AuthToken).where(AuthToken.user_id == user_id, AuthToken.used_at.is_(None))
        )
        self._s.add(
            AuthToken(user_id=user_id, token_hash=token_hash, expires_at=_now() + RESET_TOKEN_TTL)
        )
        await self._s.commit()

    async def consume_reset_token(self, token_hash: str) -> str | None:
        """Mark the token used and return its user_id; None if invalid/expired/used."""
        stmt = (
            update(AuthToken)
            .where(
                AuthToken.token_hash == token_hash,
                AuthToken.used_at.is_(None),
                AuthToken.expires_at > _now(),
            )
            .values(used_at=_now())
            .returning(AuthToken.user_id)
        )
        user_id = (await self._s.execute(stmt)).scalar_one_or_none()
        await self._s.commit()
        return user_id

    async def create_session(self, user_id: str, token_hash: str) -> None:
        self._s.add(
            Session(user_id=user_id, token_hash=token_hash, expires_at=_now() + _session_ttl())
        )
        await self._s.commit()

    async def user_for_session(self, token_hash: str) -> User | None:
        """Resolve a live session to its user, sliding its expiry when it's past the
        halfway mark — so an active user never gets logged out, but an idle one lapses
        after the TTL. The write is bounded (only past halfway), not once per request."""
        stmt = (
            select(User, Session)
            .join(Session, Session.user_id == User.id)
            .where(Session.token_hash == token_hash, Session.expires_at > _now())
        )
        row = (await self._s.execute(stmt)).first()
        if row is None:
            return None
        user, sess = row
        ttl = _session_ttl()
        if sess.expires_at < _now() + ttl / 2:
            await self._s.execute(
                update(Session)
                .where(Session.token_hash == token_hash)
                .values(expires_at=_now() + ttl)
            )
            await self._s.commit()
        return user

    async def destroy_session(self, token_hash: str) -> None:
        await self._s.execute(delete(Session).where(Session.token_hash == token_hash))
        await self._s.commit()

    async def destroy_user_sessions(self, user_id: str) -> None:
        """Revoke every session for a user — used after a password reset."""
        await self._s.execute(delete(Session).where(Session.user_id == user_id))
        await self._s.commit()
