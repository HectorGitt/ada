"""ORM models.

Run: one per paid session; holds inputs and the generated deliverables (rewritten CV,
job matches, interview questions, and scored answers). ProcessedEvent: idempotency
ledger for webhook events. Job: a listing ingested from an ATS/aggregator, embedded
for pgvector matching. User/AuthToken/Session: email+password authentication —
passwords are bcrypt-hashed, reset tokens are stored hashed and single-use, and
sessions are opaque tokens hashed at rest.
"""
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBED_DIM = 768  # text-embedding-004


class Base(DeclarativeBase):
    pass


class RunStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"  # created, awaiting a verified payment
    PAID = "paid"                        # payment confirmed, awaiting/undergoing dispatch
    RUNNING = "running"                  # agent graph in progress
    COMPLETE = "complete"                # deliverables stored
    FAILED = "failed"                    # graph raised; not retried automatically


class ProcessedEvent(Base):
    """A payment reference lands here exactly once — the idempotency guarantee."""
    __tablename__ = "processed_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    reference: Mapped[str] = mapped_column(String(128))
    __table_args__ = (UniqueConstraint("provider", "reference", name="uq_event"),)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    reference: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(32), default="paystack")
    amount: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="NGN")
    email: Mapped[str] = mapped_column(String(320))
    # Nullable: runs can be created (and paid for) without an account; linked when a
    # session exists at creation time.
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    target_role: Mapped[str] = mapped_column(String(256))
    cv_text: Mapped[str] = mapped_column(Text)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)

    # autonomous deliverables (filled by the graph run)
    rewritten_cv: Mapped[str | None] = mapped_column(Text, nullable=True)
    matches_json: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    questions_json: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    # scored interview (filled by the follow-up /interview endpoint)
    interview_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Stored as VARCHAR (not a native pg enum) so migrations stay simple and drift-free.
    status: Mapped[RunStatus] = mapped_column(
        String(20), default=RunStatus.PENDING_PAYMENT, index=True
    )
    # Graph node currently executing while RUNNING ("intake", "cv_rewrite",
    # "job_match", "interview_prep"); cleared on completion, kept on failure as a
    # diagnostic of where the run died.
    stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    """Listing ingested from an ATS/aggregator, deduped on (source, external_id)."""
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_jobs_source_external"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), default="seed")
    external_id: Mapped[str] = mapped_column(String(256), default=lambda: uuid.uuid4().hex)
    title: Mapped[str] = mapped_column(String(256))
    company: Mapped[str] = mapped_column(String(256))
    location: Mapped[str] = mapped_column(String(256))
    remote: Mapped[bool] = mapped_column(default=False)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set when an employer posts the role via Uche; NULL for ingested listings. Employer
    # postings share the pool, so they surface in candidate matching too.
    posted_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # "candidate" (default) uses Ada; "employer" uses Uche to hire.
    account_type: Mapped[str] = mapped_column(String(16), default="candidate")
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthToken(Base):
    """Single-use password-reset token. Only the sha256 hash is stored."""
    __tablename__ = "auth_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Session(Base):
    """Opaque browser session. Only the sha256 hash of the cookie token is stored."""
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Profile(Base):
    """Career profile imported by the user (LinkedIn export/paste). Grounds chat and runs.

    For discoverable candidates it doubles as the search record Uche ranks: `embedding`
    is the candidate vector and `insights` is Ada's structured analysis of them.
    """
    __tablename__ = "profiles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    profile_text: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Captured at onboarding; shown to employers on the shortlist and respected in matching.
    compensation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    work_pref: Mapped[str | None] = mapped_column(String(20), nullable=True)  # remote|hybrid|onsite
    # Identity attestation — half of the verification credential (the other half is a
    # proctored Assessment). method records how it was confirmed (attested|kyc provider).
    identity_verified: Mapped[bool] = mapped_column(default=False)
    identity_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Employer-discovery opt-in (the channel-conflict wall) + the search vector/analysis.
    discoverable: Mapped[bool] = mapped_column(default=False, index=True)
    headline: Mapped[str | None] = mapped_column(String(200), nullable=True)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    insights: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UploadedDocument(Base):
    """CV the user uploaded: extracted text for runs/preview, original archived in GCS."""
    __tablename__ = "uploaded_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(256))
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column()
    gcs_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    cv_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatTurn(Base):
    """One message in the user's rolling Ask Ada conversation."""
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserMemory(Base):
    """A durable fact Ada learned about the user (from chat), embedded for recall."""
    __tablename__ = "user_memories"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), default="chat")
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApplicationStatus(StrEnum):
    PREPARING = "preparing"
    SUBMITTED = "submitted"
    NEEDS_ATTENTION = "needs_attention"
    FAILED = "failed"


class Application(Base):
    """One submission attempt per user per job; only a detected confirmation is 'submitted'."""
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_application_user_job"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    status: Mapped[ApplicationStatus] = mapped_column(
        String(20), default=ApplicationStatus.PREPARING, index=True
    )
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"


class Subscription(Base):
    """A user's recurring plan. One row per user; provider webhooks drive its status.

    The recurring analogue of the one-off Run payment. Entitlements are derived from
    `tier` while `status == ACTIVE` (or PAST_DUE within grace); never trusted from the
    client. provider_ref is the Paystack subscription code / Stripe subscription id.
    """
    __tablename__ = "subscriptions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    tier: Mapped[str] = mapped_column(String(16), default="free")
    status: Mapped[SubscriptionStatus] = mapped_column(
        String(16), default=SubscriptionStatus.ACTIVE, index=True
    )
    cadence: Mapped[str] = mapped_column(String(16), default="monthly")
    provider: Mapped[str] = mapped_column(String(16), default="paystack")
    provider_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IntroStatus(StrEnum):
    REQUESTED = "requested"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class Intro(Base):
    """An employer reaching out to a discoverable candidate about a role — the
    reach-out and the demand signal the recruiter business is built on. One per
    (employer, candidate, job)."""
    __tablename__ = "intros"
    __table_args__ = (
        UniqueConstraint("employer_id", "candidate_id", "job_id", name="uq_intro"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    employer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    status: Mapped[IntroStatus] = mapped_column(
        String(16), default=IntroStatus.REQUESTED, index=True
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Notification(Base):
    """One in-app notification. Email/WhatsApp are best-effort side channels; this row
    is the durable record every user sees in their notification centre."""
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    # e.g. intro_request, intro_accepted, intro_declined, run_complete
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    read: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutcomeStage(StrEnum):
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    HIRED = "hired"
    REJECTED = "rejected"


class Outcome(Base):
    """A candidate's progress on one role — the hiring funnel that turns Ada's work into
    measurable results. Auto-seeded when Ada applies, advanced by the candidate. The data
    that makes the verification credential self-proving (verified → hired rates)."""
    __tablename__ = "outcomes"
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_outcome_user_job"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True)
    company: Mapped[str] = mapped_column(String(256))
    role_title: Mapped[str] = mapped_column(String(256))
    stage: Mapped[OutcomeStage] = mapped_column(
        String(16), default=OutcomeStage.APPLIED, index=True
    )
    source: Mapped[str] = mapped_column(String(16), default="one_click")  # one_click|intro|manual
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PushSubscription(Base):
    """A browser's Web Push endpoint + its encryption keys, so Ada can notify a closed tab.
    One row per device/browser; deduped on the endpoint URL."""
    __tablename__ = "push_subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    endpoint: Mapped[str] = mapped_column(String(1024), unique=True)
    p256dh: Mapped[str] = mapped_column(String(256))
    auth: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationPref(Base):
    """Per-user delivery preferences + a stable unsubscribe token. Defaults to all-on;
    the in-app centre is never suppressed — these gate the email/WhatsApp side channels."""
    __tablename__ = "notification_prefs"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    email_enabled: Mapped[bool] = mapped_column(default=True)
    whatsapp_enabled: Mapped[bool] = mapped_column(default=True)
    digest_enabled: Mapped[bool] = mapped_column(default=True)
    unsubscribe_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AssessmentStatus(StrEnum):
    PENDING = "pending"      # task issued, not yet submitted
    SUBMITTED = "submitted"  # answers in, awaiting scoring
    SCORED = "scored"        # graded — the credential is live


class AssessmentVerdict(StrEnum):
    VERIFIED = "verified"          # clean proctoring, credible score
    NEEDS_REVIEW = "needs_review"  # integrity flags — score shown but not trusted
    FAILED = "failed"              # below the bar


class Assessment(Base):
    """A proctored, role-specific skills assessment — the evidence half of the
    verification credential. Questions are issued server-side; answers arrive with
    integrity telemetry (tab-switches, blur, paste, duration) so the score means
    something to a skeptical employer. Scored independently of Ada's opinion."""
    __tablename__ = "assessments"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    skill: Mapped[str] = mapped_column(String(160))  # the role/skill assessed
    questions: Mapped[list[Any]] = mapped_column(JSONB)
    answers: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[AssessmentStatus] = mapped_column(
        String(16), default=AssessmentStatus.PENDING, index=True
    )
    verdict: Mapped[AssessmentVerdict | None] = mapped_column(String(16), nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)      # 0..100
    integrity: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)  # per-answer
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdminAudit(Base):
    """Trail of privileged admin actions — impersonation, subscription grants, deletions —
    for accountability. target_user_id is a plain string (not an FK) so the record survives
    the deletion it records."""
    __tablename__ = "admin_audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    admin_email: Mapped[str] = mapped_column(String(320), index=True)
    action: Mapped[str] = mapped_column(String(48), index=True)
    target_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CompanyProfile(Base):
    """An employer's identity — what candidates see when a company reaches out, and the
    public company page. One per employer user. Separate from the User.company string so it
    can hold the full profile (logo, about, the recruiter behind the intro)."""
    __tablename__ = "company_profiles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size: Mapped[str | None] = mapped_column(String(40), nullable=True)  # e.g. "11–50"
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    about: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # The human reaching out (v1: one recruiter per company; team seats come later).
    contact_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    contact_title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShortlistStage(StrEnum):
    SHORTLISTED = "shortlisted"
    CONTACTED = "contacted"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    HIRED = "hired"
    PASSED = "passed"


class SavedCandidate(Base):
    """An employer's talent pipeline — a candidate they've saved, moved through stages, and
    kept notes on. One row per (employer, candidate)."""
    __tablename__ = "saved_candidates"
    __table_args__ = (UniqueConstraint("employer_id", "candidate_id", name="uq_saved_candidate"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    employer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    stage: Mapped[ShortlistStage] = mapped_column(
        String(16), default=ShortlistStage.SHORTLISTED, index=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
