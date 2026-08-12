from __future__ import annotations

from sqlalchemy import func, select

from app.core.exceptions import ConfigurationError
from app.db.session import DatabaseManager
from app.modules.identity.models import (
    IdentityMigrationRun,
    Permission,
    PermissionCode,
    Role,
    RoleName,
    RolePermission,
    User,
)


async def verify_identity_cutover(
    database: DatabaseManager,
    fingerprint: str,
) -> None:
    async with database.session() as session:
        migration_run = await session.scalar(
            select(IdentityMigrationRun).where(
                IdentityMigrationRun.fingerprint_sha256 == fingerprint
            )
        )
        if migration_run is None:
            raise ConfigurationError(
                "Identity API cutover fingerprint is not present in the target database"
            )
        users_count = int(await session.scalar(select(func.count()).select_from(User)) or 0)
        if users_count < migration_run.users_count:
            raise ConfigurationError(
                "Identity API target contains fewer users than the reviewed migration run"
            )

        customer_permissions = set(
            await session.scalars(
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .join(Role, Role.id == RolePermission.role_id)
                .where(Role.name == RoleName.CUSTOMER.value)
            )
        )
        required_permissions = {
            PermissionCode.PROFILE_READ_OWN.value,
            PermissionCode.PROFILE_WRITE_OWN.value,
            PermissionCode.ORDERS_READ_OWN.value,
        }
        if not required_permissions <= customer_permissions:
            raise ConfigurationError("Identity API customer permissions are incomplete")
