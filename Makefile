.PHONY: install dev up down test lint typecheck migrate revision seed recover deploy
install:
	cd backend && pip install -e ".[dev]"
up:
	docker compose up -d
down:
	docker compose down
dev:
	cd backend && uvicorn ada.main:app --reload --port 8080
test:
	cd backend && pytest -q
lint:
	cd backend && ruff check src tests
typecheck:
	cd backend && mypy src
migrate:
	cd backend && alembic upgrade head
revision:
	cd backend && alembic revision --autogenerate -m "$(m)"
seed:
	cd backend && python -m ada.seed
recover:
	cd backend && python -m ada.recover
deploy:
	cd backend && gcloud run deploy ada --source . --region $${GCP_LOCATION:-us-central1} \
	  --set-secrets PAYSTACK_SECRET_KEY=paystack-secret:latest,STRIPE_SECRET_KEY=stripe-secret:latest,STRIPE_WEBHOOK_SECRET=stripe-webhook-secret:latest \
	  --allow-unauthenticated

include backend/quality/thresholds.env
export

.PHONY: verify fast cheats protected gauntlet-lint types coverage bdd arch security mutate hooks
verify: cheats protected gauntlet-lint types coverage bdd arch security mutate
	@echo ""
	@echo "✓ gauntlet passed — coverage ≥ $(MIN_COVERAGE)%, mutation ≥ $(MIN_MUTATION_SCORE)%"

fast: cheats gauntlet-lint types coverage bdd arch

cheats:
	cd backend && ./scripts/check-cheats.sh

protected:
	cd backend && ./scripts/check-protected.sh $(BASE)

gauntlet-lint:
	cd backend && ruff check src tests features migrations

types:
	cd backend && mypy src

coverage:
	cd backend && pytest tests -q --cov=ada --cov-report=term --cov-fail-under=$(MIN_COVERAGE)

bdd:
	cd backend && pytest features -q -p no:cacheprovider

arch:
	cd backend && lint-imports

security:
	cd backend && bandit -q -r src

mutate:
	cd backend && python scripts/mutation_score.py

hooks:
	cd backend && ./scripts/install-hooks.sh
