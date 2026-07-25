"""Data-access layer. Services depend on these, not on the ORM directly.

Idempotency and exactly-once execution are enforced here as atomic SQL:
  - PaymentRepository.confirm claims a webhook event and advances the run to PAID in one
    transaction (guards against replayed/duplicate webhooks).
  - RunRepository.claim_for_execution transitions PAID -> RUNNING via
    UPDATE ... WHERE status = PAID, so concurrent workers cannot both run the same job.
"""
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ada.db.models import Job, ProcessedEvent, Profile, Run, RunStatus

# Filler words that carry no signal when matching a role name against job titles.
_ROLE_STOPWORDS = {"a", "an", "and", "the", "of", "for", "in", "at", "to", "or"}


def role_keywords(role: str) -> list[str]:
    """Meaningful search tokens from a free-text role name.

    Alphabetic tokens of 3+ characters, lowercased, stopwords removed, capped at
    six. Tokens are letters-only by construction, so they are safe to embed in
    ILIKE patterns without escaping.
    """
    words = re.findall(r"[a-zA-Z]{3,}", role.lower())
    seen: list[str] = []
    for w in words:
        if w not in _ROLE_STOPWORDS and w not in seen:
            seen.append(w)
    return seen[:6]


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def claim(self, provider: str, reference: str) -> bool:
        """Insert-or-ignore. True only the first time a reference is seen."""
        stmt = (
            insert(ProcessedEvent)
            .values(provider=provider, reference=reference)
            .on_conflict_do_nothing(index_elements=["provider", "reference"])
            .returning(ProcessedEvent.id)
        )
        claimed = (await self._s.execute(stmt)).scalar_one_or_none() is not None
        await self._s.commit()
        return claimed


class PaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def confirm(
        self, *, provider: str, event_ref: str, run_id: str | None
    ) -> Literal["claimed", "duplicate", "no_run"]:
        """Claim the event and advance the run to PAID atomically.

        Returns "duplicate" if the event was already processed, "no_run" if no matching
        pending run exists, else "claimed".
        """
        ins = (
            insert(ProcessedEvent)
            .values(provider=provider, reference=event_ref)
            .on_conflict_do_nothing(index_elements=["provider", "reference"])
            .returning(ProcessedEvent.id)
        )
        if (await self._s.execute(ins)).scalar_one_or_none() is None:
            await self._s.rollback()
            return "duplicate"
        if run_id is not None:
            upd = (
                update(Run)
                .where(Run.id == run_id, Run.status == RunStatus.PENDING_PAYMENT)
                .values(status=RunStatus.PAID)
                .returning(Run.id)
            )
            advanced = (await self._s.execute(upd)).scalar_one_or_none() is not None
        else:
            advanced = False
        # Commit even when no run advanced so the event stays claimed and idempotent.
        await self._s.commit()
        return "claimed" if advanced else "no_run"


class RunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, run: Run) -> Run:
        self._s.add(run)
        await self._s.commit()
        return run

    async def get(self, run_id: str) -> Run | None:
        return await self._s.get(Run, run_id)

    async def get_by_reference(self, reference: str) -> Run | None:
        stmt = select(Run).where(Run.reference == reference)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def list_by_user(self, user_id: str, *, limit: int = 50) -> list[Run]:
        stmt = (
            select(Run)
            .where(Run.user_id == user_id)
            .order_by(Run.created_at.desc())
            .limit(limit)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def claim_for_execution(self, run_id: str) -> Run | None:
        """Transition PAID -> RUNNING atomically; return the run only if this call won."""
        upd = (
            update(Run)
            .where(Run.id == run_id, Run.status == RunStatus.PAID)
            .values(status=RunStatus.RUNNING)
            .returning(Run.id)
        )
        claimed = (await self._s.execute(upd)).scalar_one_or_none() is not None
        await self._s.commit()
        return await self.get(run_id) if claimed else None

    async def find_stuck(self, older_than_seconds: int) -> list[str]:
        """Ids of runs left in PAID past the dispatch window (dispatch presumed lost)."""
        cutoff = datetime.now(UTC) - timedelta(seconds=older_than_seconds)
        stmt = select(Run.id).where(Run.status == RunStatus.PAID, Run.created_at < cutoff)
        return list((await self._s.execute(stmt)).scalars().all())

    async def set_status(self, run: Run, status: RunStatus) -> None:
        run.status = status
        await self._s.commit()

    async def set_stage(self, run_id: str, stage: str) -> None:
        """Record the graph node currently executing — live progress for the UI."""
        await self._s.execute(update(Run).where(Run.id == run_id).values(stage=stage))
        await self._s.commit()

    async def set_deliverables(
        self, run: Run, *, rewritten_cv: str, matches: list[Any], questions: list[Any]
    ) -> None:
        """Store the graph's autonomous output and mark the run complete."""
        run.rewritten_cv = rewritten_cv
        run.matches_json = matches
        run.questions_json = questions
        run.status = RunStatus.COMPLETE
        run.stage = None
        await self._s.commit()

    async def set_interview(self, run: Run, interview: dict[str, Any]) -> None:
        run.interview_json = interview
        await self._s.commit()


class ProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, user_id: str) -> Profile | None:
        return await self._s.get(Profile, user_id)

    async def upsert(
        self, *, user_id: str, profile_text: str, linkedin_url: str | None
    ) -> Profile:
        stmt = (
            insert(Profile)
            .values(user_id=user_id, profile_text=profile_text, linkedin_url=linkedin_url)
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={"profile_text": profile_text, "linkedin_url": linkedin_url},
            )
        )
        await self._s.execute(stmt)
        await self._s.commit()
        profile = await self._s.get(Profile, user_id)
        if profile is None:
            raise RuntimeError(f"profile missing immediately after upsert for {user_id}")
        return profile


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def count(self) -> int:
        return (await self._s.execute(select(func.count(Job.id)))).scalar_one()

    async def add_many(self, jobs: list[Job]) -> None:
        self._s.add_all(jobs)
        await self._s.commit()

    async def preview(self, role: str, *, sample_size: int = 4) -> tuple[int, list[Job]]:
        """Cheap pre-payment teaser: keyword lookup of the role against job titles.

        Deliberately NOT the paid matching — no embeddings, no ranking, no
        reasons. Returns (total count, a few sample jobs) so the UI can show an
        honest peek before checkout.
        """
        keywords = role_keywords(role)
        if not keywords:
            return 0, []
        cond = or_(*(Job.title.ilike(f"%{k}%") for k in keywords))
        count = (
            await self._s.execute(select(func.count(Job.id)).where(cond))
        ).scalar_one()
        rows = (
            await self._s.execute(
                select(Job).where(cond).order_by(Job.id).limit(sample_size)
            )
        ).scalars()
        return count, list(rows.all())

    _UPSERT_BATCH = 500

    async def upsert_many(self, listings: list[dict[str, Any]]) -> int:
        """Insert-or-refresh keyed on (source, external_id); a NULL incoming
        embedding never overwrites a stored vector."""
        listings = list({(li["source"], li["external_id"]): li for li in listings}.values())
        for start in range(0, len(listings), self._UPSERT_BATCH):
            batch = listings[start : start + self._UPSERT_BATCH]
            stmt = insert(Job).values(batch)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_jobs_source_external",
                set_={
                    "title": stmt.excluded.title,
                    "company": stmt.excluded.company,
                    "location": stmt.excluded.location,
                    "remote": stmt.excluded.remote,
                    "url": stmt.excluded.url,
                    "description": stmt.excluded.description,
                    "posted_at": stmt.excluded.posted_at,
                    "embedding": func.coalesce(stmt.excluded.embedding, Job.embedding),
                },
            )
            await self._s.execute(stmt)
        await self._s.commit()
        return len(listings)

    async def unembedded(self, limit: int = 200) -> list[Job]:
        stmt = select(Job).where(Job.embedding.is_(None)).limit(limit)
        return list((await self._s.execute(stmt)).scalars())

    async def set_embeddings(self, pairs: list[tuple[int, list[float]]]) -> None:
        for job_id, vector in pairs:
            await self._s.execute(update(Job).where(Job.id == job_id).values(embedding=vector))
        await self._s.commit()

    async def knn(self, embedding: list[float], k: int) -> list[tuple[Job, float]]:
        """Nearest embedded jobs by cosine distance. Returns (job, distance), closest first."""
        distance = Job.embedding.cosine_distance(embedding).label("distance")
        stmt = (
            select(Job, distance)
            .where(Job.embedding.is_not(None))
            .order_by(distance)
            .limit(k)
        )
        rows = (await self._s.execute(stmt)).all()
        return [(row[0], float(row[1])) for row in rows]
