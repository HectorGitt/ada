from types import SimpleNamespace

from ada.api.routes.webhooks import _amount_ok


def _run(amount: int, currency: str):
    return SimpleNamespace(amount=amount, currency=currency)


def test_exact_amount_accepted():
    assert _amount_ok(paid=200000, currency="NGN", run=_run(200000, "NGN"))


def test_overpayment_accepted():
    assert _amount_ok(paid=250000, currency="NGN", run=_run(200000, "NGN"))


def test_underpayment_rejected():
    assert not _amount_ok(paid=199999, currency="NGN", run=_run(200000, "NGN"))


def test_currency_mismatch_rejected():
    assert not _amount_ok(paid=200000, currency="USD", run=_run(200000, "NGN"))


def test_currency_case_insensitive():
    assert _amount_ok(paid=1500, currency="USD", run=_run(1500, "usd"))
