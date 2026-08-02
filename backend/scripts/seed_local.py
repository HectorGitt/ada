"""Seed local dev accounts: an admin, a Premium candidate, and a Scale employer.

Idempotent — re-running resets the passwords and re-grants the plans. Local use only.
    python scripts/seed_local.py
"""
import asyncio
from datetime import UTC, datetime, timedelta

from ada.auth.passwords import hash_password
from ada.auth.repository import AuthRepository
from ada.db.repositories import SubscriptionRepository, UserRepository
from ada.db.session import _session_factory, init_db

PASSWORD = "AdaLocal2026!"
ACCOUNTS = [
    {"email": "admin@adalocal.io", "type": "candidate", "company": None,
     "tier": None, "label": "Admin (/admin dashboard)"},
    {"email": "candidate@adalocal.io", "type": "candidate", "company": None,
     "tier": "premium", "label": "Candidate — Premium"},
    {"email": "employer@adalocal.io", "type": "employer", "company": "Acme Inc",
     "tier": "scale", "label": "Employer — Scale"},
]


async def main() -> None:
    await init_db()
    until = datetime.now(UTC) + timedelta(days=365)
    async with _session_factory() as s:
        auth, users, subs = AuthRepository(s), UserRepository(s), SubscriptionRepository(s)
        print("\nSeeded local accounts (password is the same for all):\n")
        for a in ACCOUNTS:
            user = await auth.create_user_with_password(a["email"], hash_password(PASSWORD))
            if user is None:  # already exists — reset its password so the login is known
                user = await auth.get_user_by_email(a["email"])
                assert user is not None
                await auth.set_password(user.id, hash_password(PASSWORD))
            await users.set_account(user.id, account_type=a["type"], company=a["company"])
            if a["tier"]:
                await subs.activate(
                    user_id=user.id, tier=a["tier"], cadence="annual",
                    provider="comp", provider_ref="seed:local", current_period_end=until,
                )
            print(f"  {a['label']:26}  {a['email']:22}  {PASSWORD}")
    print("\nAdmin access needs admin@adalocal.io in ADMIN_EMAILS (already set in .env).\n")


if __name__ == "__main__":
    asyncio.run(main())
