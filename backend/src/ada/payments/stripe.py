"""Stripe payment seam (global), mirroring paystack.py.

`create_checkout` makes a hosted Checkout Session tagged with the run id;
`verify_and_parse` authenticates the webhook via Stripe's signed payload. Both are
synchronous SDK calls — routes invoke them through run_in_threadpool so the event loop
is never blocked.
"""
import stripe

from ada.config import get_settings
from ada.db.models import Run


def create_checkout(run: Run) -> str:
    """Create a hosted Checkout Session for a pending run; return its URL."""
    s = get_settings()
    stripe.api_key = s.stripe_secret_key
    session = stripe.checkout.Session.create(
        mode="payment",
        client_reference_id=run.id,
        customer_email=run.email,
        metadata={"run_id": run.id},
        line_items=[
            {
                "quantity": 1,
                "price_data": {
                    "currency": "usd",
                    "unit_amount": s.stripe_price_usd_cents,
                    "product_data": {"name": "Ada — CV rewrite + job matches + interview"},
                },
            }
        ],
        success_url=f"{s.frontend_origin}/app/runs/{run.id}?paid=1",
        cancel_url=f"{s.frontend_origin}/app/new?canceled=1",
    )
    if session.url is None:
        raise RuntimeError("Stripe checkout session created without a redirect URL")
    return session.url


def verify_and_parse(payload: bytes, signature: str | None) -> dict:
    """Authenticate + parse a Stripe webhook. Raises on a bad/absent signature."""
    s = get_settings()
    return stripe.Webhook.construct_event(payload, signature or "", s.stripe_webhook_secret)
