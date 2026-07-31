"""Outcome tracking — the candidate's hiring funnel.

Auto-seeded when Ada applies (see services/apply), advanced by the candidate as things
progress: applied → interviewing → offer → hired (or rejected). This is what turns Ada's
work into a measurable result and, over time, proves the verification credential
(verified candidates' interview/offer/hire rates).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_user
from ada.db.models import Outcome, OutcomeStage, User
from ada.db.repositories import OutcomeRepository
from ada.db.session import get_session

router = APIRouter(tags=["outcomes"])


class OutcomeOut(BaseModel):
    id: str
    company: str
    role_title: str
    stage: str
    source: str
    updated_at: str


class PipelineOut(BaseModel):
    outcomes: list[OutcomeOut]
    funnel: dict[str, int]


class OutcomeIn(BaseModel):
    company: str = Field(min_length=1, max_length=256)
    role_title: str = Field(min_length=1, max_length=256)
    stage: OutcomeStage = OutcomeStage.APPLIED


class StageIn(BaseModel):
    stage: OutcomeStage


def _out(o: Outcome) -> OutcomeOut:
    return OutcomeOut(
        id=o.id, company=o.company, role_title=o.role_title,
        stage=str(o.stage), source=o.source, updated_at=o.updated_at.isoformat(),
    )


@router.get("/outcomes", response_model=PipelineOut)
async def list_outcomes(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> PipelineOut:
    repo = OutcomeRepository(session)
    rows = await repo.list_by_user(user.id)
    return PipelineOut(outcomes=[_out(o) for o in rows], funnel=await repo.funnel(user.id))


@router.post("/outcomes", response_model=OutcomeOut, status_code=201)
async def add_outcome(
    body: OutcomeIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> OutcomeOut:
    """Track a role the candidate is pursuing outside Ada's one-click apply."""
    outcome = await OutcomeRepository(session).create_manual(
        user_id=user.id, company=body.company, role_title=body.role_title, stage=body.stage
    )
    return _out(outcome)


@router.put("/outcomes/{outcome_id}", response_model=OutcomeOut)
async def advance_outcome(
    outcome_id: str,
    body: StageIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> OutcomeOut:
    outcome = await OutcomeRepository(session).set_stage(
        outcome_id=outcome_id, user_id=user.id, stage=body.stage
    )
    if outcome is None:
        raise HTTPException(404, "No such outcome.")
    return _out(outcome)
