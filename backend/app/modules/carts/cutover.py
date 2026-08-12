from sqlalchemy import select

from app.core.exceptions import ConfigurationError
from app.db.session import DatabaseManager
from app.modules.carts.models import CartMigrationRun


async def verify_cart_cutover(
    database: DatabaseManager,
    expected_fingerprint: str,
) -> None:
    async with database.session() as session:
        migration_run = await session.scalar(
            select(CartMigrationRun).where(
                CartMigrationRun.fingerprint_sha256 == expected_fingerprint
            )
        )
        if migration_run is None:
            raise ConfigurationError("Reviewed cart migration is not present")
