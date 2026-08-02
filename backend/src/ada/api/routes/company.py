"""Public company page — no auth. A candidate who gets an intro can look up who's reaching
out (logo, about, open roles) before accepting. Exposes only the company's own public
fields, never anything private."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ada.db.repositories import CompanyRepository, JobRepository
from ada.db.session import get_session

router = APIRouter(tags=["company"])


@router.get("/company/{company_id}")
async def public_company(
    company_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    c = await CompanyRepository(session).get(company_id)
    if c is None:
        raise HTTPException(404, "Company not found.")
    roles = await JobRepository(session).list_by_poster(company_id)
    return {
        "name": c.name,
        "website": c.website,
        "industry": c.industry,
        "size": c.size,
        "location": c.location,
        "about": c.about,
        "logo_url": c.logo_url,
        "roles": [
            {"id": j.id, "title": j.title, "location": j.location, "remote": j.remote}
            for j in roles
        ],
    }
