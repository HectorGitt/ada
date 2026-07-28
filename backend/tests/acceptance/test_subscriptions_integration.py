"""Money-path: subscription webhook lifecycle is idempotent and drives entitlements.

A replayed activation must not double-apply; a disable must revoke access. Same
`processed_events` ledger as the run path, distinct namespace.
"""
import os
import uuid

import pytest

_db = pytest.mark.skipif(not os.getenv("RUN_DB_TESTS"), reason="requires Postgres")


@_db
async def test_paystack_subscription_lifecycle_idempotent(monkeypatch):
    from sqlalchemy import delete

    from ada.config import get_settings
    from ada.db.models import ProcessedEvent, Subscription, User
    from ada.db.repositories import SubscriptionRepository
    from ada.db.session import _session_factory, init_db
    from ada.services import entitlements
    from ada.services.subscriptions import handle_paystack

    monkeypatch.setenv("PAYSTACK_PLANS", '{"pro_monthly": "PLN_test"}')
    get_settings.cache_clear()
    await init_db()

    email = f"{uuid.uuid4().hex}@example.com"
    user_id = uuid.uuid4().hex
    sub_code = f"SUB_{uuid.uuid4().hex[:8]}"
    async with _session_factory() as s:
        s.add(User(id=user_id, email=email))
        await s.commit()

    created = {
        "event": "subscription.create",
        "data": {
            "id": 5001, "subscription_code": sub_code,
            "plan": {"plan_code": "PLN_test"},
            "customer": {"email": email},
            "next_payment_date": "2026-08-26T00:00:00Z",
        },
    }
    try:
        async with _session_factory() as s:
            assert (await handle_paystack(s, created))["status"] == "active"
        # Replay the exact event — must be a no-op, not a second application.
        async with _session_factory() as s:
            assert (await handle_paystack(s, created))["status"] == "duplicate"

        async with _session_factory() as s:
            sub = await SubscriptionRepository(s).get(user_id)
            assert sub is not None and sub.tier == "pro"
            assert entitlements.resolve(sub).included_runs

        disable = {"event": "subscription.disable",
                   "data": {"id": 5002, "subscription_code": sub_code}}
        async with _session_factory() as s:
            assert (await handle_paystack(s, disable))["status"] == "canceled"
        async with _session_factory() as s:
            sub = await SubscriptionRepository(s).get(user_id)
            assert entitlements.resolve(sub).tier == "free"  # access revoked
    finally:
        get_settings.cache_clear()
        async with _session_factory() as s:
            await s.execute(delete(Subscription).where(Subscription.user_id == user_id))
            await s.execute(
                delete(ProcessedEvent).where(ProcessedEvent.provider == "paystack_sub")
            )
            await s.execute(delete(User).where(User.id == user_id))
            await s.commit()
