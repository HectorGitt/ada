import pytest

from ada.config import Settings


def test_local_skips_validation():
    Settings(app_env="local", database_url="x").validate_runtime()


def test_prod_requires_project_and_payment_provider():
    s = Settings(
        app_env="prod", database_url="x", gcp_project="",
        allowed_origin="https://ada.example", paystack_secret_key="",
        paystack_public_key="", stripe_secret_key="", stripe_webhook_secret="",
    )
    with pytest.raises(RuntimeError):
        s.validate_runtime()


def test_prod_ok_with_stripe_only():
    Settings(
        app_env="prod", database_url="x", gcp_project="p",
        allowed_origin="https://ada.example",
        stripe_secret_key="sk", stripe_webhook_secret="wh",
        smtp_username="auth@x", smtp_password="pw", frontend_origin="https://ada.example",
    ).validate_runtime()


def test_prod_requires_auth_config():
    s = Settings(
        app_env="prod", database_url="x", gcp_project="p",
        allowed_origin="https://ada.example",
        stripe_secret_key="sk", stripe_webhook_secret="wh",
    )
    with pytest.raises(RuntimeError, match="SMTP_USERNAME"):
        s.validate_runtime()


def test_prod_rejects_wildcard_cors():
    s = Settings(
        app_env="prod", database_url="x", gcp_project="p",
        allowed_origin="*", stripe_secret_key="sk", stripe_webhook_secret="wh",
        smtp_username="auth@x", smtp_password="pw", frontend_origin="https://ada.example",
    )
    with pytest.raises(RuntimeError):
        s.validate_runtime()


def test_cors_origins_parsed():
    s = Settings(database_url="x", allowed_origin="https://a, https://b")
    assert s.cors_origins == ["https://a", "https://b"]
