"""Greenhouse job-board API: GET boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"""
from typing import Any

import httpx

SOURCE = "greenhouse"
_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def normalize(job: dict[str, Any], company: str) -> dict[str, Any]:
    from ada.ingest.normalize import bounded, looks_remote, parse_iso, strip_html

    location = (job.get("location") or {}).get("name", "") or "Unspecified"
    return bounded({
        "source": SOURCE,
        "external_id": str(job["id"]),
        "title": job.get("title", "").strip(),
        "company": company,
        "location": location,
        "remote": looks_remote(location),
        "url": job.get("absolute_url"),
        "description": strip_html(job.get("content") or ""),
        "posted_at": parse_iso(job.get("first_published") or job.get("updated_at")),
    })


async def fetch(client: httpx.AsyncClient, token: str, company: str) -> list[dict[str, Any]]:
    resp = await client.get(_URL.format(token=token), params={"content": "true"})
    resp.raise_for_status()
    return [normalize(j, company) for j in resp.json().get("jobs", [])]
