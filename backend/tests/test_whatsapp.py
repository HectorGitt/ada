import base64
import hashlib
import hmac
import os
import uuid

import pytest

from ada.services.whatsapp import parse_reply, phone_digits, verify_twilio_signature

_db = pytest.mark.skipif(not os.getenv("RUN_DB_TESTS"), reason="requires Postgres")


def test_parse_reply_reads_yes_and_no():
    for yes in ("yes", "YES", "y", "1", "Accept", "ok please", "sure thing", "connect"):
        assert parse_reply(yes) == "accept"
    for no in ("no", "N", "2", "decline", "pass", "stop", "no thanks"):
        assert parse_reply(no) == "decline"
    for other in ("", "maybe", "what?", "tell me more"):
        assert parse_reply(other) is None


def test_phone_digits_normalizes_to_trailing_national():
    assert phone_digits("whatsapp:+2348012345678") == "8012345678"
    assert phone_digits("+1 (415) 523-8886") == "4155238886"
    assert phone_digits("12345") == "12345"  # too short: returned as-is


def test_verify_twilio_signature_roundtrip():
    token = "s3cr3t-auth-token"
    url = "https://api.example.com/api/webhooks/whatsapp"
    params = {"From": "whatsapp:+2348012345678", "Body": "YES", "To": "whatsapp:+14155238886"}
    data = url + "".join(k + params[k] for k in sorted(params))
    good = base64.b64encode(
        hmac.new(token.encode(), data.encode(), hashlib.sha1).digest()
    ).decode()
    assert verify_twilio_signature(auth_token=token, url=url, params=params, signature=good)
    assert not verify_twilio_signature(
        auth_token=token, url=url, params=params, signature="tampered"
    )
    assert not verify_twilio_signature(
        auth_token="", url=url, params=params, signature=good
    )  # no creds → never trust


@_db
async def test_inbound_reply_accepts_latest_intro():
    """The WhatsApp path: match the sender's phone to a candidate, find their open intro,
    and accept it — idempotently."""
    from sqlalchemy import delete

    from ada.db.models import Intro, IntroStatus, Job, Profile, User
    from ada.db.repositories import IntroRepository, ProfileRepository
    from ada.db.session import _session_factory, init_db
    from ada.services.intros import respond_to_intro

    await init_db()
    emp, cand = uuid.uuid4().hex, uuid.uuid4().hex
    intro_id = uuid.uuid4().hex
    job_id: int | None = None
    try:
        async with _session_factory() as s:
            s.add(User(id=emp, email=f"{emp}@co.com", account_type="employer", company="Acme"))
            s.add(User(id=cand, email=f"{cand}@ex.com"))
            job = Job(source="test", external_id=uuid.uuid4().hex, title="Staff Engineer",
                      company="Acme", location="Remote", description="build")
            s.add(job)
            await s.commit()
            job_id = job.id
            s.add(Profile(user_id=cand, profile_text="cv", phone="+234 801 234 5678",
                          full_name="Ada Cand"))
            s.add(Intro(id=intro_id, employer_id=emp, candidate_id=cand, job_id=job_id,
                        message=None, status=IntroStatus.REQUESTED))
            await s.commit()

        # Lookup by inbound number → candidate.
        async with _session_factory() as s:
            profile = await ProfileRepository(s).by_phone(phone_digits("whatsapp:+2348012345678"))
            assert profile is not None and profile.user_id == cand
            intro = await IntroRepository(s).latest_requested_for_candidate(cand)
            assert intro is not None and intro.id == intro_id

        scheduled: list = []
        moved = await respond_to_intro(
            intro=intro, responder_id=cand, status=IntroStatus.ACCEPTED,
            schedule=lambda fn, *a, **k: scheduled.append(fn),
        )
        assert moved is True
        assert scheduled  # employer notify + connect_parties were queued

        async with _session_factory() as s:
            row = await s.get(Intro, intro_id)
            assert row is not None and row.status == IntroStatus.ACCEPTED
            # Already answered → a second reply is a no-op.
            again = await respond_to_intro(
                intro=row, responder_id=cand, status=IntroStatus.DECLINED,
                schedule=lambda fn, *a, **k: None,
            )
            assert again is False
    finally:
        async with _session_factory() as s:
            await s.execute(delete(Intro).where(Intro.candidate_id == cand))
            await s.execute(delete(Profile).where(Profile.user_id == cand))
            if job_id is not None:
                await s.execute(delete(Job).where(Job.id == job_id))
            await s.execute(delete(User).where(User.id.in_([emp, cand])))
            await s.commit()
