"""Free CV assessment — public, no auth, rate-limited by IP.

The top-of-funnel: paste a CV, get a score + three specific fixes + a nudge into the
paid rewrite. Rate-limited because it's free and calls the model. The limiter is
in-process (fine for a single instance); a multi-instance deploy should front this with
a shared store (Redis) or an API-gateway rate limit.
"""
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ada.config import get_settings
from ada.services.assess import assess_cv

router = APIRouter(tags=["assess"])

_hits: dict[str, list[float]] = {}


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limited(ip: str, *, limit: int, window: int) -> bool:
    now = time.monotonic()
    recent = [t for t in _hits.get(ip, []) if now - t < window]
    if len(recent) >= limit:
        _hits[ip] = recent
        return True
    recent.append(now)
    _hits[ip] = recent
    return False


class AssessIn(BaseModel):
    cv_text: str = Field(min_length=100, max_length=20_000)
    target_role: str | None = Field(default=None, max_length=160)


@router.post("/assess")
async def assess(body: AssessIn, request: Request) -> dict:
    s = get_settings()
    if _rate_limited(_client_ip(request), limit=s.assess_rate_limit,
                     window=s.assess_rate_window_seconds):
        raise HTTPException(429, "You've used your free assessments for now — sign up to run Ada.")
    result = await assess_cv(body.cv_text, body.target_role)
    return {
        "score": result.score,
        "headline": result.headline,
        "fixes": [{"title": f.title, "detail": f.detail, "quote": f.quote} for f in result.fixes],
    }
