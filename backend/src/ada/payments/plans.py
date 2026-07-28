"""Subscription plan catalog: the tiers, prices, and what each includes.

Display prices live here (proposals — adjust freely); the actual recurring charge is
governed by the provider Plan/Price whose code is resolved from settings per
(tier, cadence, provider). Free is not a billable plan.
"""
from dataclasses import dataclass

from ada.config import get_settings
from ada.services.entitlements import PREMIUM, PRO

CADENCES = ("monthly", "annual")


@dataclass(frozen=True)
class Price:
    ngn_kobo: int
    usd_cents: int


@dataclass(frozen=True)
class Plan:
    tier: str
    name: str
    tagline: str
    features: tuple[str, ...]
    monthly: Price
    annual: Price  # per-year total (≈ 2 months free vs monthly×12)


CATALOG: dict[str, Plan] = {
    PRO: Plan(
        tier=PRO,
        name="Pro",
        tagline="Everything Ada does, unlimited.",
        features=(
            "Unlimited CV rewrites, job matches & scored mock interviews",
            "One-click apply — Ada submits the employer's form for you",
            "Ask Ada, grounded in your profile and runs",
        ),
        monthly=Price(ngn_kobo=500_000, usd_cents=1_900),
        annual=Price(ngn_kobo=5_000_000, usd_cents=19_000),
    ),
    PREMIUM: Plan(
        tier=PREMIUM,
        name="Premium",
        tagline="Your career, with Ada on call.",
        features=(
            "Everything in Pro",
            "Live voice conversations & spoken mock interviews",
            "Priority processing and a weekly best-fit job digest",
        ),
        monthly=Price(ngn_kobo=1_200_000, usd_cents=3_900),
        annual=Price(ngn_kobo=12_000_000, usd_cents=39_000),
    ),
}


def provider_code(provider: str, tier: str, cadence: str) -> str | None:
    key = f"{tier}_{cadence}"
    s = get_settings()
    table = s.paystack_plans if provider == "paystack" else s.stripe_prices
    return table.get(key)


def resolve_plan(provider: str, code: str) -> tuple[str, str] | None:
    """Inverse of provider_code: a provider plan/price code -> (tier, cadence)."""
    s = get_settings()
    table = s.paystack_plans if provider == "paystack" else s.stripe_prices
    for key, value in table.items():
        if value == code and "_" in key:
            tier, cadence = key.rsplit("_", 1)
            return tier, cadence
    return None
