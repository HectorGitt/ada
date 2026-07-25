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

from ada.db.models import (
    Application,
    ApplicationStatus,
    ChatTurn,
    Job,
    ProcessedEvent,
    Profile,
    Run,
    RunStatus,
    UploadedDocument,
    UserMemory,
)

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

    async def set_identity(
        self, *, user_id: str, full_name: str, phone: str | None
    ) -> Profile:
        stmt = (
            insert(Profile)
            .values(user_id=user_id, profile_text="", full_name=full_name, phone=phone)
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={"full_name": full_name, "phone": phone},
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

    async def get(self, job_id: int) -> Job | None:
        return await self._s.get(Job, job_id)

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


class UploadedDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(
        self,
        *,
        user_id: str,
        filename: str,
        content_type: str | None,
        size_bytes: int,
        gcs_uri: str | None,
        cv_text: str,
    ) -> UploadedDocument:
        doc = UploadedDocument(
            user_id=user_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            gcs_uri=gcs_uri,
            cv_text=cv_text,
        )
        self._s.add(doc)
        await self._s.commit()
        await self._s.refresh(doc)
        return doc

    async def list_for_user(self, user_id: str) -> list[UploadedDocument]:
        stmt = (
            select(UploadedDocument)
            .where(UploadedDocument.user_id == user_id)
            .order_by(UploadedDocument.created_at.desc())
        )
        return list((await self._s.execute(stmt)).scalars())

    async def get_for_user(self, doc_id: int, user_id: str) -> UploadedDocument | None:
        stmt = select(UploadedDocument).where(
            UploadedDocument.id == doc_id, UploadedDocument.user_id == user_id
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()


class ApplicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create_or_get(
        self, *, application_id: str, user_id: str, job_id: int, run_id: str | None
    ) -> tuple[Application, bool]:
        stmt = (
            insert(Application)
            .values(
                id=application_id, user_id=user_id, job_id=job_id, run_id=run_id,
                status=ApplicationStatus.PREPARING,
            )
            .on_conflict_do_nothing(constraint="uq_application_user_job")
            .returning(Application.id)
        )
        created = (await self._s.execute(stmt)).scalar_one_or_none() is not None
        await self._s.commit()
        existing = (
            await self._s.execute(
                select(Application).where(
                    Application.user_id == user_id, Application.job_id == job_id
                )
            )
        ).scalar_one()
        return existing, created

    async def get(self, application_id: str) -> Application | None:
        return await self._s.get(Application, application_id)

    async def count_in_flight(self, user_id: str) -> int:
        stmt = select(func.count(Application.id)).where(
            Application.user_id == user_id,
            Application.status == ApplicationStatus.PREPARING,
        )
        return (await self._s.execute(stmt)).scalar_one()

    async def claim_for_retry(self, application_id: str) -> bool:
        """Move a finished-unsuccessfully application back to PREPARING; True only if
        this call won the transition, so a double retry dispatches once."""
        stmt = (
            update(Application)
            .where(
                Application.id == application_id,
                Application.status.in_(
                    [ApplicationStatus.NEEDS_ATTENTION, ApplicationStatus.FAILED]
                ),
            )
            .values(status=ApplicationStatus.PREPARING, detail=None)
            .returning(Application.id)
        )
        claimed = (await self._s.execute(stmt)).scalar_one_or_none() is not None
        await self._s.commit()
        return claimed

    async def find_stuck(self, older_than_seconds: int) -> list[str]:
        cutoff = datetime.now(UTC) - timedelta(seconds=older_than_seconds)
        stmt = select(Application.id).where(
            Application.status == ApplicationStatus.PREPARING,
            Application.created_at < cutoff,
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def set_status(
        self,
        application_id: str,
        status: ApplicationStatus,
        *,
        detail: str | None = None,
    ) -> None:
        values: dict[str, Any] = {"status": status, "detail": detail}
        if status == ApplicationStatus.SUBMITTED:
            values["submitted_at"] = datetime.now(UTC)
        await self._s.execute(
            update(Application).where(Application.id == application_id).values(**values)
        )
        await self._s.commit()

    async def list_by_user(
        self, user_id: str, *, limit: int = 100
    ) -> list[tuple[Application, Job]]:
        stmt = (
            select(Application, Job)
            .join(Job, Job.id == Application.job_id)
            .where(Application.user_id == user_id)
            .order_by(Application.created_at.desc())
            .limit(limit)
        )
        rows = (await self._s.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]


class UserMemoryRepository:
    """Long-term facts Ada keeps per user. Capped; oldest fall off first."""

    MAX_PER_USER = 150

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add_many(
        self, user_id: str, facts: list[tuple[str, list[float]]], source: str = "chat"
    ) -> int:
        for content, embedding in facts:
            self._s.add(
                UserMemory(user_id=user_id, content=content, source=source, embedding=embedding)
            )
        await self._s.commit()
        await self._prune(user_id)
        return len(facts)

    async def list_for_user(self, user_id: str) -> list[UserMemory]:
        stmt = (
            select(UserMemory)
            .where(UserMemory.user_id == user_id)
            .order_by(UserMemory.created_at.desc())
        )
        return list((await self._s.execute(stmt)).scalars())

    async def recall(self, user_id: str, embedding: list[float], k: int) -> list[UserMemory]:
        """The user's memories nearest to the query, closest first."""
        distance = UserMemory.embedding.cosine_distance(embedding)
        stmt = (
            select(UserMemory)
            .where(UserMemory.user_id == user_id)
            .order_by(distance)
            .limit(k)
        )
        return list((await self._s.execute(stmt)).scalars())

    async def delete_for_user(self, memory_id: int, user_id: str) -> bool:
        memory = await self._s.get(UserMemory, memory_id)
        if memory is None or memory.user_id != user_id:
            return False
        await self._s.delete(memory)
        await self._s.commit()
        return True

    async def _prune(self, user_id: str) -> None:
        stmt = (
            select(UserMemory.id)
            .where(UserMemory.user_id == user_id)
            .order_by(UserMemory.created_at.desc())
            .offset(self.MAX_PER_USER)
        )
        stale = list((await self._s.execute(stmt)).scalars())
        if stale:
            for memory_id in stale:
                memory = await self._s.get(UserMemory, memory_id)
                if memory is not None:
                    await self._s.delete(memory)
            await self._s.commit()


class ChatMessageRepository:
    """The user's rolling Ask Ada conversation; oldest turns beyond the cap are dropped."""

    MAX_PER_USER = 400

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def append(self, user_id: str, role: str, content: str) -> None:
        self._s.add(ChatTurn(user_id=user_id, role=role, content=content))
        await self._s.commit()

    async def list_recent(self, user_id: str, limit: int = 100) -> list[ChatTurn]:
        """The newest `limit` turns, returned oldest-first for direct rendering."""
        stmt = (
            select(ChatTurn)
            .where(ChatTurn.user_id == user_id)
            .order_by(ChatTurn.id.desc())
            .limit(limit)
        )
        rows = list((await self._s.execute(stmt)).scalars())
        return list(reversed(rows))

    async def clear(self, user_id: str) -> None:
        stmt = select(ChatTurn).where(ChatTurn.user_id == user_id)
        for turn in (await self._s.execute(stmt)).scalars():
            await self._s.delete(turn)
        await self._s.commit()

    async def prune(self, user_id: str) -> None:
        stmt = (
            select(ChatTurn.id)
            .where(ChatTurn.user_id == user_id)
            .order_by(ChatTurn.id.desc())
            .offset(self.MAX_PER_USER)
        )
        for turn_id in (await self._s.execute(stmt)).scalars():
            turn = await self._s.get(ChatTurn, turn_id)
            if turn is not None:
                await self._s.delete(turn)
        await self._s.commit()
