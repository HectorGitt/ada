"""Ingest adapters normalize captured sample payloads (no live HTTP) + DB dedup upsert."""
import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from ada.ingest import ashby, greenhouse, jooble, lever

_FIXTURES = Path(__file__).with_name("fixtures")

UNIFIED_KEYS = {
    "source", "external_id", "title", "company", "location",
    "remote", "url", "description", "posted_at",
}


def _load(name: str) -> dict | list:
    return json.loads((_FIXTURES / name).read_text())


def _assert_unified(listing: dict) -> None:
    assert set(listing) == UNIFIED_KEYS
    assert listing["title"] and listing["external_id"] and listing["company"]
    assert isinstance(listing["remote"], bool)
    assert listing["posted_at"] is None or isinstance(listing["posted_at"], datetime)
    # Descriptions must be plain text — no tags or escaped entities left behind.
    assert "<" not in listing["description"] and "&lt;" not in listing["description"]


def test_greenhouse_normalizes_sample():
    job = _load("greenhouse_sample.json")["jobs"][0]
    listing = greenhouse.normalize(job, "Acme")
    _assert_unified(listing)
    assert listing["source"] == "greenhouse"
    assert listing["external_id"] == "4455667788"
    assert listing["remote"] is True  # "Remote — EMEA"
    assert "payments" in listing["description"]
    assert listing["posted_at"] is not None and listing["posted_at"].tzinfo is not None


def test_lever_normalizes_sample():
    job = _load("lever_sample.json")[0]
    listing = lever.normalize(job, "Acme")
    _assert_unified(listing)
    assert listing["source"] == "lever"
    assert listing["location"] == "Lagos, Nigeria"
    assert listing["remote"] is True  # workplaceType=remote
    assert listing["posted_at"] is not None
    assert listing["posted_at"].year == 2025  # 1751328000000 ms epoch


def test_ashby_normalizes_sample():
    job = _load("ashby_sample.json")["jobs"][0]
    listing = ashby.normalize(job, "Acme")
    _assert_unified(listing)
    assert listing["source"] == "ashby"
    assert listing["remote"] is True
    assert listing["url"] == "https://jobs.ashbyhq.com/acme/f0e1d2c3"


def test_jooble_normalizes_sample():
    job = _load("jooble_sample.json")["jobs"][0]
    listing = jooble.normalize(job, "ng.jooble.org")
    _assert_unified(listing)
    assert listing["source"] == "jooble"
    assert listing["company"] == "PayNaija Ltd"
    # Ids are only unique within one country feed, so the key is host-qualified.
    assert listing["external_id"] == "ng.jooble.org:9876543210"
    assert "Python" in listing["description"] and "<b>" not in listing["description"]


def test_normalize_bounds_overlong_fields():
    job = _load("greenhouse_sample.json")["jobs"][0]
    job = {**job, "title": "Engineer, " * 60, "location": {"name": "Lagos / " * 80}}
    listing = greenhouse.normalize(job, "Acme")
    assert len(listing["title"]) <= 256
    assert len(listing["location"]) <= 256


def test_jooble_missing_id_derives_stable_key():
    job = _load("jooble_sample.json")["jobs"][0]
    job = {**job, "id": None}
    first = jooble.normalize(job, "jooble.org")["external_id"]
    second = jooble.normalize(job, "jooble.org")["external_id"]
    assert first == second  # link-derived, deterministic
    assert first.startswith("jooble.org:")


_db = pytest.mark.skipif(not os.getenv("RUN_DB_TESTS"), reason="requires Postgres")


@_db
async def test_upsert_dedups_on_source_external_id():
    from sqlalchemy import delete

    from ada.db.models import Job
    from ada.db.repositories import JobRepository
    from ada.db.session import _session_factory, init_db

    await init_db()
    listing = greenhouse.normalize(_load("greenhouse_sample.json")["jobs"][0], "Acme")
    listing["external_id"] = f"test-{os.urandom(6).hex()}"
    async with _session_factory() as s:
        repo = JobRepository(s)
        before = await repo.count()
        try:
            # The same listing twice in one batch (overlapping queries) must not
            # abort the INSERT — Postgres rejects double-updating a row per statement.
            await repo.upsert_many([listing, {**listing, "title": "Backend Engineer"}])
            await repo.upsert_many([{**listing, "title": "Backend Engineer II"}])
            assert await repo.count() == before + 1
        finally:
            await s.execute(
                delete(Job).where(
                    Job.source == listing["source"], Job.external_id == listing["external_id"]
                )
            )
            await s.commit()
