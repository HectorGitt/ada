"""Admin gate for the admin dashboard.

Admin is decided solely by the ADMIN_EMAILS allowlist in config — it can never be set
from inside the app, so a compromised account can't escalate itself. Every admin route
depends on `require_admin`.
"""
from fastapi import Depends, HTTPException

from ada.auth.dependencies import current_user
from ada.config import get_settings
from ada.db.models import User


async def require_admin(user: User = Depends(current_user)) -> User:
    if user.email.lower() not in get_settings().admin_email_set:
        raise HTTPException(403, "Admin access required.")
    return user
