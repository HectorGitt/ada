"""Create a pending run (pre-payment), list/read runs, score the interview.

Create returns provider-specific payment init:
  - paystack -> public_key + reference + amount (inline checkout on the client)
  - stripe   -> a hosted checkout_url to redirect to
Neither path runs the agent; only the payment webhook does.

Access control: a run owned by a user is visible only to that user; unowned runs
(created without a session) are addressable by their unguessable id.
"""
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_user, optional_user
from ada.auth.tokens import hash_token, mint
from ada.config import get_settings
from ada.db.models import Run, RunStatus, User
from ada.db.repositories import RunRepository, SubscriptionRepository
from ada.db.session import get_session
from ada.payments.stripe import create_checkout
from ada.services import entitlements
from ada.services.interview import InterviewService
from ada.services.runs import create_pending_run, execute_run

router = APIRouter(prefix="/runs", tags=["runs"])


class CreateRunIn(BaseModel):
    email: EmailStr
    target_role: str = Field(min_length=2, max_length=256)
    cv_text: str = Field(min_length=30, max_length=30_000)
    provider: Literal["paystack", "stripe"] = "paystack"
    transcript: str | None = Field(default=None, max_length=60_000)


class CreateRunOut(BaseModel):
    run_id: str
    reference: str
    provider: str
    # paystack (inline)
    public_key: str | None = None
    amount: int | None = None
    currency: str | None = None
    # stripe (redirect)
    checkout_url: str | None = None
    # true when the subscription covered the run — no payment needed, already dispatched
    entitled: bool = False
    # one-time access token for a guest (unowned) run — the client must send it as
    # X-Run-Token to read the run later. None for owned runs (authorized by session).
    access_token: str | None = None


class RunSummaryOut(BaseModel):
    run_id: str
    target_role: str
    status: str
    created_at: str
    has_interview: bool


class RunResultOut(BaseModel):
    status: str
    # Graph node currently executing while RUNNING; None otherwise. Lets the UI
    # show real progress instead of a client-side guess.
    stage: str | None = None
    target_role: str
    rewritten_cv: str | None = None
    matches: list[dict] | None = None
    questions: list[str] | None = None
    interview: dict | None = None


class InterviewIn(BaseModel):
    answers: list[str] = Field(min_length=1, max_length=20)


def _authorize(run: Run, user: User | None, run_token: str | None = None) -> None:
    """Owned runs: session owner only. Guest (unowned) runs: a valid access token AND within
    the guest TTL — the run id alone is never sufficient. All failures 404 (never confirm a
    run exists to someone not authorized for it)."""
    if run.user_id is not None:
        if user is None or user.id != run.user_id:
            raise HTTPException(status_code=404, detail="run not found")
        return
    # Guest run.
    if run.access_token_hash is None or run_token is None:
        raise HTTPException(status_code=404, detail="run not found")
    if hash_token(run_token) != run.access_token_hash:
        raise HTTPException(status_code=404, detail="run not found")
    created = run.created_at if run.created_at.tzinfo else run.created_at.replace(tzinfo=UTC)
    if datetime.now(UTC) - created > timedelta(days=get_settings().guest_run_ttl_days):
        raise HTTPException(status_code=404, detail="run not found")


@router.post("", response_model=CreateRunOut)
async def create_run(
    body: CreateRunIn,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_user),
) -> CreateRunOut:
    s = get_settings()
    amount = s.price_kobo if body.provider == "paystack" else s.stripe_price_usd_cents
    currency = s.currency if body.provider == "paystack" else "USD"
    runs = RunRepository(session)
    # Guest (unowned) runs get a one-time access token; owned runs rely on the session.
    raw_token, token_hash = mint() if user is None else (None, None)

    # Payments kill-switch (e2e testing): treat every run as covered — no
    # checkout, straight to PAID and execution. Same contract as entitled runs,
    # so the frontend needs no special handling.
    if not s.payments_enabled:
        run = await create_pending_run(
            session_runs=runs, provider=body.provider, amount=0, currency=currency,
            email=body.email, target_role=body.target_role, cv_text=body.cv_text,
            transcript=body.transcript, user_id=user.id if user else None,
            access_token_hash=token_hash,
        )
        await runs.set_status(run, RunStatus.PAID)
        background.add_task(execute_run, run.id)
        return CreateRunOut(
            run_id=run.id, reference=run.reference, provider=body.provider, entitled=True,
            access_token=raw_token,
        )

    # A subscriber's plan covers the run: skip payment, mark PAID, dispatch now.
    if user is not None:
        subscription = await SubscriptionRepository(session).get(user.id)
        if entitlements.resolve(subscription).included_runs:
            run = await create_pending_run(
                session_runs=runs, provider=body.provider, amount=0, currency=currency,
                email=body.email, target_role=body.target_role, cv_text=body.cv_text,
                transcript=body.transcript, user_id=user.id,
            )
            await runs.set_status(run, RunStatus.PAID)
            background.add_task(execute_run, run.id)
            return CreateRunOut(
                run_id=run.id, reference=run.reference, provider=body.provider, entitled=True
            )

    run = await create_pending_run(
        session_runs=runs, provider=body.provider,
        amount=amount, currency=currency, email=body.email,
        target_role=body.target_role, cv_text=body.cv_text, transcript=body.transcript,
        user_id=user.id if user else None, access_token_hash=token_hash,
    )
    out = CreateRunOut(
        run_id=run.id, reference=run.reference, provider=body.provider, access_token=raw_token,
    )
    if body.provider == "paystack":
        out.public_key, out.amount, out.currency = s.paystack_public_key, amount, currency
    else:
        out.checkout_url = await run_in_threadpool(create_checkout, run)
    return out


@router.get("", response_model=list[RunSummaryOut])
async def list_runs(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> list[RunSummaryOut]:
    runs = await RunRepository(session).list_by_user(user.id)
    return [
        RunSummaryOut(
            run_id=r.id, target_role=r.target_role, status=r.status,
            created_at=r.created_at.isoformat(), has_interview=r.interview_json is not None,
        )
        for r in runs
    ]


@router.get("/{run_id}", response_model=RunResultOut)
async def get_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_user),
    x_run_token: str | None = Header(default=None),
) -> RunResultOut:
    run = await RunRepository(session).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    _authorize(run, user, x_run_token)
    return RunResultOut(
        status=run.status, stage=run.stage, target_role=run.target_role,
        rewritten_cv=run.rewritten_cv, matches=run.matches_json,
        questions=run.questions_json, interview=run.interview_json,
    )


class CheckoutOut(BaseModel):
    provider: str
    reference: str
    amount: int
    currency: str
    email: str
    public_key: str | None = None   # paystack (inline)
    checkout_url: str | None = None  # stripe (redirect)


@router.get("/{run_id}/checkout", response_model=CheckoutOut)
async def run_checkout(
    run_id: str,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_user),
    x_run_token: str | None = Header(default=None),
) -> CheckoutOut:
    """Authoritative checkout data for a run, fetched by the client instead of trusting
    navigation params — a deep link can't spoof the amount/reference/recipient. Owner- (or
    guest-token-) gated; only meaningful while the run still awaits payment."""
    run = await RunRepository(session).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    _authorize(run, user, x_run_token)
    if run.status != RunStatus.PENDING_PAYMENT:
        raise HTTPException(status_code=409, detail="run is not awaiting payment")
    s = get_settings()
    out = CheckoutOut(
        provider=run.provider, reference=run.reference, amount=run.amount,
        currency=run.currency, email=run.email,
    )
    if run.provider == "paystack":
        out.public_key = s.paystack_public_key
    else:
        out.checkout_url = await run_in_threadpool(create_checkout, run)
    return out


@router.post("/{run_id}/interview")
async def score_interview(
    run_id: str,
    body: InterviewIn,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_user),
    x_run_token: str | None = Header(default=None),
) -> dict[str, Any]:
    runs = RunRepository(session)
    run = await runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    _authorize(run, user, x_run_token)
    if run.status != RunStatus.COMPLETE or not run.questions_json:
        raise HTTPException(status_code=409, detail="run not ready for interview")
    if len(body.answers) != len(run.questions_json):
        raise HTTPException(
            status_code=400,
            detail=f"expected {len(run.questions_json)} answers, got {len(body.answers)}",
        )
    result = await InterviewService().score(
        target_role=run.target_role, questions=run.questions_json, answers=body.answers,
    )
    await runs.set_interview(run, result)
    return result
