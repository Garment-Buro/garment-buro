"""Serialize online Alembic sessions and wait for their server-side completion.

Only use unpooled connections: PostgreSQL releases this session lock when the
physical connection closes, after any pending commit or rollback completes.
"""

from sqlalchemy import Connection, text

# Two int32 keys; advisory locks are scoped to the current PostgreSQL database.
MIGRATION_LOCK = text("SELECT pg_advisory_lock(1195537746, 1)")


def acquire_migration_lock(connection: Connection) -> None:
    if connection.dialect.name == "postgresql":
        connection.execute(MIGRATION_LOCK)
