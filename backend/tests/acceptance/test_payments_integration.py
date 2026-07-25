"""Integration tests for the money-path invariants against a real Postgres.

Gated on RUN_DB_TESTS=1 (CI sets it with a pgvector service). They assert the two
guarantees that protect revenue: webhook confirmation is idempotent, and a paid run can
be claimed for execution exactly once.
"""
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_DB_TESTS"), reason="requires a Postgres instance"
)

from ada.db.models import Run, RunStatus  # noqa: E402
from ada.db.repositories import PaymentRepository, RunRepository  # noqa: E402
from ada.db.session import _session_factory, init_db  # noqa: E402


async def _make_pending_run() -> str:
    run_id = uuid.uuid4().hex
    async with _session_factory() as s:
        run = Run(
            id=run_id, reference=run_id, provider="paystack", amount=200000,
            currency="NGN", email="a@b.c", target_role="Engineer", cv_text="x" * 40,
        )
        await RunRepository(s).create(run)
    return run_id


async def test_confirm_is_idempotent():
    await init_db()
    run_id = await _make_pending_run()
    async with _session_factory() as s:
        first = await PaymentRepository(s).confirm(
            provider="paystack", event_ref=run_id, run_id=run_id
        )
    async with _session_factory() as s:
        second = await PaymentRepository(s).confirm(
            provider="paystack", event_ref=run_id, run_id=run_id
        )
    assert first == "claimed"
    assert second == "duplicate"
    async with _session_factory() as s:
        assert (await RunRepository(s).get(run_id)).status == RunStatus.PAID


async def test_claim_for_execution_runs_once():
    await init_db()
    run_id = await _make_pending_run()
    async with _session_factory() as s:
        await PaymentRepository(s).confirm(
            provider="paystack", event_ref=run_id, run_id=run_id
        )
    async with _session_factory() as s:
        assert await RunRepository(s).claim_for_execution(run_id) is not None
    async with _session_factory() as s:
        assert await RunRepository(s).claim_for_execution(run_id) is None
