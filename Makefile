# ClaimCheck Rehab, B1. Targets run from the repository root. Local credentials come from .env.local
# (git-ignored). The test database is claimcheck_test; the app role is claimcheck_app.
SHELL := /bin/bash
VENV := dev/.venv/bin
PYCFG := --config dev/pyproject.toml
PY_SRC := packages/core/claimcheck_core apps/api/claimcheck_api apps/worker/claimcheck_worker scripts
ENV := set -a; . ./.env.local; set +a;

.PHONY: venv dev stop lint typecheck test test-unit test-integration test-clean test-minimiser check-migrations migrate

venv:
	/opt/homebrew/bin/python3.12 -m venv dev/.venv
	$(VENV)/pip install -q -e packages/core -e apps/api -e apps/worker pytest hypothesis httpx ruff mypy
	cd packages/minimiser && npm install --no-audit --no-fund

dev:
	scripts/dev.sh

stop:
	scripts/dev.sh-stop

migrate:
	$(ENV) cd packages/core && ../../$(VENV)/alembic upgrade head

lint:
	$(VENV)/ruff check $(PYCFG) packages apps tests scripts
	cd packages/minimiser && npx eslint src test

typecheck:
	$(VENV)/mypy --config-file dev/pyproject.toml $(PY_SRC)
	cd packages/minimiser && npx tsc --noEmit

test-unit:
	$(VENV)/pytest -q -p no:cacheprovider tests/unit

test-integration:
	$(VENV)/pytest -q -p no:cacheprovider tests/integration

test-minimiser:
	cd packages/minimiser && npx vitest run

# The integration fixtures drop and re-create the public schema of claimcheck_test and migrate it.
test: test-unit test-integration test-minimiser

test-clean: test
	$(ENV) MIGRATION_DATABASE_URL=$$TEST_MIGRATION_DATABASE_URL $(VENV)/python scripts/check_migrations.py

check-migrations:
	$(ENV) $(VENV)/python scripts/check_migrations.py
