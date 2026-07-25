# Working agreement for agents

Read this before writing anything. It is short on purpose.

## The contract

`make verify` is the whole contract for backend work. If it is green, your work is
done. If it is red, your work is not done. There is no third state, and there is no
"it works, the test is wrong."

Inner loop: `make fast` (seconds). Final gate: `make verify` (minutes, includes
mutation testing). Both need Postgres up (`make up`) and `RUN_DB_TESTS=1` for the
full suite; CI always runs the full suite.

Frontend and mobile: `pnpm typecheck && pnpm build` (frontend), `npx tsc --noEmit`
(mobile) must be green before any commit touching them.

## What you may change

- `backend/src/**` — implementation
- `backend/tests/**` except `backend/tests/acceptance/**` — your own unit tests
- `frontend/src/**`, `mobile/src/**`
- Alembic migrations under `backend/migrations/versions/` (append-only; never edit
  an existing revision)

## What you may not change, ever

- `backend/features/**` — the Gherkin specification of the money path
- `backend/tests/acceptance/**` — the public contract (webhook + idempotency tests)
- `backend/quality/**` — thresholds and protected globs
- `backend/scripts/**`, `backend/.importlinter`, `backend/pyproject.toml`
- `Makefile`, `AGENTS.md`, `.github/**`

If passing requires touching any of these, stop and say so. That is a spec problem,
and spec problems are the human's, not yours. A commit that lowers a threshold or
deletes a scenario is worse than no commit at all.

## Non-negotiable invariants

- Payment webhooks: signature check first, then out-of-band charge verification,
  then amount/currency check. Never trust the payload alone.
- Exactly-once: event claim + PENDING_PAYMENT→PAID in one transaction;
  PAID→RUNNING via atomic UPDATE. The acceptance tests and the Gherkin spec pin
  these; if your change makes them fail, your change is wrong.
- Matching reads the local jobs table only. No external job API in a request path.
- Secrets live in .env / Secret Manager. Never in code, never committed.

## Forbidden moves

These fail the build automatically (`backend/scripts/check-cheats.sh`):

- bare `# type: ignore` or bare `# noqa` (code-specific with a written reason is
  allowed, e.g. `# noqa: BLE001 — classify, then re-raise`)
- `# pragma: no cover`, `@pytest.mark.skip`, `@pytest.mark.xfail`, `pytest.skip(...)`
- tests with no assertions, or `assert True`
- redefining MIN_COVERAGE / MIN_MUTATION_SCORE outside quality/thresholds.env
- deleting a failing test instead of fixing the code

Code style: no comments unless explicitly asked; one-line docstrings only where a
contract is non-obvious.

## What "done" means

1. `make verify` exits 0 (backend) / typecheck+build green (frontend, mobile).
2. Mutation score at or above the floor.
3. Public API routes and response shapes unchanged, or the change is flagged
   explicitly in your summary.

## What to put in your summary

- which public routes/response shapes changed, if any
- which surviving mutants remain and why they are acceptable
- any assumption you made that the spec did not settle
- anything you wanted to change in a protected path but didn't
