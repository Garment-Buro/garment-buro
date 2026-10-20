PYTHON ?= python

.PHONY: check dependency-check test lint format migration-check

check: dependency-check lint test migration-check

dependency-check:
	$(PYTHON) -m scripts.check_dependencies

test:
	$(PYTHON) -m pytest -q --tb=short

lint:
	$(PYTHON) -m ruff check app migrations scripts tests
	$(PYTHON) -m ruff format --check app migrations scripts tests

format:
	$(PYTHON) -m ruff check app migrations scripts tests --fix
	$(PYTHON) -m ruff format app migrations scripts tests

migration-check:
	APP_ENV=test DATABASE_ENABLED=true DATABASE_URL=postgresql+asyncpg://check:check@localhost/check $(PYTHON) -m alembic -c alembic.ini upgrade head --sql >/dev/null
	APP_ENV=test DATABASE_ENABLED=true DATABASE_URL=postgresql+asyncpg://check:check@localhost/check $(PYTHON) -m alembic -c alembic.ini downgrade head:base --sql >/dev/null
