"""Bounded async retry with exponential backoff + jitter.

Used to wrap Vertex/Gemini calls so a transient 429/5xx or a dropped connection
doesn't fail a paid run. Non-transient errors (bad request, auth) are raised
immediately — retrying them just wastes the user's time and our quota.
"""
import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

_jitter = random.SystemRandom()

T = TypeVar("T")

_TRANSIENT_CODES = {429, 500, 502, 503, 504}


def _is_transient(exc: BaseException) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int) and code in _TRANSIENT_CODES:
        return True
    # Network-level failures raised by the async transport are worth a retry.
    return isinstance(exc, (asyncio.TimeoutError, ConnectionError))


async def retry_async(
    fn: Callable[[], Awaitable[T]], *, attempts: int = 3, base_delay: float = 0.5
) -> T:
    last: BaseException | None = None
    for i in range(attempts):
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001 — classify, then re-raise or retry
            last = exc
            if i == attempts - 1 or not _is_transient(exc):
                raise
            await asyncio.sleep(base_delay * (2**i) + _jitter.random() * 0.1)
    if last is None:
        raise RuntimeError("retry loop exited without an exception")
    raise last
