"""Lever postings API: GET api.lever.co/v0/postings/{company}?mode=json"""
from typing import Any

import httpx

SOURCE = "lever"
_URL = "https://api.lever.co/v0/postings/{company}"


def normalize(job: dict[str, Any], company: str) -> dict[str, Any]:
    from ada.ingest.normalize import bounded, looks_remote, parse_epoch_ms, strip_html

    categories = job.get("categories") or {}
    location = categories.get("location") or "Unspecified"
    remote = job.get("workplaceType") == "remote" or looks_remote(location)
    description = job.get("descriptionPlain") or strip_html(job.get("description") or "")
    return bounded({
        "source": SOURCE,
        "external_id": str(job["id"]),
        "title": job.get("text", "").strip(),
        "company": company,
        "location": location,
        "remote": remote,
        "url": job.get("hostedUrl"),
        "description": description[:20_000],
        "posted_at": parse_epoch_ms(job.get("createdAt")),
    })


async def fetch(client: httpx.AsyncClient, slug: str, company: str) -> list[dict[str, Any]]:
    resp = await client.get(_URL.format(company=slug), params={"mode": "json"})
    resp.raise_for_status()
    return [normalize(j, company) for j in resp.json()]
