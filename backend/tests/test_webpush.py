"""Web Push crypto correctness.

`encrypt()` is verified by an independent decrypt written straight from RFC 8291 — the
AES-GCM auth tag makes this a real check: a wrong CEK or nonce fails to authenticate. The
VAPID header is checked for shape and a verifiable ES256 signature.
"""
import base64
import json

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ada.services import webpush

_CURVE = ec.SECP256R1()


def _point(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _decrypt(body: bytes, ua_private: ec.EllipticCurvePrivateKey, auth_secret: bytes) -> bytes:
    """Independent RFC 8291 receiver: recover the plaintext from an aes128gcm body."""
    salt, body = body[:16], body[16:]
    _rs, body = body[:4], body[4:]
    idlen, body = body[0], body[1:]
    as_public_bytes, ciphertext = body[:idlen], body[idlen:]

    as_public = ec.EllipticCurvePublicKey.from_encoded_point(_CURVE, as_public_bytes)
    ua_public_bytes = _point(ua_private.public_key())
    shared = ua_private.exchange(ec.ECDH(), as_public)

    def hkdf(s: bytes, ikm: bytes, info: bytes, n: int) -> bytes:
        return HKDF(algorithm=hashes.SHA256(), length=n, salt=s, info=info).derive(ikm)

    ikm = hkdf(auth_secret, shared, b"WebPush: info\x00" + ua_public_bytes + as_public_bytes, 32)
    cek = hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    plain = AESGCM(cek).decrypt(nonce, ciphertext, None)
    return plain.rstrip(b"\x02")  # strip the last-record delimiter


def test_encrypt_roundtrips_through_independent_decrypt():
    # A receiver (the browser) and its auth secret.
    ua_private = ec.generate_private_key(_CURVE)
    ua_public_bytes = _point(ua_private.public_key())
    auth_secret = b"0123456789abcdef"
    p256dh = _b64e(ua_public_bytes)
    auth = _b64e(auth_secret)

    message = {"title": "Ada", "body": "An employer wants to connect"}
    salt = b"S" * 16
    server_private = ec.generate_private_key(_CURVE)
    body = webpush.encrypt(
        json.dumps(message).encode(),
        p256dh=p256dh, auth=auth, salt=salt, server_private=server_private,
    )
    recovered = _decrypt(body, ua_private, auth_secret)
    assert json.loads(recovered) == message


def test_vapid_header_has_verifiable_es256_signature():
    priv = ec.generate_private_key(_CURVE)
    private_b64 = _b64e(priv.private_numbers().private_value.to_bytes(32, "big"))
    public_b64 = _b64e(_point(priv.public_key()))
    header = webpush.vapid_auth_header(
        "https://fcm.googleapis.com/fcm/send/abc123",
        subject="mailto:ops@ada.dev", private_key=private_b64, public_key=public_b64,
    )
    assert header.startswith("vapid t=")
    token = header[len("vapid t="):].split(", k=")[0]
    h, claims, sig = token.split(".")

    # Claims target the push origin, not the full endpoint.
    payload = json.loads(base64.urlsafe_b64decode(claims + "=" * (-len(claims) % 4)))
    assert payload["aud"] == "https://fcm.googleapis.com"
    assert payload["sub"] == "mailto:ops@ada.dev"

    # The signature verifies against the advertised public key.
    raw = base64.urlsafe_b64decode(sig + "=" * (-len(sig) % 4))
    r = int.from_bytes(raw[:32], "big")
    s = int.from_bytes(raw[32:], "big")
    priv.public_key().verify(
        encode_dss_signature(r, s), f"{h}.{claims}".encode(), ec.ECDSA(hashes.SHA256())
    )
