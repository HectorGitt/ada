"""Tier -> capability resolution. Pure and side-effect free so it stays in the gauntlet.

Entitlements are derived from an active subscription's tier, never trusted from the
client. Free tier keeps the one-off pay-per-run path; paid tiers unlock recurring use.
"""
from dataclasses import dataclass

from ada.db.models import Subscription, SubscriptionStatus

FREE = "free"
PRO = "pro"
PREMIUM = "premium"
TIERS = (FREE, PRO, PREMIUM)

# Grace: a PAST_DUE subscription keeps its entitlements while the provider retries.
_ACTIVE_STATUSES = frozenset({SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE})


@dataclass(frozen=True)
class Entitlement:
    tier: str
    included_runs: bool  # runs covered by the plan (no per-run payment)
    can_apply: bool
    can_voice: bool
    priority: bool

    @property
    def requires_payment_per_run(self) -> bool:
        return not self.included_runs


_MATRIX: dict[str, Entitlement] = {
    FREE: Entitlement(
        FREE, included_runs=False, can_apply=False, can_voice=False, priority=False
    ),
    PRO: Entitlement(
        PRO, included_runs=True, can_apply=True, can_voice=False, priority=False
    ),
    PREMIUM: Entitlement(
        PREMIUM, included_runs=True, can_apply=True, can_voice=True, priority=True
    ),
}


def for_tier(tier: str) -> Entitlement:
    return _MATRIX.get(tier, _MATRIX[FREE])


def resolve(subscription: Subscription | None) -> Entitlement:
    """The effective entitlement for a user, defaulting to free when no active plan."""
    if subscription is None or subscription.status not in _ACTIVE_STATUSES:
        return _MATRIX[FREE]
    return for_tier(subscription.tier)
