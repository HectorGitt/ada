# Go-live runbook — Ada · Uche (Recrulus)

Everything that stands between the green `main` branch and a live product taking real
users and money. Ordered; each step says **who** (you, in a console) vs **automated**.

Legend: 🔴 blocks launch · 🟡 before real users · 🟢 nice-to-have

---

## 0. Prerequisites
- A **Google Cloud project** with **billing enabled** (this is the big one — see §1).
- The **recrulus.com** domain (or your own) with DNS access.
- Accounts: **Paystack**, **Stripe**, **Resend** (email), optionally **Twilio** (WhatsApp).

---

## 1. 🔴 AI: enable generation (the #1 blocker)
Right now the Gemini key is on the free tier at `limit: 0` for generation and a tiny
embedding quota — so insights, Uche's rationale, CV rewrite, chat, voice, **and** the
verification grading all silently fall back to heuristics, and only ~a few dozen jobs can
be embedded before `429`.

Pick one:
- **A — pay-as-you-go AI Studio key:** [aistudio.google.com](https://aistudio.google.com) → the key's project → **Set up billing**. Keeps `GEMINI_API_KEY`; nothing else changes.
- **B — Vertex AI (recommended for prod):** unset `GEMINI_API_KEY`, set `GCP_PROJECT` +
  give the Cloud Run service account the **Vertex AI User** role. `vertex.py` switches
  automatically. Higher, production-grade quotas.

Verify: after enabling, re-run the ingest embed backfill (§7) and confirm `count(embedding)`
climbs.

---

## 2. 🔴 Database — Cloud SQL (Postgres + pgvector)
```bash
gcloud sql instances create ada-db --database-version=POSTGRES_16 --region=<region> --tier=db-custom-2-7680
gcloud sql databases create ada --instance=ada-db
# connect once and enable the extension:
#   CREATE EXTENSION IF NOT EXISTS vector;
```
Run migrations as a release step (see §5): `alembic upgrade head` → head is `0015_verification`.

---

## 3. 🔴 Payments — create the real plan codes
Checkout resolves codes from `PAYSTACK_PLANS` / `STRIPE_PRICES` (JSON, keyed
`<tier>_<cadence>`). Tiers: candidate `pro`/`premium`, employer `growth`/`scale`; cadences
`monthly`/`annual`. Prices live in `backend/src/ada/payments/plans.py`.

- **Paystack** → Plans → create one plan per (tier, cadence) → copy each `PLN_…` code.
- **Stripe** → Products → a price per (tier, cadence) → copy each `price_…` id.
- **Webhooks:** point `https://<api-host>/api/webhooks/paystack` and `/api/webhooks/stripe`
  at the deploy; put the Stripe signing secret in `STRIPE_WEBHOOK_SECRET`.

Set (example):
```
PAYSTACK_PLANS={"pro_monthly":"PLN_a","pro_annual":"PLN_b","premium_monthly":"PLN_c","premium_annual":"PLN_d","growth_monthly":"PLN_e","growth_annual":"PLN_f","scale_monthly":"PLN_g","scale_annual":"PLN_h"}
STRIPE_PRICES={"pro_monthly":"price_a", ... , "scale_annual":"price_h"}
```
Also set the one-off run price server-side: `PRICE_KOBO` (NGN) and `STRIPE_PRICE_USD_CENTS`.

---

## 4. 🔴 Secrets — Secret Manager
Every secret `validate_runtime()` and the features need. Create in Secret Manager and wire
into the Cloud Run service:

| Secret | Purpose |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://…` Cloud SQL connection |
| `GEMINI_API_KEY` **or** `GCP_PROJECT` | AI (see §1) |
| `PAYSTACK_SECRET_KEY` · `PAYSTACK_PUBLIC_KEY` | payments |
| `STRIPE_SECRET_KEY` · `STRIPE_PUBLISHABLE_KEY` · `STRIPE_WEBHOOK_SECRET` | payments |
| `PAYSTACK_PLANS` · `STRIPE_PRICES` | plan codes (§3) |
| `RESEND_API_KEY` | email (auth + notifications) |
| `TWILIO_ACCOUNT_SID` · `TWILIO_AUTH_TOKEN` · `TWILIO_WHATSAPP_FROM` | 🟡 WhatsApp |
| `JOOBLE_FEEDS` | Nigerian/global job ingestion |
| `GCS_BUCKET` | 🟡 CV upload archive |

Non-secret env (set on the service): `APP_ENV=prod`, `ALLOWED_ORIGIN=https://ada.recrulus.com,https://uche.recrulus.com`,
`FRONTEND_ORIGIN=https://ada.recrulus.com`, `FRONTEND_BASE_URL=https://ada.recrulus.com`,
`NEXT_PUBLIC_WS_URL` (frontend). `validate_runtime()` **refuses to boot** without a payment
provider, `RESEND_API_KEY`, a real `FRONTEND_ORIGIN`, and non-wildcard CORS — so a
misconfig fails the deploy, not a user request.

---

## 5. 🟢 Backend deploy — Cloud Run (already automated)
CI/CD deploys `backend/` to Cloud Run on push to `main` (`.github/workflows`). Confirm the
workflow has: the secrets bound (§4), a **release step running `alembic upgrade head`**
before traffic shifts, and the Cloud SQL connection attached. Health: `GET /api/readyz`.

---

## 6. 🔴 Frontend deploy — Vercel
- Import `frontend/`. Set `BACKEND_URL=https://<api-host>` (server-side `/api` proxy) and
  `NEXT_PUBLIC_WS_URL=wss://<api-host>` (voice).
- **Two domains, one deploy:** point **both** `ada.recrulus.com` and `uche.recrulus.com`
  at the Vercel project. `middleware.ts` rewrites the `uche.*` host into `/hire`.

---

## 7. 🟡 Scheduled jobs — Cloud Scheduler → Cloud Run Jobs
Three cron jobs (each a Cloud Run Job running the container with a different command):

| Command | Cadence | Purpose |
|---|---|---|
| `python -m ada.ingest` | every 6h | refresh the jobs pool + embed new listings |
| `python -m ada.recover` | every 2–5 min | re-dispatch stuck runs/applications |
| `python -m ada.digest` | weekly | Ada's proactive fresh-roles outreach |

First ingest run after billing is on will backfill the ~6.9k jobs' embeddings (they're
already fetched; only the vectors are pending).

---

## 8. 🟡 Compliance (before real users)
Employment data + cross-border = not optional:
- **Privacy policy + Terms** (linked in footer + signup).
- **NDPR** (Nigeria) and **GDPR** (any EU/UK employer touching candidate data): lawful basis,
  consent records, data-subject rights, retention. The `discoverable` opt-in already gates
  employer visibility — record and timestamp consent.
- **Email/WhatsApp opt-out** — ship notification preferences + an unsubscribe path before
  turning up volume.

---

## 9. Smoke test (go / no-go)
- [ ] `GET /api/readyz` → `ready`
- [ ] Sign up → welcome email arrives (Resend live)
- [ ] Start a run → pay (Paystack test → live) → run completes → deliverables render
- [ ] Uche: post a role → shortlist has embedded candidates with match scores + verified badges
- [ ] Candidate: take the proctored assessment → credential shows on the Uche card
- [ ] Intro request → candidate notified (in-app + email + WhatsApp) → accept → connection email to both
- [ ] Subscribe (candidate + employer) → webhook flips status → entitlement unlocks
- [ ] Both hosts resolve: `ada.recrulus.com` (Ada) and `uche.recrulus.com` (Uche landing)

When every box is checked, you're live.

---

## Current state (2026-07-31)
- ✅ Code: feature-complete, `main` green (gauntlet + 26 frontend routes).
- ✅ Jobs: **~6,937 real listings ingested** (Greenhouse, Ashby, Lever, Nigerian Jooble).
- ⏳ Embeddings: rate-limited on free tier — backfill once §1 billing is on.
- 🔴 Not live: §1 billing, §3 plan codes, §4 secrets, §6 frontend deploy, §8 compliance.
