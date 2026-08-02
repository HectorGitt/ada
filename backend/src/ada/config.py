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
    # Kill-switch for end-to-end testing: when false, POST /runs skips checkout
    # entirely and every run is marked PAID and dispatched immediately (the
    # same path a subscriber's included run takes). Webhooks stay mounted but
    # become no-ops for these runs. Set PAYMENTS_ENABLED=true before launch.
    payments_enabled: bool = True
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
    # Google AI Studio (Gemini Developer API) key. When set, every Gemini call uses it
    # instead of Vertex — lets the full AI stack run without GCP creds (local/demo).
    gemini_api_key: str = Field(default="", repr=False)
    # Uploaded CV originals land here (empty = extraction only, nothing stored).
    gcs_bucket: str = ""
    vertex_model: str = "gemini-2.5-flash"
    embedding_model: str = "text-embedding-004"
    # AI Studio embedding model (used when gemini_api_key is set); reduced to EMBED_DIM.
    gemini_embedding_model: str = "gemini-embedding-001"
    live_model: str = "gemini-live-2.5-flash-native-audio"
    # Ada's single voice everywhere (live sessions + the landing intro asset).
    live_voice: str = "Aoede"

    # LLM resilience
    llm_timeout_ms: int = 60_000
    llm_max_attempts: int = 3

    # Jooble keys are country-feed-bound: maps feed host -> key.
    jooble_feeds: dict[str, str] = Field(default_factory=dict, repr=False)

    # one-click apply
    apply_max_concurrency: int = 3
    apply_max_in_flight_per_user: int = 5
    apply_stuck_seconds: int = 300

    # proactive digest (Ada's "fresh leads" outreach, scheduled)
    digest_matches: int = 4
    digest_cooldown_seconds: int = 6 * 24 * 3600  # ~weekly; re-runs inside this are no-ops

    # free CV assessment (public top-of-funnel) — per-IP rate limit
    assess_rate_limit: int = 5
    assess_rate_window_seconds: int = 3600

    # verification credential — proctored assessment
    verify_pass_mark: int = 60
    verify_time_limit_seconds: int = 1800        # server-authoritative; over = can't certify
    verify_max_attempts: int = 3                 # per skill within the window below
    verify_attempt_window_seconds: int = 86_400  # rolling 24h attempt cap
    verify_retake_cooldown_seconds: int = 1800   # min gap between finished attempts
    # Voice+camera sessions: face out of frame beyond this (seconds) flags for review.
    verify_face_absent_limit_seconds: int = 25

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
    # Sliding session window: a session (and its cookie) lasts this long, refreshed on
    # activity — so an active user stays in, but an idle one is signed out after this many
    # idle days. Not a fixed-forever cookie.
    session_ttl_days: int = 14

    # Admin dashboard — comma-separated emails granted admin. Set via env/secrets only;
    # admin is never assignable from inside the app. Empty ⇒ no admins.
    admin_emails: str = ""

    # WhatsApp notifications via Twilio (best-effort; unset = channel skipped, logged).
    twilio_account_sid: str = Field(default="", repr=False)
    twilio_auth_token: str = Field(default="", repr=False)
    twilio_whatsapp_from: str = ""  # e.g. "whatsapp:+14155238886" (Twilio sandbox)
    # Reject inbound WhatsApp webhooks whose Twilio signature doesn't verify. On by
    # default; only turn off for local testing without a signature.
    twilio_validate_signature: bool = True

    # Web Push (VAPID). Generate a P-256 keypair once (scripts/gen_vapid.py); public key
    # is base64url of the uncompressed point, private key base64url of the 32-byte scalar.
    # Unset = push channel skipped (no subscriptions can be created), logged.
    vapid_public_key: str = ""
    vapid_private_key: str = Field(default="", repr=False)
    vapid_subject: str = "mailto:ops@ada.dev"  # RFC 8292 contact for the push service

    # Smile Identity KYC (real ID verification). Unset ⇒ identity falls back to
    # self-attestation. Sandbox base URL: https://testapi.smileidentity.com
    smile_partner_id: str = ""
    smile_api_key: str = Field(default="", repr=False)
    smile_base_url: str = ""  # e.g. https://api.smileidentity.com (prod) / testapi... (sandbox)
    smile_default_country: str = "NG"

    frontend_base_url: str = "http://localhost:3000"  # for links inside notifications

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
    stripe_price_usd_cents: int = 999
    stripe_currency: str = "usd"

    # subscription plan codes (created in the Paystack/Stripe dashboards), keyed
    # "<tier>_<cadence>" e.g. PAYSTACK_PLANS='{"pro_monthly":"PLN_x","premium_annual":"PLN_y"}'
    paystack_plans: dict[str, str] = Field(default_factory=dict)
    stripe_prices: dict[str, str] = Field(default_factory=dict)

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origin.split(",") if o.strip()]

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    def validate_runtime(self) -> None:
        """Raise on boot if a required secret is missing outside local dev."""
        if self.app_env == "local":
            return
        missing: list[str] = []
        if not self.gcp_project:
            missing.append("GCP_PROJECT")
        # At least one payment provider must be fully configured to take money —
        # unless payments are switched off for end-to-end testing.
        if self.payments_enabled:
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
