from ada.services.subscriptions import is_paystack_subscription, is_stripe_subscription


def test_paystack_subscription_detection():
    assert is_paystack_subscription({"event": "subscription.create", "data": {}})
    assert is_paystack_subscription({"event": "subscription.disable", "data": {}})
    assert is_paystack_subscription(
        {"event": "charge.success", "data": {"plan": {"plan_code": "PLN_x"}}}
    )
    # A plain one-off run charge (no plan) must NOT be treated as a subscription.
    assert not is_paystack_subscription(
        {"event": "charge.success", "data": {"reference": "run-1"}}
    )


def test_stripe_subscription_detection():
    assert is_stripe_subscription({"type": "customer.subscription.updated", "data": {"object": {}}})
    assert is_stripe_subscription({"type": "customer.subscription.deleted", "data": {"object": {}}})
    assert is_stripe_subscription(
        {"type": "checkout.session.completed", "data": {"object": {"mode": "subscription"}}}
    )
    # A one-off run checkout (mode=payment) must NOT be treated as a subscription.
    assert not is_stripe_subscription(
        {"type": "checkout.session.completed", "data": {"object": {"mode": "payment"}}}
    )
