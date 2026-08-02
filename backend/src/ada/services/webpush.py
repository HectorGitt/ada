"""Web Push — closed-tab browser notifications, no third-party service.

Implements the two specs a push needs, on the `cryptography` we already ship:
  * RFC 8291 — message encryption (ECDH → HKDF → AES-128-GCM, "aes128gcm" content coding)
  * RFC 8292 — VAPID: an ES256 JWT that identifies us to the push service

The alternative, pywebpush, is a heavy transitive dependency for ~80 lines of well-specified
crypto; doing it here keeps the deploy self-contained. Correctness is pinned by a round-trip
decrypt test.
"""
import asyncio
import base64
import ipaddress
import json
import socket
import time
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ada.observability import log

_CURVE = ec.SECP256R1()


def _b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def _public_bytes(key: ec.EllipticCurvePublicKey) -> bytes:
    """Uncompressed X9.62 point (65 bytes) — the wire format for both p256dh and VAPID keys."""
    return key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )


def encrypt(
    payload: bytes,
    *,
    p256dh: str,
    auth: str,
    salt: bytes,
    server_private: ec.EllipticCurvePrivateKey,
) -> bytes:
    """Encrypt `payload` for a subscription per RFC 8291, returning the aes128gcm body
    (header ‖ ciphertext). `salt` (16 bytes) and the server ephemeral key are injected so
    the encryption is deterministic and testable."""
    ua_public = ec.EllipticCurvePublicKey.from_encoded_point(_CURVE, _b64d(p256dh))
    as_public_bytes = _public_bytes(server_private.public_key())
    ua_public_bytes = _public_bytes(ua_public)
    auth_secret = _b64d(auth)

    shared = server_private.exchange(ec.ECDH(), ua_public)
    # RFC 8291 §3.4: mix the two public keys into the key material with the auth secret.
    key_info = b"WebPush: info\x00" + ua_public_bytes + as_public_bytes
    ikm = _hkdf(auth_secret, shared, key_info, 32)

    # RFC 8188 aes128gcm: derive the content key + nonce from the record salt.
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)

    # Single record: append the 0x02 last-record delimiter, then AES-128-GCM (no AAD).
    ciphertext = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)

    record_size = (4096).to_bytes(4, "big")
    header = salt + record_size + len(as_public_bytes).to_bytes(1, "big") + as_public_bytes
    return header + ciphertext


def vapid_auth_header(endpoint: str, *, subject: str, private_key: str, public_key: str) -> str:
    """RFC 8292 Authorization header: a short-lived ES256 JWT bound to the push origin."""
    parts = urlsplit(endpoint)
    origin = f"{parts.scheme}://{parts.netloc}"
    header = _b64e(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    claims = _b64e(
        json.dumps(
            {"aud": origin, "exp": int(time.time()) + 12 * 3600, "sub": subject},
            separators=(",", ":"),
        ).encode()
    )
    signing_input = f"{header}.{claims}".encode()

    priv = ec.derive_private_key(int.from_bytes(_b64d(private_key), "big"), _CURVE)
    der = priv.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    jws_sig = _b64e(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return f"vapid t={header}.{claims}.{jws_sig}, k={public_key}"


async def endpoint_is_public(endpoint: str) -> bool:
    """Resolve the endpoint host and require every resolved address to be public — blocks
    SSRF to loopback, private, link-local (incl. 169.254.169.254 cloud metadata), reserved,
    or multicast ranges. Re-resolved here at dispatch (not just at registration) to shrink
    the DNS-rebinding window."""
    parts = urlsplit(endpoint)
    host = parts.hostname
    if parts.scheme != "https" or not host:
        return False
    try:
        infos = await asyncio.to_thread(
            socket.getaddrinfo, host, parts.port or 443, 0, socket.SOCK_STREAM
        )
    except OSError:
        return False
    if not infos:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            return False
    return True


async def send_web_push(
    *, endpoint: str, p256dh: str, auth: str, payload: dict, settings: object, ttl: int = 2419200
) -> int:
    """Encrypt and POST one push. Returns the HTTP status; 404/410 mean the subscription
    is gone and the caller should drop it. Raises only on transport/crypto errors."""
    import os

    # Defence-in-depth against SSRF: never POST to a non-public destination, even if a
    # bad endpoint slipped past registration validation.
    if not await endpoint_is_public(endpoint):
        log.warning("webpush_blocked_endpoint", host=urlsplit(endpoint).hostname)
        return 400

    salt = os.urandom(16)
    server_private = ec.generate_private_key(_CURVE)
    body = encrypt(
        json.dumps(payload).encode(),
        p256dh=p256dh, auth=auth, salt=salt, server_private=server_private,
    )
    headers = {
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "TTL": str(ttl),
        "Authorization": vapid_auth_header(
            endpoint,
            subject=settings.vapid_subject,  # type: ignore[attr-defined]
            private_key=settings.vapid_private_key,  # type: ignore[attr-defined]
            public_key=settings.vapid_public_key,  # type: ignore[attr-defined]
        ),
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(endpoint, content=body, headers=headers)
    if resp.status_code >= 400 and resp.status_code not in (404, 410):
        log.warning("webpush_send_failed", status=resp.status_code, body=resp.text[:160])
    return resp.status_code
