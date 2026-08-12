# Alembic migrations

Generate revisions from the `backend` directory and review every operation
before committing it:

```bash
../.venv/bin/python -m alembic revision --autogenerate -m "describe change"
../.venv/bin/python -m alembic upgrade head
```

Application startup never calls `create_all` for refactored models. Schema
changes are applied as an explicit deployment step before a new application
version becomes ready.
