"""Request-scoped auth dependencies."""
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.cookies import set_session_cookie
from ada.auth.repository import AuthRepository
from ada.auth.tokens import hash_token
from ada.config import get_settings
from ada.db.models import User
from ada.db.session import get_session


async def optional_user(
    request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> User | None:
    raw = request.cookies.get(get_settings().session_cookie)
    if not raw:
        return None
    user = await AuthRepository(session).user_for_session(hash_token(raw))
    if user is not None:
        # Keep the browser cookie's lifetime in step with the sliding session.
        set_session_cookie(response, raw)
    return user


async def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return user


async def current_employer(user: User = Depends(current_user)) -> User:
    """Gate for Uche's employer surface — candidates can't reach hiring routes."""
    if user.account_type != "employer":
        raise HTTPException(status_code=403, detail="This area is for employer accounts.")
    return user
