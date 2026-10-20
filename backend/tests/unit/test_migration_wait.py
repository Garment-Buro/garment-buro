from __future__ import annotations

import asyncio
import json

import pytest
from sqlalchemy.exc import SQLAlchemyError

from scripts import wait_for_migration


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        "sqlite+aiosqlite:///local.db",
        "mysql://user@host/db",
        "postgresql://",
        "postgresql://host/db",
        "postgresql://user@host",
    ],
)
def test_invalid_database_settings_do_not_create_engine(monkeypatch, url):
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid settings must not connect to a default database")

    monkeypatch.setattr(wait_for_migration, "create_async_engine", unexpected)
    with pytest.raises((SQLAlchemyError, ValueError)):
        asyncio.run(wait_for_migration.run({} if url is None else {"DATABASE_URL": url}))


def test_help_does_not_connect(monkeypatch, capsys):
    def unexpected(*args, **kwargs):
        pytest.fail("Help must not connect")

    monkeypatch.setattr(wait_for_migration, "create_async_engine", unexpected)
    with pytest.raises(SystemExit) as error:
        wait_for_migration.main(["--help"])
    assert error.value.code == 0
    assert "PostgreSQL" in capsys.readouterr().out


def test_database_error_does_not_print_credentials(monkeypatch, capsys):
    async def fail(environment):
        raise SQLAlchemyError("postgresql://private-user:private-secret@private-host/private-db")

    monkeypatch.setattr(wait_for_migration, "run", fail)
    assert wait_for_migration.main([]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err) == {
        "event": "database.migration_wait_failed",
        "error_type": "SQLAlchemyError",
    }
    assert "private-" not in output.err
