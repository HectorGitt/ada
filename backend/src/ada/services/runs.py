"""Run orchestration, invoked only after a payment is confirmed.

execute_run claims a PAID run atomically before doing work, drives the agent graph
(cv -> match -> interview), and stores the result. recover_stuck_runs re-dispatches runs
whose in-process enqueue was lost (e.g. process crash).
"""
import uuid

from ada.db.models import Run, RunStatus
from ada.db.repositories import RunRepository
from ada.db.session import _session_factory
from ada.observability import emit_run_log, log
from ada.services.graph import build_graph


async def execute_run(run_id: str) -> None:
    """Background task: atomically claim the paid run, run the agent graph, store output."""
    async with _session_factory() as session:
        runs = RunRepository(session)
        run = await runs.claim_for_execution(run_id)
        if run is None:
            # Not in PAID state: already claimed by another worker, or not yet paid.
            return
        emit_run_log(run_id=run_id, step="run", status="start")
        try:
            # Each node reports itself; the row is the single source of truth the
            # status endpoint (and so the UI timeline) reads from.
            async def on_stage(stage: str) -> None:
                await runs.set_stage(run_id, stage)

            graph = build_graph(session, run_id=run_id, on_stage=on_stage)
            final = await graph.ainvoke(
                {
                    "run_id": run_id,
                    "email": run.email,
                    "target_role": run.target_role,
                    "cv_text": run.cv_text,
                }
            )
            await runs.set_deliverables(
                run,
                rewritten_cv=final["rewritten_cv"],
                matches=final["matches"],
                questions=final["questions"],
            )
            emit_run_log(run_id=run_id, step="run", status="ok")
            if run.user_id:
                from ada.services.notify import notify

                await notify(
                    run.user_id, kind="run_complete",
                    title="Your run is ready",
                    body=f"Ada finished your run for {run.target_role} — CV, matches, "
                         "and interview questions are in.",
                    link=f"/app/runs/{run_id}",
                )
        except Exception as exc:  # noqa: BLE001
            await runs.set_status(run, RunStatus.FAILED)
            emit_run_log(run_id=run_id, step="run", status="error", error=repr(exc))


async def recover_stuck_runs() -> int:
    """Re-dispatch runs left in PAID past the dispatch window.

    Idempotent and concurrency-safe: execute_run re-claims atomically, so a run already
    picked up elsewhere is skipped. Intended to run on a schedule (e.g. Cloud Scheduler).
    """
    from ada.config import get_settings

    async with _session_factory() as session:
        stuck = await RunRepository(session).find_stuck(get_settings().stuck_run_seconds)
    for run_id in stuck:
        log.info("recover_stuck_run", run_id=run_id)
        await execute_run(run_id)
    return len(stuck)


async def create_pending_run(
    *, session_runs: RunRepository, provider: str, amount: int, currency: str,
    email: str, target_role: str, cv_text: str, transcript: str | None = None,
    user_id: str | None = None, access_token_hash: str | None = None,
) -> Run:
    reference = uuid.uuid4().hex
    run = Run(
        id=reference, reference=reference, provider=provider, amount=amount,
        currency=currency, email=email, target_role=target_role, cv_text=cv_text,
        transcript=transcript, user_id=user_id, access_token_hash=access_token_hash,
    )
    return await session_runs.create(run)
