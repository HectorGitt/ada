"""Real identity verification via Smile Identity — the KYC half of the credential.

Smile is the natural fit for the African market (NIN/BVN/voter's card/passport lookups).
This does a server-to-server ID Verification (job type 5): confirm the government ID belongs
to the name on the profile. Self-attestation stays as the fallback when KYC isn't configured.

Auth follows Smile's signature scheme: base64(HMAC-SHA256(api_key, timestamp‖partner_id‖
"sid_request")). No creds ⇒ KycNotConfigured, so the caller can fall back cleanly.
"""
import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from ada.config import get_settings
from ada.observability import log

# ID types we accept and forward to Smile (Nigeria-first; extend per country as needed).
SUPPORTED_ID_TYPES = {
    "NIN", "NIN_SLIP", "BVN", "DRIVERS_LICENSE", "VOTER_ID", "PASSPORT", "CAC", "TIN",
}


class KycNotConfigured(RuntimeError):
    """Smile credentials aren't set — the route should fall back to attestation."""


class KycError(RuntimeError):
    """The provider was reachable but the request failed (network/HTTP/parse)."""


@dataclass
class KycResult:
    verified: bool
    detail: str
    provider_ref: str | None = None


def _signature(timestamp: str, partner_id: str, api_key: str) -> str:
    mac = hmac.new(api_key.encode(), digestmod=hashlib.sha256)
    mac.update(timestamp.encode())
    mac.update(partner_id.encode())
    mac.update(b"sid_request")
    return base64.b64encode(mac.digest()).decode()


def is_configured() -> bool:
    s = get_settings()
    return bool(s.smile_partner_id and s.smile_api_key and s.smile_base_url)


async def verify_id(
    *, id_type: str, id_number: str, first_name: str, last_name: str,
    dob: str | None = None, country: str | None = None, user_id: str,
) -> KycResult:
    """Verify a government ID against the candidate's name. Raises KycNotConfigured when
    Smile isn't set up, KycError on transport failure; otherwise returns the verdict."""
    s = get_settings()
    if not is_configured():
        raise KycNotConfigured
    if id_type not in SUPPORTED_ID_TYPES:
        raise KycError(f"Unsupported ID type: {id_type}")

    timestamp = datetime.now(UTC).isoformat()
    body = {
        "partner_id": s.smile_partner_id,
        "signature": _signature(timestamp, s.smile_partner_id, s.smile_api_key),
        "timestamp": timestamp,
        "country": country or s.smile_default_country,
        "id_type": id_type,
        "id_number": id_number,
        "first_name": first_name,
        "last_name": last_name,
        # Ties the job back to us in Smile's dashboard; job_type 5 = ID verification.
        "partner_params": {"user_id": user_id, "job_type": 5},
    }
    if dob:
        body["dob"] = dob

    url = s.smile_base_url.rstrip("/") + "/v1/id_verification"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001 — surface a clean typed error to the route
        log.warning("kyc_request_failed", user_id=user_id, error=str(exc))
        raise KycError("Couldn't reach the identity provider. Try again shortly.") from exc

    return _interpret(data)


def _interpret(data: dict) -> KycResult:
    """Map Smile's response to a verdict. The authoritative field is
    Actions.Verify_ID_Number ('Verified' / 'Not Verified'); ResultText carries the reason."""
    actions = data.get("Actions") or {}
    verified = actions.get("Verify_ID_Number") == "Verified"
    detail = data.get("ResultText") or ("Identity verified." if verified else "Couldn't verify.")
    ref = data.get("SmileJobID") or data.get("job_id")
    return KycResult(verified=verified, detail=detail, provider_ref=ref)
