"""Ingestion pipeline: fetch -> normalize -> upsert -> embed backfill."""
import asyncio
from typing import Any

import httpx

from ada.config import get_settings
from ada.db.repositories import JobRepository
from ada.db.session import _session_factory
from ada.ingest import ashby, boards, greenhouse, jooble, lever
from ada.observability import log

_EMBED_BATCH = 32
# text-embedding-004 rejects requests over 20k tokens total; pack batches to a
# conservative estimate (~3 chars/token) so no single request can exceed it.
_EMBED_TOKEN_BUDGET = 15_000
_EMBED_MAX_FAILURES = 3
_HTTP_TIMEOUT = 30.0
_JOOBLE_CONCURRENCY = 4


async def _gather_listings(limit: int | None) -> list[dict[str, Any]]:
    s = get_settings()
    listings: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=True) as client:
        tasks: list[tuple[str, Any]] = []
        for slug, company in boards.GREENHOUSE_BOARDS.items():
            tasks.append((f"greenhouse/{slug}", greenhouse.fetch(client, slug, company)))
        for slug, company in boards.LEVER_COMPANIES.items():
            tasks.append((f"lever/{slug}", lever.fetch(client, slug, company)))
        for slug, company in boards.ASHBY_BOARDS.items():
            tasks.append((f"ashby/{slug}", ashby.fetch(client, slug, company)))
        if s.jooble_feeds:
            semaphore = asyncio.Semaphore(_JOOBLE_CONCURRENCY)

            async def _throttled(host: str, key: str, keywords: str, location: str) -> list:
                async with semaphore:
                    return await jooble.fetch(client, host, key, keywords, location)

            for host, key in s.jooble_feeds.items():
                for keywords, location in boards.JOOBLE_QUERIES.get(host, []):
                    coro = _throttled(host, key, keywords, location)
                    tasks.append((f"jooble:{host}/{keywords}", coro))
        else:
            log.info("jooble_skipped", reason="JOOBLE_FEEDS not set")

        results = await asyncio.gather(*(t[1] for t in tasks), return_exceptions=True)
        for (name, _), result in zip(tasks, results, strict=True):
            if isinstance(result, BaseException):
                log.warning("ingest_source_failed", source=name, error=str(result))
                continue
            log.info("ingest_source_ok", source=name, listings=len(result))
            if limit is not None:
                result = result[: max(0, limit - len(listings))]
            listings.extend(result)
            if limit is not None and len(listings) >= limit:
                break
    return listings


async def _backfill_embeddings(repo: JobRepository) -> int:
    from ada.services.search import SearchService

    pending = await repo.unembedded()
    if not pending:
        return 0
    service = SearchService()
    embedded = 0
    failures = 0
    batch: list[tuple[Any, str]] = []
    budget = 0

    async def _flush() -> None:
        nonlocal embedded, failures, batch, budget
        if not batch:
            return
        try:
            vectors = await service.embed_many([text for _, text in batch])
            await repo.set_embeddings(
                [(job.id, vector) for (job, _), vector in zip(batch, vectors, strict=True)]
            )
            embedded += len(batch)
        except Exception as exc:
            failures += 1
            log.warning("embed_batch_failed", error=str(exc), batch=len(batch))
        batch, budget = [], 0

    for job in pending:
        text = f"{job.title} at {job.company}. {job.description}"[:8_000]
        tokens = len(text) // 3
        if batch and (budget + tokens > _EMBED_TOKEN_BUDGET or len(batch) >= _EMBED_BATCH):
            await _flush()
            if failures >= _EMBED_MAX_FAILURES:
                log.warning("embed_backfill_aborted", pending=len(pending) - embedded)
                return embedded
        batch.append((job, text))
        budget += tokens
    await _flush()
    return embedded


async def run(limit: int | None = None) -> dict[str, int]:
    listings = await _gather_listings(limit)
    async with _session_factory() as session:
        repo = JobRepository(session)
        upserted = await repo.upsert_many(listings)
        embedded = await _backfill_embeddings(repo)
        total = await repo.count()
    stats = {"fetched": len(listings), "upserted": upserted, "embedded": embedded, "total": total}
    log.info("ingest_complete", **stats)
    return stats
