# Ada backend

FastAPI service that runs the whole business: paid agent runs (LangGraph over Gemini on
Vertex AI), dual-provider payments, email+password auth, career-profile grounding, and a
streaming coaching chat.

## Layout

```
src/ada/
  config.py            env-driven settings + fail-fast prod validation
  observability.py     JSON structured logging (Cloud Logging-ready)
  resilience.py        bounded retry w/ backoff for transient LLM/API failures
  vertex.py            shared Vertex/Gemini client (request timeout)
  main.py              app factory (API-only; frontend is a separate service)
  auth/                bcrypt passwords, reset tokens (hashed, single-use), sessions, mailer (Resend)
  api/routes/          health/readyz · auth · profile · chat (SSE) · runs · webhooks · voice (WS)
  payments/            paystack (sig + server-side verify) · stripe (checkout + verify)
  db/                  pooled async session · models · repositories (atomic money-path SQL)
  services/
    graph.py           LangGraph: intake -> cv_rewrite -> job_match -> interview_prep
    cv.py              ATS rewrite        search.py   embeddings + pgvector KNN
    interview.py       questions + scoring (structured output)
    coach.py           chat grounded in profile + run history
    voice.py           Gemini Live intake + transcript extraction
    runs.py            atomic run execution + crash recovery
  seed.py / recover.py CLIs (jobs corpus, stuck-run sweep)
migrations/            Alembic (async): 0001 schema · 0002 auth · 0003 profiles
tests/                 unit + Postgres-gated integration (RUN_DB_TESTS=1)
```

## Endpoints

| Area | Route | Notes |
|---|---|---|
| Health | `GET /api/healthz` · `GET /api/readyz` | readyz pings the DB |
| Auth | `POST /api/auth/signup` · `login` → cookie; `request-reset` → `reset`; `me`, `logout` | bcrypt passwords; generic 401 + always-202 reset = no account enumeration; reset tokens hashed, single-use, 30-min TTL |
| Profile | `GET/PUT /api/profile` | imported LinkedIn text grounds chat + runs |
| Chat | `POST /api/chat` (SSE) | streams deltas; grounded in profile + last runs |
| Runs | `POST /api/runs` · `GET /api/runs` · `GET /api/runs/{id}` · `POST /api/runs/{id}/interview` | owned runs are private; creation works with or without a session |
| Webhooks | `POST /api/webhooks/paystack` · `/stripe` | the only paths that start a run |
| Voice | `WS /api/voice` | Gemini Live relay; produces intake fields only |

## Invariants that protect revenue

1. Webhook signatures are verified, then the charge is confirmed **out of band**
   (Paystack `transaction/verify` API; Stripe event `payment_status` + `amount_total`),
   and amount/currency are checked against the run.
2. `PaymentRepository.confirm`: event claim + `PENDING_PAYMENT → PAID` in one
   transaction — a replayed webhook is a no-op.
3. `RunRepository.claim_for_execution`: `PAID → RUNNING` via
   `UPDATE ... WHERE status = PAID` — concurrent workers can't both run a job.
4. `python -m ada.recover` re-dispatches runs stuck in PAID (lost dispatch); safe to run
   on a schedule because of (3).

## Develop

```bash
pip install -e ".[dev]"        # on older macOS: PIP_CONSTRAINT=constraints-local.txt
cp .env.example .env
docker compose up -d           # from repo root
alembic upgrade head
python -m ada.seed             # embeds the jobs corpus (needs GCP creds)
uvicorn ada.main:app --reload --port 8080
```

Local `APP_ENV=local`: schema auto-creates on boot, password-reset links are logged not emailed.

## Fetching jobs

Matching only ever reads the local `jobs` table; listings are pulled ahead of time:

```bash
python -m ada.ingest [--limit N]
```

The pipeline fetches every source configured in `src/ada/ingest/boards.py`
(Greenhouse, Lever, and Ashby boards — public, keyless; Jooble when `JOOBLE_FEEDS`
maps feed hosts to keys — keys are country-bound, e.g. `ng.jooble.org` for Nigeria
plus `jooble.org` for remote/global roles), normalizes each listing to one schema, upserts
with `ON CONFLICT (source, external_id) DO UPDATE` (re-runs refresh, never duplicate),
then embeds any rows with NULL embeddings. Without model credentials the embed pass
logs and skips — listings still land, and the next credentialed run backfills vectors.

In production this runs as a **Cloud Run Job on a Cloud Scheduler trigger** (e.g. every
6 hours), never in a request handler. `python -m ada.seed` remains a dev-only fallback
corpus for running without any network fetch.

## Test

```bash
ruff check src tests migrations
pytest -q                      # unit tests
RUN_DB_TESTS=1 pytest -q       # + idempotency/atomicity tests against Postgres
```

## Deploy

Cloud Run via `make deploy` (repo root). Secrets come from Secret Manager. Run
`alembic upgrade head` as a release step before shifting traffic. `validate_runtime`
refuses to boot staging/prod without payment provider secrets, `RESEND_API_KEY`,
a real `FRONTEND_ORIGIN`, and non-wildcard CORS.
