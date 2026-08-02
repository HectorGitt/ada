import base64
import hashlib
import hmac

import pytest

from ada.services import kyc


def test_signature_matches_smile_scheme():
    """base64(HMAC-SHA256(api_key, timestamp‖partner_id‖'sid_request'))."""
    ts, partner, key = "2026-07-31T00:00:00+00:00", "1234", "test-api-key"
    expected = base64.b64encode(
        hmac.new(key.encode(), (ts + partner + "sid_request").encode(), hashlib.sha256).digest()
    ).decode()
    assert kyc._signature(ts, partner, key) == expected


def test_interpret_reads_the_authoritative_action():
    verified = kyc._interpret(
        {"Actions": {"Verify_ID_Number": "Verified"}, "ResultText": "ID verified",
         "SmileJobID": "job-1"}
    )
    assert verified.verified is True
    assert verified.provider_ref == "job-1"

    rejected = kyc._interpret(
        {"Actions": {"Verify_ID_Number": "Not Verified"}, "ResultText": "No match"}
    )
    assert rejected.verified is False
    assert rejected.detail == "No match"

    # Absent/garbled Actions is treated as not verified, never as a pass.
    assert kyc._interpret({}).verified is False


async def test_verify_id_falls_back_when_not_configured(monkeypatch):
    # Force "not configured" so the fallback is exercised regardless of the environment.
    monkeypatch.setattr(kyc, "is_configured", lambda: False)
    with pytest.raises(kyc.KycNotConfigured):
        await kyc.verify_id(
            id_type="NIN", id_number="12345678901", first_name="Ada", last_name="Lovelace",
            user_id="u1",
        )


async def test_verify_id_rejects_unsupported_type(monkeypatch):
    # Force "configured" so we exercise the type guard, not the creds guard.
    monkeypatch.setattr(kyc, "is_configured", lambda: True)
    with pytest.raises(kyc.KycError):
        await kyc.verify_id(
            id_type="MADE_UP", id_number="x", first_name="A", last_name="B", user_id="u1",
        )
