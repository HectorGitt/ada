"""Env-driven config. No secrets in code.

validate_runtime() raises on boot in staging/prod when a required secret or setting is
missing, so misconfiguration fails the deploy rather than surfacing at request time.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["local", "staging", "prod"] = "local"
    log_level: str = "INFO"
    # Comma-separated allowlist in staging/prod (e.g. "https://ada.africa,https://www.ada.africa").
    allowed_origin: str = "*"

    database_url: str
    # Cloud SQL pool sizing — tuned per instance in prod via env.
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle_seconds: int = 1800

    gcp_project: str = ""
    gcp_location: str = "us-central1"
    # Uploaded CV originals land here (empty = extraction only, nothing stored).
    gcs_bucket: str = ""
    vertex_model: str = "gemini-2.5-flash"
    embedding_model: str = "text-embedding-004"
    live_model: str = "gemini-live-2.5-flash-native-audio"

    # LLM resilience
    llm_timeout_ms: int = 60_000
    llm_max_attempts: int = 3

    # Jooble keys are country-feed-bound: maps feed host -> key.
    jooble_feeds: dict[str, str] = Field(default_factory=dict, repr=False)

    # one-click apply
    apply_max_concurrency: int = 3
    apply_max_in_flight_per_user: int = 5
    apply_stuck_seconds: int = 300

    # matching + interview
    jobs_match_k: int = 5
    interview_questions: int = 5
    # Runs stuck in PAID longer than this had their in-process dispatch lost — recover them.
    stuck_run_seconds: int = 300

    # auth (email + password; email used for password-reset links)
    frontend_origin: str = "http://localhost:3000"
    resend_api_key: str = Field(default="", repr=False)
    email_from: str = "Ada <auth@ada.local>"
    session_cookie: str = "ada_session"

    # paystack (NGN)
    paystack_base_url: str = "https://api.paystack.co"
    paystack_public_key: str = ""
    paystack_secret_key: str = Field(default="", repr=False)
    price_kobo: int = 200000
    currency: str = "NGN"

    # stripe (global)
    stripe_secret_key: str = Field(default="", repr=False)
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = Field(default="", repr=False)
    stripe_price_usd_cents: int = 1500
    stripe_currency: str = "usd"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origin.split(",") if o.strip()]

    def validate_runtime(self) -> None:
        """Raise on boot if a required secret is missing outside local dev."""
        if self.app_env == "local":
            return
        missing: list[str] = []
        if not self.gcp_project:
            missing.append("GCP_PROJECT")
        # At least one payment provider must be fully configured to take money.
        paystack_ok = bool(self.paystack_secret_key and self.paystack_public_key)
        stripe_ok = bool(self.stripe_secret_key and self.stripe_webhook_secret)
        if not (paystack_ok or stripe_ok):
            missing.append("a fully-configured payment provider (Paystack or Stripe)")
        if self.allowed_origin == "*":
            missing.append("ALLOWED_ORIGIN (wildcard CORS is not allowed in prod)")
        if not self.resend_api_key:
            missing.append("RESEND_API_KEY (password-reset email delivery)")
        if self.frontend_origin.startswith("http://localhost"):
            missing.append("FRONTEND_ORIGIN (reset links must point at the real app)")
        if missing:
            raise RuntimeError(
                f"Ada misconfigured for {self.app_env}: missing {', '.join(missing)}"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
