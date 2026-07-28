"""Payment webhooks — the only paths that can trigger an agent run.

Each request is: authenticate the sender (HMAC / Stripe signature) -> confirm the charge
out of band (Paystack verify API / Stripe event fields) -> reject wrong amount or
currency -> claim the event and mark the run PAID in one transaction -> dispatch. A
duplicate or replayed webhook resolves to a no-op.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from ada.db.models import Run
from ada.db.repositories import PaymentRepository, RunRepository
from ada.db.session import get_session
from ada.observability import emit_run_log, log
from ada.payments.paystack import verify_signature, verify_transaction
from ada.payments.stripe import verify_and_parse
from ada.services.runs import execute_run
from ada.services.subscriptions import (
    handle_paystack,
    handle_stripe,
    is_paystack_subscription,
    is_stripe_subscription,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _dispatch(
    *, provider: str, event_ref: str, run: Run,
    session: AsyncSession, background: BackgroundTasks,
) -> dict[str, str]:
    """Confirm the event once, then enqueue execution for a newly-paid run."""
    outcome = await PaymentRepository(session).confirm(
        provider=provider, event_ref=event_ref, run_id=run.id
    )
    if outcome == "claimed":
        background.add_task(execute_run, run.id)
        emit_run_log(run_id=run.id, step="webhook", status="accepted", provider=provider)
    else:
        emit_run_log(run_id=run.id, step="webhook", status=outcome, provider=provider)
    return {"status": "accepted" if outcome == "claimed" else outcome}


def _amount_ok(*, paid: int, currency: str, run: Run) -> bool:
    return paid >= run.amount and currency.upper() == run.currency.upper()


@router.post("/paystack")
async def paystack(
    request: Request,
    background: BackgroundTasks,
    x_paystack_signature: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    body = await request.body()
    if not verify_signature(body, x_paystack_signature):
        raise HTTPException(status_code=401, detail="bad signature")

    event = await request.json()
    if is_paystack_subscription(event):
        return await handle_paystack(session, event)
    if event.get("event") != "charge.success":
        return {"status": "ignored"}

    reference = event["data"]["reference"]  # equals the run id for paystack
    run = await RunRepository(session).get(reference)
    if run is None:
        return {"status": "no_run"}

    # Confirm the charge against Paystack directly; the webhook body is not authoritative.
    verification = await verify_transaction(reference)
    if not verification.ok or not _amount_ok(
        paid=verification.amount, currency=verification.currency, run=run
    ):
        log.warning(
            "paystack_rejected", run_id=run.id, reason=verification.reason,
            paid=verification.amount, currency=verification.currency,
            expected=run.amount, expected_currency=run.currency,
        )
        return {"status": "rejected"}

    return await _dispatch(
        provider="paystack", event_ref=reference, run=run,
        session=session, background=background,
    )


@router.post("/stripe")
async def stripe(
    request: Request,
    background: BackgroundTasks,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    body = await request.body()
    try:
        event = await run_in_threadpool(verify_and_parse, body, stripe_signature)
    except Exception as exc:  # noqa: BLE001 — any verification failure is a 400
        raise HTTPException(status_code=400, detail="bad signature") from exc

    if is_stripe_subscription(event):
        return await handle_stripe(session, event)
    if event["type"] != "checkout.session.completed":
        return {"status": "ignored"}

    obj = event["data"]["object"]
    run_id = (obj.get("metadata") or {}).get("run_id") or obj.get("client_reference_id")
    if not run_id:
        return {"status": "no_run"}
    run = await RunRepository(session).get(run_id)
    if run is None:
        return {"status": "no_run"}

    paid = obj.get("payment_status") == "paid"
    if not paid or not _amount_ok(
        paid=int(obj.get("amount_total") or 0), currency=str(obj.get("currency") or ""), run=run
    ):
        log.warning(
            "stripe_rejected", run_id=run.id, payment_status=obj.get("payment_status"),
            paid=obj.get("amount_total"), currency=obj.get("currency"),
            expected=run.amount, expected_currency=run.currency,
        )
        return {"status": "rejected"}

    # Key idempotency on the Stripe event id to tolerate replays.
    return await _dispatch(
        provider="stripe", event_ref=event["id"], run=run,
        session=session, background=background,
    )
