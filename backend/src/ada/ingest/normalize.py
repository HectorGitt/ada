"""Shared normalization helpers for ingest adapters.

Every adapter maps its source's payload to ONE unified listing dict:
{source, external_id, title, company, location, remote, url, description, posted_at}
"""
import html
import re
from datetime import UTC, datetime

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\n{3,}|\r")

MAX_DESCRIPTION = 20_000

_BOUNDS = {"external_id": 256, "title": 256, "company": 256, "location": 256, "url": 1024}


def bounded(listing: dict) -> dict:
    for field, limit in _BOUNDS.items():
        value = listing.get(field)
        if isinstance(value, str) and len(value) > limit:
            listing[field] = value[:limit]
    return listing


def strip_html(raw: str) -> str:
    text = html.unescape(raw)
    text = _TAG.sub(" ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return _WS.sub("\n\n", text).strip()[:MAX_DESCRIPTION]


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def parse_epoch_ms(value: int | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def looks_remote(location: str) -> bool:
    return "remote" in location.lower()
