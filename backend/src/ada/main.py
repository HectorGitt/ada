"""FastAPI app factory. API-only service; the Next.js frontend lives in frontend/."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ada.api.routes import (
    account,
    applications,
    auth,
    candidate,
    chat,
    documents,
    employer,
    health,
    jobs,
    memories,
    profile,
    runs,
    subscriptions,
    voice,
    webhooks,
)
from ada.config import get_settings
from ada.db.session import init_db
from ada.observability import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    settings.validate_runtime()  # fail fast in staging/prod on missing secrets/config
    if settings.app_env == "local":
        # Dev convenience only. Staging/prod schema is owned by Alembic (`make migrate`).
        await init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Ada", version="0.2.0", lifespan=lifespan)
    # The frontend proxies /api/* same-origin, so CORS matters only for direct API
    # consumers; credentials are allowed for the session cookie.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins + [settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(profile.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")
    app.include_router(memories.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(applications.router, prefix="/api")
    app.include_router(subscriptions.router, prefix="/api")
    app.include_router(account.router, prefix="/api")
    app.include_router(candidate.router, prefix="/api")
    app.include_router(employer.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(webhooks.router, prefix="/api")
    app.include_router(voice.router, prefix="/api")
    return app


app = create_app()
