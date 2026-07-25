"""Jooble aggregator API (the Nigeria/local source): POST jooble.org/api/{key}

The only keyed source. The pipeline skips it with a log when JOOBLE_API_KEY is
unset, so local dev runs without an account.
"""
import hashlib
from typing import Any

import httpx

SOURCE = "jooble"
_URL = "https://{host}/api/{key}"


def normalize(job: dict[str, Any], host: str) -> dict[str, Any]:
    from ada.ingest.normalize import bounded, looks_remote, parse_iso, strip_html

    location = job.get("location") or "Unspecified"
    link_key = hashlib.sha256((job.get("link") or "").encode()).hexdigest()[:32]
    external_id = f"{host}:{job.get('id') or link_key}"
    return bounded({
        "source": SOURCE,
        "external_id": external_id,
        "title": job.get("title", "").strip(),
        "company": job.get("company") or "Unspecified",
        "location": location,
        "remote": looks_remote(location),
        "url": job.get("link"),
        "description": strip_html(job.get("snippet") or ""),
        "posted_at": parse_iso(job.get("updated")),
    })


async def fetch(
    client: httpx.AsyncClient, host: str, api_key: str, keywords: str, location: str
) -> list[dict[str, Any]]:
    resp = await client.post(
        _URL.format(host=host, key=api_key),
        json={"keywords": keywords, "location": location},
    )
    resp.raise_for_status()
    return [normalize(j, host) for j in resp.json().get("jobs", [])]
