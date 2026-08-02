"""Session cookie — one place that knows how the cookie is written, so login and the
sliding-refresh on each request stay in lock-step (same name, flags, and lifetime)."""
from fastapi import Response

from ada.config import get_settings


def set_session_cookie(resp: Response, raw: str) -> None:
    s = get_settings()
    resp.set_cookie(
        key=s.session_cookie,
        value=raw,
        httponly=True,
        secure=s.app_env != "local",
        samesite="lax",
        max_age=s.session_ttl_days * 24 * 3600,
        path="/",
    )
