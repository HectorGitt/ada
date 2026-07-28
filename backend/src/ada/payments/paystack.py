"""Paystack webhook verification + server-side transaction verification.

A valid signature proves Paystack sent the event; it does NOT prove the amount is
right or that the charge truly succeeded (webhooks can be replayed, and payloads
shouldn't be trusted blindly for money). So the webhook also calls Paystack's
transaction/verify endpoint and checks status, amount, and currency before a run is
allowed to execute.
"""
import hashlib
import hmac
from dataclasses import dataclass

import httpx

from ada.config import get_settings


def verify_signature(payload: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    secret = get_settings().paystack_secret_key.encode()
    expected = hmac.new(secret, payload, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)


@dataclass(frozen=True)
class Verification:
    ok: bool
    amount: int          # kobo
    currency: str
    reason: str = ""


async def verify_transaction(reference: str) -> Verification:
    """Authoritatively confirm a charge with Paystack's API (not the webhook body)."""
    s = get_settings()
    url = f"{s.paystack_base_url}/transaction/verify/{reference}"
    headers = {"Authorization": f"Bearer {s.paystack_secret_key}"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code != 200:
        return Verification(False, 0, "", f"verify http {resp.status_code}")
    data = resp.json().get("data") or {}
    ok = data.get("status") == "success"
    return Verification(
        ok=ok,
        amount=int(data.get("amount") or 0),
        currency=str(data.get("currency") or ""),
        reason="" if ok else f"status={data.get('status')}",
    )


async def disable_subscription(sub_code: str) -> None:
    """Stop a subscription's renewal (Paystack needs the fetched email_token to disable)."""
    s = get_settings()
    headers = {"Authorization": f"Bearer {s.paystack_secret_key}"}
    async with httpx.AsyncClient(timeout=15) as client:
        fetched = await client.get(
            f"{s.paystack_base_url}/subscription/{sub_code}", headers=headers
        )
        token = (fetched.json().get("data") or {}).get("email_token")
        if not token:
            raise RuntimeError("paystack subscription has no email_token to disable")
        resp = await client.post(
            f"{s.paystack_base_url}/subscription/disable",
            json={"code": sub_code, "token": token}, headers=headers,
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"paystack disable failed: {resp.status_code} {resp.text[:200]}")


async def subscription_checkout(*, email: str, plan_code: str, reference: str) -> str:
    """Initialize a subscription transaction; Paystack creates the subscription on the
    first successful charge. Returns the hosted authorization URL to redirect to."""
    s = get_settings()
    url = f"{s.paystack_base_url}/transaction/initialize"
    headers = {"Authorization": f"Bearer {s.paystack_secret_key}"}
    payload = {"email": email, "plan": plan_code, "reference": reference,
               "callback_url": f"{s.frontend_origin}/app/billing?status=success"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=headers)
    if resp.status_code >= 400:
        raise RuntimeError(f"paystack init failed: {resp.status_code} {resp.text[:200]}")
    auth_url = ((resp.json().get("data") or {}).get("authorization_url"))
    if not auth_url:
        raise RuntimeError("paystack init returned no authorization_url")
    return str(auth_url)
