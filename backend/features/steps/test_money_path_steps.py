"""HUMAN-OWNED. Step definitions binding the money-path spec to the repositories."""
import asyncio
import os
import uuid
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_DB_TESTS"), reason="requires Postgres"
)

scenarios("../money_path.feature")


@pytest.fixture(scope="module")
def loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture()
def ctx() -> dict[str, Any]:
    return {}


def _new_run(status: str) -> Any:
    from ada.db.models import Run, RunStatus

    return Run(
        id=uuid.uuid4().hex,
        reference=f"bdd-{uuid.uuid4().hex}",
        email="bdd@example.com",
        target_role="QA Engineer",
        cv_text="cv",
        status=RunStatus(status),
    )


async def _create_run(status: str) -> Any:
    from ada.db.repositories import RunRepository
    from ada.db.session import _session_factory, init_db

    await init_db()
    async with _session_factory() as s:
        return await RunRepository(s).create(_new_run(status))


async def _confirm(run: Any) -> str:
    from ada.db.repositories import PaymentRepository
    from ada.db.session import _session_factory

    async with _session_factory() as s:
        return await PaymentRepository(s).confirm(
            provider="paystack", event_ref=run.reference, run_id=run.id
        )


async def _claim(run_id: str) -> Any:
    from ada.db.repositories import RunRepository
    from ada.db.session import _session_factory

    async with _session_factory() as s:
        return await RunRepository(s).claim_for_execution(run_id)


async def _status(run_id: str) -> str:
    from ada.db.repositories import RunRepository
    from ada.db.session import _session_factory

    async with _session_factory() as s:
        run = await RunRepository(s).get(run_id)
        assert run is not None
        return str(run.status)


@given("a pending run awaiting payment")
def pending_run(loop, ctx):
    ctx["run"] = loop.run_until_complete(_create_run("pending_payment"))


@given("a paid run")
def paid_run(loop, ctx):
    ctx["run"] = loop.run_until_complete(_create_run("paid"))


@when("the payment event is confirmed")
def confirm_event(loop, ctx):
    ctx["first"] = loop.run_until_complete(_confirm(ctx["run"]))


@when("the same payment event is delivered again")
def replay_event(loop, ctx):
    ctx["second"] = loop.run_until_complete(_confirm(ctx["run"]))


@when("a worker tries to claim the run for execution")
def claim_once(loop, ctx):
    ctx["claim"] = loop.run_until_complete(_claim(ctx["run"].id))


@when("two workers race to claim the run")
def claim_race(loop, ctx):
    async def race() -> list[Any]:
        return list(await asyncio.gather(_claim(ctx["run"].id), _claim(ctx["run"].id)))

    ctx["claims"] = loop.run_until_complete(race())


@then("the run is paid")
def run_is_paid(loop, ctx):
    assert ctx["first"] == "claimed"
    assert loop.run_until_complete(_status(ctx["run"].id)) == "paid"


@then("the second delivery is recognized as a duplicate")
def second_is_duplicate(ctx):
    assert ctx["second"] == "duplicate"


@then("the claim is refused")
def claim_refused(ctx):
    assert ctx["claim"] is None


@then("exactly one claim succeeds")
def one_claim_wins(ctx):
    winners = [c for c in ctx["claims"] if c is not None]
    assert len(winners) == 1
