from types import SimpleNamespace

from ada.db.models import SubscriptionStatus
from ada.payments import plans
from ada.services import entitlements as ent


def _sub(tier: str, status: SubscriptionStatus):
    return SimpleNamespace(tier=tier, status=status)


def test_free_when_no_subscription():
    e = ent.resolve(None)
    assert e.tier == "free"
    assert not e.included_runs and not e.can_apply and not e.can_voice
    assert e.requires_payment_per_run


def test_pro_unlocks_runs_and_apply_but_not_voice():
    e = ent.resolve(_sub("pro", SubscriptionStatus.ACTIVE))
    assert e.included_runs and e.can_apply
    assert not e.can_voice
    assert not e.requires_payment_per_run


def test_premium_unlocks_everything():
    e = ent.resolve(_sub("premium", SubscriptionStatus.ACTIVE))
    assert e.included_runs and e.can_apply and e.can_voice and e.priority


def test_past_due_keeps_access_canceled_reverts_to_free():
    assert ent.resolve(_sub("pro", SubscriptionStatus.PAST_DUE)).can_apply
    assert ent.resolve(_sub("pro", SubscriptionStatus.CANCELED)).tier == "free"


def test_unknown_tier_falls_back_to_free():
    assert ent.for_tier("enterprise").tier == "free"


def test_catalog_has_pro_and_premium_with_both_cadences():
    assert set(plans.CATALOG) == {"pro", "premium"}
    for plan in plans.CATALOG.values():
        assert plan.monthly.ngn_kobo > 0 and plan.annual.usd_cents > 0
        assert plan.annual.usd_cents < plan.monthly.usd_cents * 12  # annual discount


def test_plan_code_resolution_roundtrips(monkeypatch):
    from ada.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("PAYSTACK_PLANS", '{"pro_monthly": "PLN_abc", "premium_annual": "PLN_xyz"}')
    try:
        assert plans.provider_code("paystack", "pro", "monthly") == "PLN_abc"
        assert plans.resolve_plan("paystack", "PLN_xyz") == ("premium", "annual")
        assert plans.resolve_plan("paystack", "PLN_missing") is None
    finally:
        get_settings.cache_clear()
