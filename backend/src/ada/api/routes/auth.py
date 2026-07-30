"""Email + password authentication.

signup and login mint the same opaque session cookie; login returns a generic 401 on
any bad-credential case so it can't be used to probe which emails exist. request-reset
always returns 202 regardless of whether the email exists, so it can't enumerate
accounts either. reset consumes its token atomically and revokes existing sessions.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_user
from ada.auth.mailer import send_reset_link
from ada.auth.passwords import hash_password, verify_password
from ada.auth.repository import AuthRepository
from ada.auth.tokens import hash_token, mint
from ada.config import get_settings
from ada.db.models import User
from ada.db.session import get_session
from ada.observability import log
from ada.services.notify import notify

router = APIRouter(prefix="/auth", tags=["auth"])

# A password long enough to matter; the 72-byte bcrypt cap sets the practical ceiling.
Password = Field(min_length=8, max_length=200)


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Password


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RequestResetIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str = Password


def _set_session_cookie(resp: Response, raw: str) -> None:
    s = get_settings()
    resp.set_cookie(
        key=s.session_cookie,
        value=raw,
        httponly=True,
        secure=s.app_env != "local",
        samesite="lax",
        max_age=30 * 24 * 3600,
        path="/",
    )


async def _start_session(repo: AuthRepository, user_id: str, resp: Response) -> None:
    raw, token_hash = mint()
    await repo.create_session(user_id, token_hash)
    _set_session_cookie(resp, raw)


@router.post("/signup", status_code=201)
async def signup(
    body: SignupIn,
    response: Response,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    repo = AuthRepository(session)
    user = await repo.create_user_with_password(body.email, hash_password(body.password))
    if user is None:
        # Email taken. Surfaced plainly: signup can't be passwordless-probed for existence,
        # and hiding this only pushes the same information to the login form.
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    await _start_session(repo, user.id, response)
    background.add_task(
        notify, user.id, kind="welcome",
        title="Welcome to Ada",
        body="I'm Ada — tell me the role you're after and I'll rewrite your CV, find your "
             "best-fit jobs, and prep your interview. Start your first run when you're ready.",
        link="/app/new", whatsapp=False,
    )
    return {"email": user.email}


@router.post("/login")
async def login(
    body: LoginIn, response: Response, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    repo = AuthRepository(session)
    user = await repo.get_user_by_email(body.email)
    if user is None or user.password_hash is None or not verify_password(
        body.password, user.password_hash
    ):
        # One generic error for every failure mode — no account enumeration.
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    await _start_session(repo, user.id, response)
    return {"email": user.email}


@router.post("/request-reset", status_code=202)
async def request_reset(
    body: RequestResetIn, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    s = get_settings()
    repo = AuthRepository(session)
    user = await repo.get_user_by_email(body.email)
    # Always 202: never reveal whether the email is registered.
    if user is not None:
        raw, token_hash = mint()
        await repo.create_reset_token(user.id, token_hash)
        link = f"{s.frontend_origin}/auth/reset?token={raw}"
        try:
            await send_reset_link(user.email, link)
        except RuntimeError as exc:
            log.error("reset_link_delivery_failed", error=str(exc))
            raise HTTPException(status_code=502, detail="email delivery failed") from exc
    return {"status": "sent"}


@router.post("/reset")
async def reset(
    body: ResetIn, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    repo = AuthRepository(session)
    user_id = await repo.consume_reset_token(hash_token(body.token))
    if user_id is None:
        raise HTTPException(status_code=400, detail="This reset link is invalid or expired.")
    await repo.set_password(user_id, hash_password(body.password))
    # Revoke every existing session — a reset should log out other devices.
    await repo.destroy_user_sessions(user_id)
    return {"status": "ok"}


@router.get("/me")
async def me(user: User = Depends(current_user)) -> dict[str, str | None]:
    return {"email": user.email, "account_type": user.account_type, "company": user.company}


@router.post("/logout")
async def logout(
    request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    s = get_settings()
    raw = request.cookies.get(s.session_cookie)
    if raw:
        await AuthRepository(session).destroy_session(hash_token(raw))
    response.delete_cookie(s.session_cookie, path="/")
    return {"status": "ok"}
