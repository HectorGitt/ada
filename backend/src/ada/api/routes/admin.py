"""Admin dashboard API — gated by the ADMIN_EMAILS allowlist (see auth.admin).

Everything here is privileged: comping subscriptions, impersonation, deletions, ops
triggers. Mutating actions are recorded in the admin audit log so there's always a trail.
"""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ada.api.routes.auth import _set_session_cookie
from ada.auth.admin import require_admin
from ada.auth.repository import AuthRepository
from ada.auth.tokens import mint
from ada.config import get_settings
from ada.db.models import User
from ada.db.repositories import (
    AdminRepository,
    AssessmentRepository,
    ProfileRepository,
    SubscriptionRepository,
)
from ada.db.session import get_session
from ada.services import entitlements
from ada.services.notify import notify

router = APIRouter(prefix="/admin", tags=["admin"])

_CANDIDATE_TIERS = set(entitlements.TIERS)          # free, pro, premium
_EMPLOYER_TIERS = set(entitlements.EMPLOYER_TIERS)  # pilot, growth, scale
_GRANTABLE = (_CANDIDATE_TIERS | _EMPLOYER_TIERS) - {"free"}


def _user_row(user: User, sub: object | None) -> dict:
    tier = getattr(sub, "tier", None) if sub else None
    status = str(getattr(sub, "status", "")) if sub else None
    return {
        "id": user.id,
        "email": user.email,
        "account_type": user.account_type,
        "company": user.company,
        "created_at": user.created_at.isoformat(),
        "subscription": {"tier": tier, "status": status} if sub else None,
    }


@router.get("/me")
async def admin_me(admin: User = Depends(require_admin)) -> dict:
    return {"email": admin.email, "admin": True}


@router.get("/overview")
async def overview(
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
) -> dict:
    return await AdminRepository(session).overview()


@router.get("/users")
async def list_users(
    q: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
) -> list[dict]:
    rows = await AdminRepository(session).list_users(q=q, limit=limit, offset=offset)
    return [_user_row(u, s) for u, s in rows]


@router.get("/users/{user_id}")
async def user_detail(
    user_id: str,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
) -> dict:
    repo = AdminRepository(session)
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found.")
    sub = await SubscriptionRepository(session).get(user_id)
    profile = await ProfileRepository(session).get(user_id)
    assessment = await AssessmentRepository(session).latest_scored(user_id)
    ent = entitlements.resolve(sub)
    return {
        **_user_row(user, sub),
        "is_admin": user.email.lower() in get_settings().admin_email_set,
        "entitlement": {
            "tier": ent.tier, "included_runs": ent.included_runs,
            "can_apply": ent.can_apply, "can_voice": ent.can_voice,
        },
        "profile": {
            "full_name": profile.full_name if profile else None,
            "phone": profile.phone if profile else None,
            "headline": profile.headline if profile else None,
            "identity_verified": bool(profile and profile.identity_verified),
            "discoverable": bool(profile and profile.discoverable),
        } if profile else None,
        "credential": {
            "skill": assessment.skill, "score": assessment.score,
            "verdict": str(assessment.verdict) if assessment.verdict else None,
        } if assessment else None,
        "counts": await repo.user_counts(user_id),
    }


class AccountTypeIn(BaseModel):
    account_type: str = Field(pattern="^(candidate|employer)$")


@router.put("/users/{user_id}/account-type")
async def set_account_type(
    user_id: str,
    body: AccountTypeIn,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
) -> dict:
    repo = AdminRepository(session)
    if not await repo.set_account_type(user_id, body.account_type):
        raise HTTPException(404, "User not found.")
    await repo.record_audit(
        admin_email=admin.email, action="set_account_type",
        target_user_id=user_id, detail={"account_type": body.account_type},
    )
    return {"ok": True}


class GrantIn(BaseModel):
    tier: str
    cadence: str = Field(default="monthly", pattern="^(monthly|annual)$")
    days: int = Field(default=30, ge=1, le=3650)


@router.post("/users/{user_id}/subscription")
async def grant_subscription(
    user_id: str,
    body: GrantIn,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
) -> dict:
    """Comp a plan — the 'give someone premium' button. Recorded as a provider='comp'
    subscription so it's distinguishable from a paid one, with an expiry."""
    if body.tier not in _GRANTABLE:
        raise HTTPException(422, f"Tier must be one of: {', '.join(sorted(_GRANTABLE))}.")
    if await session.get(User, user_id) is None:
        raise HTTPException(404, "User not found.")
    until = datetime.now(UTC) + timedelta(days=body.days)
    await SubscriptionRepository(session).activate(
        user_id=user_id, tier=body.tier, cadence=body.cadence,
        provider="comp", provider_ref=f"comp:{admin.email}", current_period_end=until,
    )
    await AdminRepository(session).record_audit(
        admin_email=admin.email, action="grant_subscription", target_user_id=user_id,
        detail={"tier": body.tier, "cadence": body.cadence, "until": until.isoformat()},
    )
    return {"ok": True, "tier": body.tier, "until": until.isoformat()}


@router.delete("/users/{user_id}/subscription")
async def revoke_subscription(
    user_id: str,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
) -> dict:
    repo = AdminRepository(session)
    await repo.revoke_subscription(user_id)
    await repo.record_audit(
        admin_email=admin.email, action="revoke_subscription", target_user_id=user_id,
    )
    return {"ok": True}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
) -> dict:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found.")
    if user.email.lower() in get_settings().admin_email_set:
        raise HTTPException(403, "Refusing to delete an admin account.")
    repo = AdminRepository(session)
    await repo.record_audit(
        admin_email=admin.email, action="delete_user", target_user_id=user_id,
        detail={"email": user.email},
    )
    await repo.delete_user(user_id)
    return {"ok": True}


@router.post("/users/{user_id}/impersonate")
async def impersonate(
    user_id: str,
    response: Response,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
) -> dict:
    """Mint a session as the target user and set it on this browser — support/debugging.
    Logged every time. Sign out and back in to return to the admin account."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found.")
    raw, token_hash = mint()
    await AuthRepository(session).create_session(user_id, token_hash)
    _set_session_cookie(response, raw)
    await AdminRepository(session).record_audit(
        admin_email=admin.email, action="impersonate", target_user_id=user_id,
        detail={"email": user.email},
    )
    return {"ok": True, "impersonating": user.email}


@router.get("/runs")
async def list_runs(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
) -> list[dict]:
    runs = await AdminRepository(session).list_runs(status=status, limit=limit, offset=offset)
    return [
        {
            "id": r.id, "user_id": r.user_id, "target_role": r.target_role,
            "status": str(r.status), "amount": r.amount, "currency": r.currency,
            "created_at": r.created_at.isoformat(),
        }
        for r in runs
    ]


@router.post("/runs/{run_id}/redispatch")
async def redispatch_run(
    run_id: str,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
) -> dict:
    """Re-enqueue a paid run whose in-process dispatch was lost."""
    from ada.services.runs import execute_run

    background.add_task(execute_run, run_id)
    await AdminRepository(session).record_audit(
        admin_email=admin.email, action="redispatch_run", detail={"run_id": run_id},
    )
    return {"ok": True}


@router.get("/events")
async def list_events(
    limit: int = Query(default=100, le=500),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
) -> list[dict]:
    events = await AdminRepository(session).list_events(limit=limit)
    return [{"id": e.id, "provider": e.provider, "reference": e.reference} for e in events]


@router.post("/jobs/ingest")
async def trigger_ingest(
    background: BackgroundTasks,
    limit: int | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
) -> dict:
    from ada.ingest.pipeline import run as ingest_run

    background.add_task(ingest_run, limit)
    await AdminRepository(session).record_audit(
        admin_email=admin.email, action="trigger_ingest", detail={"limit": limit},
    )
    return {"ok": True, "message": "Ingestion started in the background."}


@router.post("/jobs/embed")
async def trigger_embed(
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
) -> dict:
    from ada.ingest.pipeline import backfill_embeddings

    background.add_task(backfill_embeddings)
    await AdminRepository(session).record_audit(
        admin_email=admin.email, action="trigger_embed",
    )
    return {"ok": True, "message": "Embedding backfill started in the background."}


class BroadcastIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    body: str = Field(min_length=2, max_length=1000)
    link: str | None = Field(default=None, max_length=512)
    account_type: str | None = Field(default=None, pattern="^(candidate|employer)$")


async def _broadcast(user_ids: list[str], *, title: str, body: str, link: str | None) -> None:
    for uid in user_ids:
        await notify(uid, kind="announcement", title=title, body=body, link=link)


@router.post("/broadcast")
async def broadcast(
    body: BroadcastIn,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
) -> dict:
    """Send an in-app (+ email/WhatsApp per each user's prefs) announcement to a segment."""
    repo = AdminRepository(session)
    user_ids = await repo.all_user_ids(account_type=body.account_type)
    background.add_task(
        _broadcast, user_ids, title=body.title, body=body.body, link=body.link
    )
    await repo.record_audit(
        admin_email=admin.email, action="broadcast",
        detail={"count": len(user_ids), "account_type": body.account_type, "title": body.title},
    )
    return {"ok": True, "recipients": len(user_ids)}


@router.get("/audit")
async def audit_log(
    limit: int = Query(default=100, le=500),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
) -> list[dict]:
    rows = await AdminRepository(session).list_audit(limit=limit)
    return [
        {
            "id": a.id, "admin_email": a.admin_email, "action": a.action,
            "target_user_id": a.target_user_id, "detail": a.detail,
            "created_at": a.created_at.isoformat(),
        }
        for a in rows
    ]
