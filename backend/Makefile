PYTHON ?= python

.PHONY: check test lint format migration-check

check: lint test migration-check

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check app migrations scripts cdek_client.py payments.py email_service.py tests
	$(PYTHON) -m ruff format --check app migrations scripts cdek_client.py payments.py email_service.py tests
	$(PYTHON) -m ruff check main.py --select E9

format:
	$(PYTHON) -m ruff check app migrations scripts cdek_client.py payments.py email_service.py tests --fix
	$(PYTHON) -m ruff format app migrations scripts cdek_client.py payments.py email_service.py tests

migration-check:
	APP_ENV=test DATABASE_ENABLED=true DATABASE_URL=postgresql+asyncpg://check:check@localhost/check $(PYTHON) -m alembic -c alembic.ini upgrade head --sql >/dev/null
	APP_ENV=test DATABASE_ENABLED=true DATABASE_URL=postgresql+asyncpg://check:check@localhost/check $(PYTHON) -m alembic -c alembic.ini downgrade head:base --sql >/dev/null
