"""Ashby job-board API: GET api.ashbyhq.com/posting-api/job-board/{name}"""
from typing import Any

import httpx

SOURCE = "ashby"
_URL = "https://api.ashbyhq.com/posting-api/job-board/{name}"


def normalize(job: dict[str, Any], company: str) -> dict[str, Any]:
    from ada.ingest.normalize import bounded, looks_remote, parse_iso, strip_html

    location = job.get("location") or "Unspecified"
    description = job.get("descriptionPlain") or strip_html(job.get("descriptionHtml") or "")
    return bounded({
        "source": SOURCE,
        "external_id": str(job["id"]),
        "title": job.get("title", "").strip(),
        "company": company,
        "location": location,
        "remote": bool(job.get("isRemote")) or looks_remote(location),
        "url": job.get("jobUrl") or job.get("applyUrl"),
        "description": description[:20_000],
        "posted_at": parse_iso(job.get("publishedAt")),
    })


async def fetch(client: httpx.AsyncClient, name: str, company: str) -> list[dict[str, Any]]:
    resp = await client.get(_URL.format(name=name), params={"includeCompensation": "true"})
    resp.raise_for_status()
    return [normalize(j, company) for j in resp.json().get("jobs", [])]
