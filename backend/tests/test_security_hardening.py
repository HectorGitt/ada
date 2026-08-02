"""Unit coverage for the security-audit hardening: notification-email escaping and the
bcrypt byte-limit password guard."""
import pytest

from ada.api.routes.auth import _bcrypt_safe
from ada.services.notify import _email_html, _safe_href


def test_email_html_escapes_dynamic_text_and_drops_unsafe_links():
    out = _email_html("<script>alert(1)</script>", "<b>hi & bye</b>", "javascript:alert(1)")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "javascript:" not in out  # unsafe scheme dropped, so no href at all


def test_safe_href_allows_only_http_and_relative():
    assert _safe_href("/app/intros") == "/app/intros"
    assert _safe_href("https://ada.africa/x") == "https://ada.africa/x"
    assert _safe_href("http://localhost:3000/x") == "http://localhost:3000/x"
    assert _safe_href("javascript:alert(1)") is None
    assert _safe_href("data:text/html,<script>") is None
    assert _safe_href(None) is None


def test_password_rejects_over_72_utf8_bytes():
    assert _bcrypt_safe("a" * 72) == "a" * 72          # exactly at the limit is fine
    with pytest.raises(ValueError):
        _bcrypt_safe("a" * 73)                          # one over
    with pytest.raises(ValueError):
        _bcrypt_safe("😀" * 20)                          # 80 bytes of multibyte


def test_origin_allowed_enforces_allowlist_but_permits_native(monkeypatch):
    from ada import security

    class _Prod:
        cors_origins = ["https://ada.africa"]
        frontend_origin = "https://app.ada.africa"

    monkeypatch.setattr(security, "get_settings", lambda: _Prod())
    assert security.origin_allowed(None) is True             # native / no Origin
    assert security.origin_allowed("null") is True            # opaque origin
    assert security.origin_allowed("https://ada.africa") is True
    assert security.origin_allowed("https://app.ada.africa/") is True  # trailing slash ok
    assert security.origin_allowed("https://evil.example") is False

    class _Dev:
        cors_origins = ["*"]
        frontend_origin = "http://localhost:3000"

    monkeypatch.setattr(security, "get_settings", lambda: _Dev())
    assert security.origin_allowed("https://anything.example") is True  # wildcard dev
