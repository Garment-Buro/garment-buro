from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class PostgresRehearsalSnapshot:
    server_version: str
    transaction_read_only: bool
    in_recovery: bool
    is_superuser: bool
    tls_in_use: bool
    schema_revisions: tuple[str, ...]


class RehearsalRepository:
    async def inspect_postgres(self, session: AsyncSession) -> PostgresRehearsalSnapshot:
        row = (
            (
                await session.execute(
                    text(
                        """
                    SELECT
                        current_setting('server_version') AS server_version,
                        current_setting('transaction_read_only')::boolean
                            AS transaction_read_only,
                        pg_is_in_recovery() AS in_recovery,
                        COALESCE(
                            (SELECT usesuper FROM pg_user WHERE usename = current_user),
                            false
                        ) AS is_superuser,
                        COALESCE(
                            (SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()),
                            false
                        ) AS tls_in_use
                    """
                    )
                )
            )
            .mappings()
            .one()
        )
        revisions = tuple(
            await session.scalars(
                text("SELECT version_num FROM alembic_version ORDER BY version_num")
            )
        )
        return PostgresRehearsalSnapshot(
            server_version=str(row["server_version"]),
            transaction_read_only=bool(row["transaction_read_only"]),
            in_recovery=bool(row["in_recovery"]),
            is_superuser=bool(row["is_superuser"]),
            tls_in_use=bool(row["tls_in_use"]),
            schema_revisions=revisions,
        )
