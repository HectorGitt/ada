"""Recovery sweep entrypoint — re-dispatch runs stuck in PAID (lost dispatch).

Wire to Cloud Scheduler (e.g. every minute):  `python -m ada.recover`.
Idempotent and concurrency-safe via the atomic PAID -> RUNNING claim.
"""
import asyncio

from ada.observability import configure_logging, log
from ada.services.apply import recover_stuck_applications
from ada.services.runs import recover_stuck_runs


async def _sweep() -> tuple[int, int]:
    return await recover_stuck_runs(), await recover_stuck_applications()


def main() -> None:
    configure_logging()
    runs, applications = asyncio.run(_sweep())
    log.info("recover_sweep", redispatched_runs=runs, recovered_applications=applications)
    print(f"redispatched {runs} stuck runs; recovered {applications} stuck applications")


if __name__ == "__main__":
    main()
