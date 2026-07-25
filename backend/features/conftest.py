"""HUMAN-OWNED. Environment for the BDD suite, set before any ada import."""
import os

os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/ada")
os.environ.setdefault("PAYSTACK_SECRET_KEY", "sk_test_secret")
os.environ.setdefault("PAYSTACK_PUBLIC_KEY", "pk_test_public")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_stripe")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test")
os.environ.setdefault("GCP_PROJECT", "test-project")
