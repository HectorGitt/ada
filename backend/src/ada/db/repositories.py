"""Data-access layer. Services depend on these, not on the ORM directly.

Idempotency and exactly-once execution are enforced here as atomic SQL:
  - PaymentRepository.confirm claims a webhook event and advances the run to PAID in one
    transaction (guards against replayed/duplicate webhooks).
  - RunRepository.claim_for_execution transitions PAID -> RUNNING via
    UPDATE ... WHERE status = PAID, so concurrent workers cannot both run the same job.
"""
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ada.db.models import (
    AdminAudit,
    Application,
    ApplicationStatus,
    Assessment,
    AssessmentStatus,
    AssessmentVerdict,
    ChatTurn,
    CompanyProfile,
    Intro,
    IntroMessage,
    IntroStatus,
    Job,
    Notification,
    NotificationPref,
    Outcome,
    OutcomeStage,
    ProcessedEvent,
    Profile,
    PushSubscription,
    Run,
    RunStatus,
    SavedCandidate,
    ShortlistStage,
    Subscription,
    SubscriptionStatus,
    UploadedDocument,
    User,
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

    async def by_phone(self, digits: str) -> Profile | None:
        """Find a profile by the trailing digits of its phone — used to map an inbound
        WhatsApp `From` to the candidate, tolerant of '+', country code and formatting.
        Empty/too-short input matches nothing."""
        if len(digits) < 7:
            return None
        normalized = func.regexp_replace(Profile.phone, r"\D", "", "g")
        stmt = select(Profile).where(normalized.like(f"%{digits}")).limit(1)
        return (await self._s.execute(stmt)).scalar_one_or_none()

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
        self, *, user_id: str, full_name: str, phone: str | None,
        compensation: str | None = None, work_pref: str | None = None,
    ) -> Profile:
        fields = {
            "full_name": full_name, "phone": phone,
            "compensation": compensation, "work_pref": work_pref,
        }
        stmt = (
            insert(Profile)
            .values(user_id=user_id, profile_text="", **fields)
            .on_conflict_do_update(index_elements=["user_id"], set_=fields)
        )
        await self._s.execute(stmt)
        await self._s.commit()
        profile = await self._s.get(Profile, user_id)
        if profile is None:
            raise RuntimeError(f"profile missing immediately after upsert for {user_id}")
        return profile

    async def set_discoverable(self, user_id: str, discoverable: bool) -> None:
        await self._s.execute(
            update(Profile).where(Profile.user_id == user_id).values(discoverable=discoverable)
        )
        await self._s.commit()

    async def set_identity_verified(self, user_id: str, *, method: str) -> None:
        await self._s.execute(
            update(Profile)
            .where(Profile.user_id == user_id)
            .values(identity_verified=True, identity_method=method)
        )
        await self._s.commit()

    async def set_analysis(
        self,
        user_id: str,
        *,
        embedding: list[float] | None,
        insights: dict[str, Any] | None,
        headline: str | None,
        location: str | None,
    ) -> None:
        """Persist Ada's structured analysis + the candidate search vector."""
        await self._s.execute(
            update(Profile)
            .where(Profile.user_id == user_id)
            .values(embedding=embedding, insights=insights, headline=headline, location=location)
        )
        await self._s.commit()

    async def list_embedded_candidates(self, *, limit: int = 500) -> list[Profile]:
        """Candidate profiles with a search vector — the audience for the proactive
        digest (they've engaged enough to be matchable)."""
        stmt = (
            select(Profile)
            .join(User, User.id == Profile.user_id)
            .where(Profile.embedding.is_not(None), User.account_type == "candidate")
            .limit(limit)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def search_candidates(
        self, embedding: list[float], k: int, *, exclude: str | None = None
    ) -> list[tuple[Profile, float]]:
        """Discoverable, embedded candidates nearest to a role vector (cosine)."""
        distance = Profile.embedding.cosine_distance(embedding).label("distance")
        stmt = (
            select(Profile, distance)
            .where(Profile.discoverable.is_(True), Profile.embedding.is_not(None))
            .order_by(distance)
            .limit(k)
        )
        if exclude is not None:
            stmt = stmt.where(Profile.user_id != exclude)
        rows = (await self._s.execute(stmt)).all()
        return [(row[0], float(row[1])) for row in rows]

    async def search_talent(
        self, *, q: str | None, location: str | None, seniority: str | None,
        verified_only: bool, exclude: str | None, limit: int,
    ) -> list[Profile]:
        """Filtered search over the discoverable pool — the employer's talent search. SQL
        only (no embedding needed), so it works even when generation/embeddings are down."""
        stmt = select(Profile).where(Profile.discoverable.is_(True))
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Profile.headline.ilike(like), Profile.profile_text.ilike(like)))
        if location:
            stmt = stmt.where(Profile.location.ilike(f"%{location}%"))
        if seniority:
            stmt = stmt.where(Profile.insights["seniority"].astext == seniority)
        if verified_only:
            stmt = stmt.where(Profile.identity_verified.is_(True))
        if exclude is not None:
            stmt = stmt.where(Profile.user_id != exclude)
        stmt = stmt.order_by(Profile.updated_at.desc()).limit(limit)
        return list((await self._s.execute(stmt)).scalars().all())


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, job_id: int) -> Job | None:
        return await self._s.get(Job, job_id)

    async def create_posting(self, job: Job) -> Job:
        """An employer-posted role (source='employer', posted_by set). Joins the pool."""
        self._s.add(job)
        await self._s.commit()
        await self._s.refresh(job)
        return job

    async def list_by_poster(self, user_id: str, *, limit: int = 100) -> list[Job]:
        stmt = (
            select(Job)
            .where(Job.posted_by == user_id)
            .order_by(Job.id.desc())
            .limit(limit)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def set_embedding(self, job_id: int, embedding: list[float]) -> None:
        await self._s.execute(update(Job).where(Job.id == job_id).values(embedding=embedding))
        await self._s.commit()

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


class SubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, user_id: str) -> Subscription | None:
        return await self._s.get(Subscription, user_id)

    async def activate(
        self,
        *,
        user_id: str,
        tier: str,
        cadence: str,
        provider: str,
        provider_ref: str | None,
        current_period_end: datetime | None,
    ) -> None:
        """Idempotent upsert to an active plan — a replayed 'created' webhook is a no-op."""
        values = {
            "tier": tier,
            "status": SubscriptionStatus.ACTIVE,
            "cadence": cadence,
            "provider": provider,
            "provider_ref": provider_ref,
            "current_period_end": current_period_end,
        }
        stmt = insert(Subscription).values(user_id=user_id, **values)
        stmt = stmt.on_conflict_do_update(index_elements=["user_id"], set_=values)
        await self._s.execute(stmt)
        await self._s.commit()

    async def set_status(
        self,
        provider_ref: str,
        status: SubscriptionStatus,
        *,
        current_period_end: datetime | None = None,
    ) -> bool:
        """Advance a subscription by its provider ref (renewal / past_due / cancel).
        Returns False when no row matches, so a stray event is a safe no-op."""
        values: dict[str, Any] = {"status": status}
        if current_period_end is not None:
            values["current_period_end"] = current_period_end
        stmt = (
            update(Subscription)
            .where(Subscription.provider_ref == provider_ref)
            .values(**values)
            .returning(Subscription.user_id)
        )
        matched = (await self._s.execute(stmt)).scalar_one_or_none() is not None
        await self._s.commit()
        return matched


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, user_id: str) -> User | None:
        return await self._s.get(User, user_id)

    async def set_account(
        self, user_id: str, *, account_type: str, company: str | None
    ) -> None:
        await self._s.execute(
            update(User)
            .where(User.id == user_id)
            .values(account_type=account_type, company=company)
        )
        await self._s.commit()


class IntroRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(
        self, *, intro_id: str, employer_id: str, candidate_id: str, job_id: int,
        message: str | None,
    ) -> tuple[Intro, bool]:
        """Idempotent per (employer, candidate, job): re-requesting returns the existing row."""
        stmt = (
            insert(Intro)
            .values(
                id=intro_id, employer_id=employer_id, candidate_id=candidate_id,
                job_id=job_id, message=message, status=IntroStatus.REQUESTED,
            )
            .on_conflict_do_nothing(constraint="uq_intro")
            .returning(Intro.id)
        )
        created = (await self._s.execute(stmt)).scalar_one_or_none() is not None
        await self._s.commit()
        existing = (
            await self._s.execute(
                select(Intro).where(
                    Intro.employer_id == employer_id,
                    Intro.candidate_id == candidate_id,
                    Intro.job_id == job_id,
                )
            )
        ).scalar_one()
        return existing, created

    async def list_for_employer(self, employer_id: str) -> list[Intro]:
        stmt = (
            select(Intro)
            .where(Intro.employer_id == employer_id)
            .order_by(Intro.created_at.desc())
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def requested_candidate_ids(self, employer_id: str, job_id: int) -> set[str]:
        stmt = select(Intro.candidate_id).where(
            Intro.employer_id == employer_id, Intro.job_id == job_id
        )
        return set((await self._s.execute(stmt)).scalars().all())

    async def list_for_candidate(self, candidate_id: str) -> list[tuple[Intro, Job, User]]:
        """Intros sent to this candidate, with the role and the employer behind each."""
        stmt = (
            select(Intro, Job, User)
            .join(Job, Job.id == Intro.job_id)
            .join(User, User.id == Intro.employer_id)
            .where(Intro.candidate_id == candidate_id)
            .order_by(Intro.created_at.desc())
        )
        rows = (await self._s.execute(stmt)).all()
        return [(row[0], row[1], row[2]) for row in rows]

    async def latest_requested_for_candidate(self, candidate_id: str) -> Intro | None:
        """The candidate's most recent still-open intro — the one a WhatsApp reply answers."""
        stmt = (
            select(Intro)
            .where(
                Intro.candidate_id == candidate_id,
                Intro.status == IntroStatus.REQUESTED,
            )
            .order_by(Intro.created_at.desc())
            .limit(1)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def respond(
        self, intro_id: str, candidate_id: str, status: IntroStatus
    ) -> bool:
        """Candidate accepts/declines their own intro. Only a REQUESTED intro can move,
        and only by its candidate — returns False (→ 404) otherwise, idempotently."""
        stmt = (
            update(Intro)
            .where(
                Intro.id == intro_id,
                Intro.candidate_id == candidate_id,
                Intro.status == IntroStatus.REQUESTED,
            )
            .values(status=status)
            .returning(Intro.id)
        )
        moved = (await self._s.execute(stmt)).scalar_one_or_none() is not None
        await self._s.commit()
        return moved


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(
        self, *, notification_id: str, user_id: str, kind: str, title: str,
        body: str | None, link: str | None,
    ) -> Notification:
        n = Notification(
            id=notification_id, user_id=user_id, kind=kind, title=title, body=body, link=link,
        )
        self._s.add(n)
        await self._s.commit()
        return n

    async def list_for_user(self, user_id: str, *, limit: int = 30) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def unread_count(self, user_id: str) -> int:
        stmt = select(func.count(Notification.id)).where(
            Notification.user_id == user_id, Notification.read.is_(False)
        )
        return (await self._s.execute(stmt)).scalar_one()

    async def last_of_kind(self, user_id: str, kind: str) -> datetime | None:
        """Most recent notification of a kind — used to throttle the digest."""
        stmt = (
            select(Notification.created_at)
            .where(Notification.user_id == user_id, Notification.kind == kind)
            .order_by(Notification.created_at.desc())
            .limit(1)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def mark_read(self, user_id: str, notification_id: str | None) -> None:
        """Mark one notification read, or all of the user's when id is None."""
        stmt = update(Notification).where(Notification.user_id == user_id)
        if notification_id is not None:
            stmt = stmt.where(Notification.id == notification_id)
        await self._s.execute(stmt.values(read=True))
        await self._s.commit()


class AssessmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, assessment: Assessment) -> Assessment:
        self._s.add(assessment)
        await self._s.commit()
        await self._s.refresh(assessment)
        return assessment

    async def get(self, assessment_id: str) -> Assessment | None:
        return await self._s.get(Assessment, assessment_id)

    async def latest_for_user(self, user_id: str) -> Assessment | None:
        stmt = (
            select(Assessment)
            .where(Assessment.user_id == user_id)
            .order_by(Assessment.started_at.desc())
            .limit(1)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def latest_scored(self, user_id: str) -> Assessment | None:
        stmt = (
            select(Assessment)
            .where(Assessment.user_id == user_id, Assessment.status == AssessmentStatus.SCORED)
            .order_by(Assessment.started_at.desc())
            .limit(1)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def active_for_user(self, user_id: str) -> Assessment | None:
        """The candidate's most recent in-flight assessment, any skill — lets the client
        resume after a refresh instead of losing the session."""
        stmt = (
            select(Assessment)
            .where(Assessment.user_id == user_id, Assessment.status == AssessmentStatus.PENDING)
            .order_by(Assessment.started_at.desc())
            .limit(1)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def pending_for(self, user_id: str, skill: str) -> Assessment | None:
        """An in-flight (unsubmitted) assessment for this skill — resumed on re-start
        so a candidate can't farm fresh questions by hitting start repeatedly."""
        stmt = (
            select(Assessment)
            .where(
                Assessment.user_id == user_id,
                Assessment.skill == skill,
                Assessment.status == AssessmentStatus.PENDING,
            )
            .order_by(Assessment.started_at.desc())
            .limit(1)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def recent_attempt_count(self, user_id: str, skill: str, since: datetime) -> int:
        stmt = select(func.count(Assessment.id)).where(
            Assessment.user_id == user_id,
            Assessment.skill == skill,
            Assessment.started_at >= since,
        )
        return (await self._s.execute(stmt)).scalar_one()

    async def last_submitted_at(self, user_id: str, skill: str) -> datetime | None:
        stmt = (
            select(Assessment.submitted_at)
            .where(
                Assessment.user_id == user_id,
                Assessment.skill == skill,
                Assessment.submitted_at.is_not(None),
            )
            .order_by(Assessment.submitted_at.desc())
            .limit(1)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def record_result(
        self,
        assessment_id: str,
        *,
        answers: list,
        integrity: dict,
        duration_seconds: int,
        score: int,
        verdict: AssessmentVerdict,
        evidence: dict,
    ) -> None:
        await self._s.execute(
            update(Assessment)
            .where(Assessment.id == assessment_id)
            .values(
                answers=answers, integrity=integrity, duration_seconds=duration_seconds,
                score=score, verdict=verdict, evidence=evidence,
                status=AssessmentStatus.SCORED, submitted_at=datetime.now(UTC),
            )
        )
        await self._s.commit()


class NotificationPrefRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_or_create(self, user_id: str) -> NotificationPref:
        pref = await self._s.get(NotificationPref, user_id)
        if pref is None:
            pref = NotificationPref(user_id=user_id, unsubscribe_token=uuid.uuid4().hex)
            self._s.add(pref)
            await self._s.commit()
            await self._s.refresh(pref)
        return pref

    async def update(
        self, user_id: str, *, email: bool, whatsapp: bool, digest: bool
    ) -> NotificationPref:
        pref = await self.get_or_create(user_id)
        await self._s.execute(
            update(NotificationPref)
            .where(NotificationPref.user_id == user_id)
            .values(email_enabled=email, whatsapp_enabled=whatsapp, digest_enabled=digest)
        )
        await self._s.commit()
        pref.email_enabled, pref.whatsapp_enabled, pref.digest_enabled = email, whatsapp, digest
        return pref

    async def by_token(self, token: str) -> NotificationPref | None:
        stmt = select(NotificationPref).where(NotificationPref.unsubscribe_token == token)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def unsubscribe_all(self, token: str) -> bool:
        """One-click unsubscribe from the email footer — kills every side channel."""
        stmt = (
            update(NotificationPref)
            .where(NotificationPref.unsubscribe_token == token)
            .values(email_enabled=False, whatsapp_enabled=False, digest_enabled=False)
            .returning(NotificationPref.user_id)
        )
        ok = (await self._s.execute(stmt)).scalar_one_or_none() is not None
        await self._s.commit()
        return ok


class PushSubscriptionRepository:
    """Browser Web Push endpoints, one per device. Dead endpoints are pruned on send."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def upsert(self, *, user_id: str, endpoint: str, p256dh: str, auth: str) -> None:
        """Register (or re-point) a subscription. The endpoint is the identity, so a
        browser that re-subscribes updates its keys and owner in place."""
        stmt = (
            insert(PushSubscription)
            .values(user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
            .on_conflict_do_update(
                index_elements=["endpoint"],
                set_={"user_id": user_id, "p256dh": p256dh, "auth": auth},
            )
        )
        await self._s.execute(stmt)
        await self._s.commit()

    async def list_for_user(self, user_id: str) -> list[PushSubscription]:
        stmt = select(PushSubscription).where(PushSubscription.user_id == user_id)
        return list((await self._s.execute(stmt)).scalars().all())

    async def delete(self, *, user_id: str, endpoint: str) -> None:
        # Scoped to the owner (audit #2): knowing an endpoint isn't enough to unsubscribe it.
        await self._s.execute(
            delete(PushSubscription).where(
                PushSubscription.user_id == user_id,
                PushSubscription.endpoint == endpoint,
            )
        )
        await self._s.commit()


class OutcomeRepository:
    """The candidate's hiring funnel — one row per role pursued, advanced through stages."""

    # Stages are ordered; the funnel counts everyone who reached at least each stage.
    _ORDER = [
        OutcomeStage.APPLIED,
        OutcomeStage.INTERVIEWING,
        OutcomeStage.OFFER,
        OutcomeStage.HIRED,
    ]

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def seed(
        self, *, user_id: str, job_id: int | None, company: str, role_title: str, source: str
    ) -> None:
        """Record that a pursuit began, if we aren't already tracking it. Never regresses
        a stage the candidate has already advanced — insert-only, on-conflict-do-nothing."""
        if job_id is None:  # a unique constraint on (user, NULL) won't dedupe — skip seeding
            return
        stmt = (
            insert(Outcome)
            .values(
                id=uuid.uuid4().hex, user_id=user_id, job_id=job_id, company=company,
                role_title=role_title, stage=OutcomeStage.APPLIED, source=source,
            )
            .on_conflict_do_nothing(constraint="uq_outcome_user_job")
        )
        await self._s.execute(stmt)
        await self._s.commit()

    async def create_manual(
        self, *, user_id: str, company: str, role_title: str, stage: OutcomeStage
    ) -> Outcome:
        outcome = Outcome(
            id=uuid.uuid4().hex, user_id=user_id, job_id=None, company=company,
            role_title=role_title, stage=stage, source="manual",
        )
        self._s.add(outcome)
        await self._s.commit()
        await self._s.refresh(outcome)
        return outcome

    async def set_stage(
        self, *, outcome_id: str, user_id: str, stage: OutcomeStage
    ) -> Outcome | None:
        """Advance (or correct) a stage — scoped to the owner so one user can't touch
        another's pipeline."""
        stmt = (
            update(Outcome)
            .where(Outcome.id == outcome_id, Outcome.user_id == user_id)
            .values(stage=stage)
            .returning(Outcome)
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        await self._s.commit()
        return row

    async def list_by_user(self, user_id: str, *, limit: int = 200) -> list[Outcome]:
        stmt = (
            select(Outcome)
            .where(Outcome.user_id == user_id)
            .order_by(Outcome.updated_at.desc())
            .limit(limit)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def funnel(self, user_id: str) -> dict[str, int]:
        """Count of pursuits currently at each stage. 'rejected' is terminal and reported
        separately from the forward funnel."""
        stmt = (
            select(Outcome.stage, func.count(Outcome.id))
            .where(Outcome.user_id == user_id)
            .group_by(Outcome.stage)
        )
        rows = (await self._s.execute(stmt)).all()
        return {str(stage): count for stage, count in rows}


class AdminRepository:
    """Read-side aggregates, privileged mutations, and the audit trail for the admin
    dashboard. Every mutating admin action is expected to also call record_audit."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _scalar(self, stmt: Any) -> int:
        return int((await self._s.execute(stmt)).scalar_one())

    async def overview(self) -> dict[str, Any]:
        """A snapshot of the whole marketplace for the dashboard's home."""
        by_type = {
            t: c
            for t, c in (
                await self._s.execute(
                    select(User.account_type, func.count(User.id)).group_by(User.account_type)
                )
            ).all()
        }
        runs_by_status = {
            str(st): c
            for st, c in (
                await self._s.execute(
                    select(Run.status, func.count(Run.id)).group_by(Run.status)
                )
            ).all()
        }
        subs_by_tier = {
            t: c
            for t, c in (
                await self._s.execute(
                    select(Subscription.tier, func.count())
                    .where(
                        Subscription.status.in_(
                            [SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE]
                        )
                    )
                    .group_by(Subscription.tier)
                )
            ).all()
        }
        paid = [RunStatus.PAID, RunStatus.RUNNING, RunStatus.COMPLETE]
        revenue = [
            {"currency": cur, "amount_minor": int(total or 0), "runs": cnt}
            for cur, total, cnt in (
                await self._s.execute(
                    select(Run.currency, func.coalesce(func.sum(Run.amount), 0), func.count(Run.id))
                    .where(Run.status.in_(paid))
                    .group_by(Run.currency)
                )
            ).all()
        ]
        return {
            "users_total": await self._scalar(select(func.count(User.id))),
            "users_by_type": by_type,
            "runs_total": await self._scalar(select(func.count(Run.id))),
            "runs_by_status": runs_by_status,
            "subscriptions_active": sum(subs_by_tier.values()),
            "subscriptions_by_tier": subs_by_tier,
            "jobs_total": await self._scalar(select(func.count(Job.id))),
            "jobs_embedded": await self._scalar(
                select(func.count(Job.id)).where(Job.embedding.isnot(None))
            ),
            "applications_total": await self._scalar(select(func.count(Application.id))),
            "applications_submitted": await self._scalar(
                select(func.count(Application.id)).where(
                    Application.status == ApplicationStatus.SUBMITTED
                )
            ),
            "intros_total": await self._scalar(select(func.count(Intro.id))),
            "intros_accepted": await self._scalar(
                select(func.count(Intro.id)).where(Intro.status == IntroStatus.ACCEPTED)
            ),
            "identity_verified": await self._scalar(
                select(func.count()).select_from(Profile).where(Profile.identity_verified.is_(True))
            ),
            "assessments_verified": await self._scalar(
                select(func.count(Assessment.id)).where(
                    Assessment.verdict == AssessmentVerdict.VERIFIED
                )
            ),
            "revenue": revenue,
        }

    async def list_users(
        self, *, q: str | None, limit: int, offset: int
    ) -> list[tuple[User, Subscription | None]]:
        stmt = select(User, Subscription).join(
            Subscription, Subscription.user_id == User.id, isouter=True
        )
        if q:
            stmt = stmt.where(or_(User.email.ilike(f"%{q}%"), User.company.ilike(f"%{q}%")))
        stmt = stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)
        rows = (await self._s.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]

    async def user_counts(self, user_id: str) -> dict[str, int]:
        return {
            "runs": await self._scalar(
                select(func.count(Run.id)).where(Run.user_id == user_id)
            ),
            "applications": await self._scalar(
                select(func.count(Application.id)).where(Application.user_id == user_id)
            ),
        }

    async def list_runs(
        self, *, status: str | None, limit: int, offset: int
    ) -> list[Run]:
        stmt = select(Run)
        if status:
            stmt = stmt.where(Run.status == status)
        stmt = stmt.order_by(Run.created_at.desc()).limit(limit).offset(offset)
        return list((await self._s.execute(stmt)).scalars().all())

    async def list_events(self, *, limit: int) -> list[ProcessedEvent]:
        stmt = select(ProcessedEvent).order_by(ProcessedEvent.id.desc()).limit(limit)
        return list((await self._s.execute(stmt)).scalars().all())

    async def all_user_ids(self, *, account_type: str | None) -> list[str]:
        """User ids for a broadcast, optionally scoped to candidates/employers."""
        stmt = select(User.id)
        if account_type:
            stmt = stmt.where(User.account_type == account_type)
        return list((await self._s.execute(stmt)).scalars().all())

    async def delete_user(self, user_id: str) -> None:
        """Hard-delete a user and every row that references them, in FK-safe order.
        Employer-posted jobs are kept (posted_by nulled), so the job pool is preserved."""
        from ada.db.models import (
            AuthToken,
            ChatTurn,
            Notification,
            Outcome,
            Session,
            UploadedDocument,
            UserMemory,
        )

        await self._s.execute(
            update(Job).where(Job.posted_by == user_id).values(posted_by=None)
        )
        for model in (
            Outcome, Application, Assessment, Notification, NotificationPref,
            PushSubscription, UserMemory, ChatTurn, UploadedDocument, Profile,
            Subscription, Run, AuthToken, Session,
        ):
            await self._s.execute(delete(model).where(model.user_id == user_id))
        await self._s.execute(
            delete(Intro).where(
                or_(Intro.employer_id == user_id, Intro.candidate_id == user_id)
            )
        )
        await self._s.execute(delete(User).where(User.id == user_id))
        await self._s.commit()

    async def record_audit(
        self, *, admin_email: str, action: str,
        target_user_id: str | None = None, detail: dict[str, Any] | None = None,
    ) -> None:
        self._s.add(
            AdminAudit(
                admin_email=admin_email, action=action,
                target_user_id=target_user_id, detail=detail,
            )
        )
        await self._s.commit()

    async def list_audit(self, *, limit: int) -> list[AdminAudit]:
        stmt = select(AdminAudit).order_by(AdminAudit.id.desc()).limit(limit)
        return list((await self._s.execute(stmt)).scalars().all())

    async def set_account_type(self, user_id: str, account_type: str) -> bool:
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(account_type=account_type)
            .returning(User.id)
        )
        ok = (await self._s.execute(stmt)).scalar_one_or_none() is not None
        await self._s.commit()
        return ok

    async def revoke_subscription(self, user_id: str) -> None:
        """Drop a user back to free by cancelling their subscription row."""
        await self._s.execute(
            update(Subscription)
            .where(Subscription.user_id == user_id)
            .values(status=SubscriptionStatus.CANCELED)
        )
        await self._s.commit()


class CompanyRepository:
    """An employer's company profile — one per employer user. Also read publicly for the
    company page and to enrich intros."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, user_id: str) -> CompanyProfile | None:
        return await self._s.get(CompanyProfile, user_id)

    async def upsert(self, user_id: str, values: dict[str, Any]) -> CompanyProfile:
        stmt = insert(CompanyProfile).values(user_id=user_id, **values)
        stmt = stmt.on_conflict_do_update(index_elements=["user_id"], set_=values)
        await self._s.execute(stmt)
        await self._s.commit()
        existing = await self._s.get(CompanyProfile, user_id)
        if existing is None:  # unreachable after an upsert; keeps the return type honest
            raise RuntimeError("company profile missing after upsert")
        return existing


class ShortlistRepository:
    """The employer's talent pipeline — saved candidates moving through stages."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(
        self, *, entry_id: str, employer_id: str, candidate_id: str,
        job_id: int | None, note: str | None,
    ) -> SavedCandidate:
        """Add a candidate to the pipeline, or return the existing entry (idempotent)."""
        stmt = (
            insert(SavedCandidate)
            .values(
                id=entry_id, employer_id=employer_id, candidate_id=candidate_id,
                job_id=job_id, note=note, stage=ShortlistStage.SHORTLISTED,
            )
            .on_conflict_do_nothing(constraint="uq_saved_candidate")
        )
        await self._s.execute(stmt)
        await self._s.commit()
        existing = (
            await self._s.execute(
                select(SavedCandidate).where(
                    SavedCandidate.employer_id == employer_id,
                    SavedCandidate.candidate_id == candidate_id,
                )
            )
        ).scalar_one()
        return existing

    async def list_for_employer(self, employer_id: str) -> list[tuple[SavedCandidate, Profile]]:
        stmt = (
            select(SavedCandidate, Profile)
            .join(Profile, Profile.user_id == SavedCandidate.candidate_id)
            .where(SavedCandidate.employer_id == employer_id)
            .order_by(SavedCandidate.updated_at.desc())
        )
        rows = (await self._s.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]

    async def saved_candidate_ids(self, employer_id: str) -> set[str]:
        stmt = select(SavedCandidate.candidate_id).where(
            SavedCandidate.employer_id == employer_id
        )
        return set((await self._s.execute(stmt)).scalars().all())

    async def update(
        self, *, employer_id: str, candidate_id: str,
        stage: ShortlistStage | None, note: str | None,
    ) -> bool:
        values: dict[str, Any] = {}
        if stage is not None:
            values["stage"] = stage
        if note is not None:
            values["note"] = note
        if not values:
            return False
        stmt = (
            update(SavedCandidate)
            .where(
                SavedCandidate.employer_id == employer_id,
                SavedCandidate.candidate_id == candidate_id,
            )
            .values(**values)
            .returning(SavedCandidate.id)
        )
        ok = (await self._s.execute(stmt)).scalar_one_or_none() is not None
        await self._s.commit()
        return ok

    async def remove(self, *, employer_id: str, candidate_id: str) -> None:
        await self._s.execute(
            delete(SavedCandidate).where(
                SavedCandidate.employer_id == employer_id,
                SavedCandidate.candidate_id == candidate_id,
            )
        )
        await self._s.commit()

    async def funnel(self, employer_id: str) -> dict[str, int]:
        stmt = (
            select(SavedCandidate.stage, func.count(SavedCandidate.id))
            .where(SavedCandidate.employer_id == employer_id)
            .group_by(SavedCandidate.stage)
        )
        rows = (await self._s.execute(stmt)).all()
        return {str(stage): count for stage, count in rows}


class IntroMessageRepository:
    """The conversation thread inside an accepted intro."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, *, intro_id: str, sender: str, body: str) -> IntroMessage:
        msg = IntroMessage(intro_id=intro_id, sender=sender, body=body)
        self._s.add(msg)
        await self._s.commit()
        await self._s.refresh(msg)
        return msg

    async def list_for_intro(self, intro_id: str) -> list[IntroMessage]:
        stmt = (
            select(IntroMessage)
            .where(IntroMessage.intro_id == intro_id)
            .order_by(IntroMessage.id.asc())
        )
        return list((await self._s.execute(stmt)).scalars().all())
