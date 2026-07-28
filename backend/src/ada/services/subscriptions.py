"""Subscription webhook processing.

Separate from the run-payment path: subscription events are claimed through the same
`processed_events` idempotency ledger (a distinct provider namespace) and drive the
Subscription row's status. Never raises into the webhook — an unmapped or partial event
is a safe no-op. Tiers come only from the configured plan code, never the client.
"""
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.repository import AuthRepository
from ada.db.models import SubscriptionStatus
from ada.db.repositories import EventRepository, SubscriptionRepository
from ada.observability import log
from ada.payments.plans import resolve_plan

_PAYSTACK_CANCEL = {"subscription.disable", "subscription.not_renew"}
_STRIPE_SUB_EVENTS = {"customer.subscription.updated", "customer.subscription.deleted"}


def _epoch(value: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), tz=UTC) if value else None
    except (TypeError, ValueError):
        return None


def _iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def is_paystack_subscription(event: dict[str, Any]) -> bool:
    etype = event.get("event")
    data = event.get("data") or {}
    return etype in _PAYSTACK_CANCEL or etype == "subscription.create" or (
        etype == "charge.success" and bool(data.get("plan"))
    )


def is_stripe_subscription(event: dict[str, Any]) -> bool:
    etype = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}
    return etype in _STRIPE_SUB_EVENTS or (
        etype == "checkout.session.completed" and obj.get("mode") == "subscription"
    )


async def _claim(session: AsyncSession, namespace: str, ref: str) -> bool:
    return await EventRepository(session).claim(namespace, ref)


async def handle_paystack(session: AsyncSession, event: dict[str, Any]) -> dict[str, str]:
    etype = str(event.get("event"))
    data = event.get("data") or {}
    sub_code = data.get("subscription_code") or (data.get("subscription") or {}).get("code")
    ref = f"{etype}:{data.get('id') or sub_code or ''}"
    if not await _claim(session, "paystack_sub", ref):
        return {"status": "duplicate"}

    repo = SubscriptionRepository(session)
    if etype in _PAYSTACK_CANCEL:
        if sub_code:
            await repo.set_status(sub_code, SubscriptionStatus.CANCELED)
        return {"status": "canceled"}

    plan_code = (data.get("plan") or {}).get("plan_code")
    email = (data.get("customer") or {}).get("email")
    resolved = resolve_plan("paystack", plan_code) if plan_code else None
    if not (resolved and email and sub_code):
        log.info("paystack_sub_unmapped", event=etype, has_plan=bool(plan_code))
        return {"status": "ignored"}
    user = await AuthRepository(session).get_user_by_email(email)
    if user is None:
        return {"status": "no_user"}
    tier, cadence = resolved
    await repo.activate(
        user_id=user.id, tier=tier, cadence=cadence, provider="paystack",
        provider_ref=sub_code, current_period_end=_iso(data.get("next_payment_date")),
    )
    return {"status": "active"}


async def handle_stripe(session: AsyncSession, event: dict[str, Any]) -> dict[str, str]:
    etype = str(event.get("type"))
    obj = (event.get("data") or {}).get("object") or {}
    ref = f"{etype}:{obj.get('id') or ''}"
    if not await _claim(session, "stripe_sub", ref):
        return {"status": "duplicate"}

    repo = SubscriptionRepository(session)
    if etype == "customer.subscription.deleted":
        await repo.set_status(str(obj.get("id")), SubscriptionStatus.CANCELED)
        return {"status": "canceled"}

    if etype == "customer.subscription.updated":
        status = (
            SubscriptionStatus.ACTIVE
            if obj.get("status") in ("active", "trialing")
            else SubscriptionStatus.PAST_DUE
            if obj.get("status") in ("past_due", "unpaid")
            else SubscriptionStatus.CANCELED
        )
        await repo.set_status(
            str(obj.get("id")), status, current_period_end=_epoch(obj.get("current_period_end"))
        )
        return {"status": status.value}

    # checkout.session.completed (mode=subscription): first activation.
    meta = obj.get("metadata") or {}
    user_id = meta.get("user_id") or obj.get("client_reference_id")
    tier, cadence = meta.get("tier"), meta.get("cadence")
    sub_id = obj.get("subscription")
    if not (user_id and tier and cadence and sub_id):
        return {"status": "ignored"}
    await repo.activate(
        user_id=str(user_id), tier=str(tier), cadence=str(cadence), provider="stripe",
        provider_ref=str(sub_id), current_period_end=None,
    )
    return {"status": "active"}
