"""Cross-origin trust checks shared by the CSRF guard (HTTP) and the WebSocket handshake.

A missing Origin is allowed on purpose: browsers always send Origin on cross-origin
state-changing requests and WebSocket handshakes, so "no Origin" means a non-browser client
(native app, server-to-server, curl) — not a CSRF/CSWSH vector. A present Origin must be in
the configured allowlist (ALLOWED_ORIGIN); "*" (local dev) trusts everything.
"""
from ada.config import get_settings


def origin_allowed(origin: str | None) -> bool:
    # None / "" / "null" (native apps, opaque origins) are not CSRF vectors — SameSite=Lax
    # already blocks cross-site cookie attachment for those — so they pass.
    if not origin or origin.strip().lower() == "null":
        return True
    s = get_settings()
    if "*" in s.cors_origins:
        return True
    # Mirror the CORS allowlist: ALLOWED_ORIGIN entries plus the configured frontend origin.
    trusted = {o.rstrip("/") for o in s.cors_origins} | {s.frontend_origin.rstrip("/")}
    return origin.rstrip("/") in trusted
