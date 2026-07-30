"""Subscription plans, checkout, status, and cancellation."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_user
from ada.db.models import SubscriptionStatus, User
from ada.db.repositories import SubscriptionRepository
from ada.db.session import get_session
from ada.payments import plans as plan_catalog
from ada.payments import stripe as stripe_pay
from ada.payments.paystack import disable_subscription, subscription_checkout
from ada.services import entitlements

router = APIRouter(tags=["subscriptions"])


class PriceOut(BaseModel):
    ngn_kobo: int
    usd_cents: int


class PlanOut(BaseModel):
    tier: str
    name: str
    tagline: str
    features: list[str]
    monthly: PriceOut
    annual: PriceOut


class SubscriptionOut(BaseModel):
    tier: str
    status: str
    cadence: str
    current_period_end: str | None
    can_apply: bool
    can_voice: bool


class CheckoutIn(BaseModel):
    tier: str
    cadence: str
    provider: str


@router.get("/plans", response_model=list[PlanOut])
async def list_plans() -> list[PlanOut]:
    return [
        PlanOut(
            tier=p.tier, name=p.name, tagline=p.tagline, features=list(p.features),
            monthly=PriceOut(ngn_kobo=p.monthly.ngn_kobo, usd_cents=p.monthly.usd_cents),
            annual=PriceOut(ngn_kobo=p.annual.ngn_kobo, usd_cents=p.annual.usd_cents),
        )
        for p in plan_catalog.CATALOG.values()
    ]


@router.get("/subscription", response_model=SubscriptionOut)
async def my_subscription(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> SubscriptionOut:
    sub = await SubscriptionRepository(session).get(user.id)
    ent = entitlements.resolve(sub)
    return SubscriptionOut(
        tier=ent.tier,
        status=sub.status if sub else "none",
        cadence=sub.cadence if sub else "monthly",
        current_period_end=sub.current_period_end.isoformat()
        if sub and sub.current_period_end
        else None,
        can_apply=ent.can_apply,
        can_voice=ent.can_voice,
    )


@router.post("/subscriptions", status_code=201)
async def start_subscription(
    body: CheckoutIn, user: User = Depends(current_user)
) -> dict[str, str]:
    if body.tier not in plan_catalog.ALL_PLANS or body.cadence not in plan_catalog.CADENCES:
        raise HTTPException(422, "Unknown plan or billing cycle.")
    if body.provider not in ("paystack", "stripe"):
        raise HTTPException(422, "Unknown payment provider.")
    code = plan_catalog.provider_code(body.provider, body.tier, body.cadence)
    if not code:
        raise HTTPException(
            503, "This plan isn't available for that provider yet — try the other one."
        )
    try:
        if body.provider == "paystack":
            url = await subscription_checkout(
                email=user.email, plan_code=code, reference=uuid.uuid4().hex
            )
        else:
            url = await run_in_threadpool(
                stripe_pay.create_subscription_checkout,
                email=user.email, price_id=code, user_id=user.id,
                tier=body.tier, cadence=body.cadence,
            )
    except Exception as exc:  # noqa: BLE001 — checkout init failure -> clean 502
        raise HTTPException(502, "Couldn't start checkout — try again.") from exc
    return {"checkout_url": url}


@router.post("/subscriptions/cancel")
async def cancel_subscription(
    session: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> dict[str, str]:
    repo = SubscriptionRepository(session)
    sub = await repo.get(user.id)
    if sub is None or sub.status == SubscriptionStatus.CANCELED or not sub.provider_ref:
        raise HTTPException(409, "No active subscription to cancel.")
    try:
        if sub.provider == "paystack":
            await disable_subscription(sub.provider_ref)
        else:
            await run_in_threadpool(stripe_pay.cancel_subscription, sub.provider_ref)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, "Couldn't reach the payment provider — try again.") from exc
    # The provider webhook confirms the final state; reflect the request immediately.
    await repo.set_status(sub.provider_ref, SubscriptionStatus.CANCELED)
    return {"status": "canceled"}
