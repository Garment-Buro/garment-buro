from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import ConfigurationError
from app.db.session import DatabaseManager


async def verify_postgres_schema(database: DatabaseManager) -> None:
    """Deployment databases must be migrated before serving application traffic.

    SQLite is used by isolated domain tests. PostgreSQL is checked against the
    actual revision bundled with this release, without modifying the database.
    """
    if not database.enabled or database.backend_name != "postgresql":
        return
    configuration = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    expected = set(ScriptDirectory.from_config(configuration).get_heads())
    try:
        async with database.engine.connect() as connection:
            current = await connection.run_sync(
                lambda sync: set(MigrationContext.configure(sync).get_current_heads())
            )
    except (OSError, SQLAlchemyError) as error:
        raise ConfigurationError("PostgreSQL schema could not be verified") from error
    if not expected or current != expected:
        raise ConfigurationError(
            "PostgreSQL schema is not current; run Alembic upgrade head before starting the API"
        )
