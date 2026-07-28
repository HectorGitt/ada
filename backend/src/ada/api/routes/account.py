"""Account type switch — a user is a candidate (Ada) or an employer (Uche).

Kept intentionally simple: one person can flip to hiring mode and back. Employer mode
just needs a company name; nothing destructive happens to their candidate data.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ada.auth.dependencies import current_user
from ada.db.models import User
from ada.db.repositories import UserRepository
from ada.db.session import get_session

router = APIRouter(prefix="/account", tags=["account"])


class AccountIn(BaseModel):
    account_type: str = Field(pattern="^(candidate|employer)$")
    company: str | None = Field(default=None, max_length=200)


@router.put("")
async def set_account(
    body: AccountIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
) -> dict[str, str | None]:
    if body.account_type == "employer" and not (body.company or "").strip():
        raise HTTPException(422, "A company name is required for employer accounts.")
    await UserRepository(session).set_account(
        user.id, account_type=body.account_type, company=(body.company or "").strip() or None
    )
    return {"account_type": body.account_type, "company": body.company}
