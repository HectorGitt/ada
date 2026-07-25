"""Seed the jobs table with embeddings. Idempotent: no-op if already populated.

Run once after migrating (or after adding roles to data/jobs.json):  `make seed`.
Embedding happens here, at seed time — never on the app boot path.
"""
import asyncio
import json
from pathlib import Path

from ada.db.models import Job
from ada.db.repositories import JobRepository
from ada.db.session import _session_factory
from ada.observability import configure_logging, log
from ada.services.search import SearchService

_DATA = Path(__file__).with_name("data") / "jobs.json"


async def seed_jobs() -> int:
    async with _session_factory() as session:
        repo = JobRepository(session)
        if await repo.count() > 0:
            return 0
        raw = json.loads(_DATA.read_text())
        texts = [f"{j['title']} at {j['company']}. {j['description']}" for j in raw]
        vectors = await SearchService().embed_many(texts)
        jobs = [
            Job(
                source="seed", external_id=f"seed-{i}",
                title=j["title"], company=j["company"], location=j["location"],
                description=j["description"], embedding=vector,
            )
            for i, (j, vector) in enumerate(zip(raw, vectors, strict=True))
        ]
        await repo.add_many(jobs)
        return len(jobs)


def main() -> None:
    configure_logging()
    n = asyncio.run(seed_jobs())
    log.info("seed_jobs", inserted=n)
    print(f"seeded {n} jobs")


if __name__ == "__main__":
    main()
