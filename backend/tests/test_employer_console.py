import os
import uuid

import pytest

_db = pytest.mark.skipif(not os.getenv("RUN_DB_TESTS"), reason="requires Postgres")


@_db
async def test_company_profile_and_shortlist_pipeline():
    from sqlalchemy import delete

    from ada.db.models import CompanyProfile, Profile, SavedCandidate, ShortlistStage, User
    from ada.db.repositories import (
        CompanyRepository,
        ProfileRepository,
        ShortlistRepository,
    )
    from ada.db.session import _session_factory, init_db

    await init_db()
    emp = uuid.uuid4().hex
    cands = [uuid.uuid4().hex for _ in range(2)]
    try:
        async with _session_factory() as s:
            s.add(User(id=emp, email=f"{emp}@co.com", account_type="employer"))
            for c in cands:
                s.add(User(id=c, email=f"{c}@ex.com"))
            await s.commit()
            # Two discoverable candidates; one identity-verified, in Lagos.
            s.add(Profile(user_id=cands[0], profile_text="Senior backend engineer, Python",
                          headline="Backend Engineer", location="Lagos", discoverable=True,
                          identity_verified=True, insights={"seniority": "senior"}))
            s.add(Profile(user_id=cands[1], profile_text="Junior designer", headline="Designer",
                          location="Abuja", discoverable=True, identity_verified=False))
            await s.commit()

        async with _session_factory() as s:
            # Company profile upsert + read.
            company = await CompanyRepository(s).upsert(
                emp, {"name": "Acme Inc", "website": "https://acme.co", "industry": "Fintech",
                      "size": "11–50", "location": "Lagos", "about": "We build things.",
                      "logo_url": None, "contact_name": "Ada R.", "contact_title": "Head of Talent"}
            )
            assert company.name == "Acme Inc" and company.contact_name == "Ada R."

            # Talent search: verified filter narrows to the one verified candidate.
            profiles = ProfileRepository(s)
            all_hits = await profiles.search_talent(
                q=None, location=None, seniority=None, verified_only=False, exclude=emp, limit=50
            )
            assert {p.user_id for p in all_hits} == set(cands)
            verified = await profiles.search_talent(
                q=None, location=None, seniority=None, verified_only=True, exclude=emp, limit=50
            )
            assert [p.user_id for p in verified] == [cands[0]]
            # Location + seniority filters.
            lagos_senior = await profiles.search_talent(
                q=None, location="lagos", seniority="senior", verified_only=False,
                exclude=emp, limit=50
            )
            assert [p.user_id for p in lagos_senior] == [cands[0]]

            # Shortlist: save (idempotent), advance a stage, funnel counts, remove.
            sl = ShortlistRepository(s)
            await sl.save(entry_id=uuid.uuid4().hex, employer_id=emp, candidate_id=cands[0],
                          job_id=None, note="Strong")
            await sl.save(entry_id=uuid.uuid4().hex, employer_id=emp, candidate_id=cands[0],
                          job_id=None, note="dup")  # idempotent — no second row
            assert len(await sl.list_for_employer(emp)) == 1
            assert await sl.update(employer_id=emp, candidate_id=cands[0],
                                   stage=ShortlistStage.HIRED, note=None) is True
            assert (await sl.funnel(emp)).get("hired") == 1
            assert cands[0] in await sl.saved_candidate_ids(emp)
            await sl.remove(employer_id=emp, candidate_id=cands[0])
            assert await sl.list_for_employer(emp) == []
    finally:
        async with _session_factory() as s:
            await s.execute(delete(SavedCandidate).where(SavedCandidate.employer_id == emp))
            await s.execute(delete(CompanyProfile).where(CompanyProfile.user_id == emp))
            await s.execute(delete(Profile).where(Profile.user_id.in_(cands)))
            await s.execute(delete(User).where(User.id.in_([emp, *cands])))
            await s.commit()
