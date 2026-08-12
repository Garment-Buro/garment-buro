from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.migration_types import (
    IdentityMigrationPlan,
    IdentityMigrationResult,
    InvalidIdentityMigrationPlanError,
    TargetIdentityNotEmptyError,
)
from app.modules.identity.models import (
    IdentityMigrationRun,
    OtpChallenge,
    RefreshSession,
    Role,
    RoleName,
    SecurityAuditEvent,
    User,
    UserRole,
    UserStatus,
)
from app.modules.identity.repository import IdentityRepository
from app.modules.orders.models import LegacyOrderClaim


class IdentityMigrationService:
    def __init__(self, repository: IdentityRepository | None = None) -> None:
        self.repository = repository or IdentityRepository()

    async def apply(
        self,
        session: AsyncSession,
        plan: IdentityMigrationPlan,
    ) -> IdentityMigrationResult:
        if not plan.valid:
            raise InvalidIdentityMigrationPlanError(
                "Identity migration plan contains validation errors"
            )
        await self._ensure_target_empty(session)
        await self.repository.ensure_system_authorization(session)
        customer_role = await session.scalar(
            select(Role).where(Role.name == RoleName.CUSTOMER.value)
        )
        if customer_role is None:
            raise RuntimeError("System customer role is missing")

        for record in plan.users:
            user = User(
                id=record.id,
                email=record.email,
                email_normalized=record.email_normalized,
                telegram_id=record.telegram_id,
                first_name=record.first_name,
                last_name=record.last_name,
                username=record.username,
                phone=record.phone,
                gender=record.gender,
                birth_date=record.birth_date,
                height_cm=record.height_cm,
                weight_kg=record.weight_kg,
                status=UserStatus.ACTIVE.value,
                email_verified_at=(
                    record.created_at
                    if record.email is not None and not record.had_legacy_otp
                    else None
                ),
                created_at=record.created_at,
                updated_at=record.created_at,
            )
            user.role_links.append(UserRole(role_id=customer_role.id))
            session.add(user)

        session.add(
            IdentityMigrationRun(
                fingerprint_sha256=plan.fingerprint,
                users_count=len(plan.users),
            )
        )
        await session.flush()
        await self._synchronize_postgresql_sequences(session)
        await session.commit()
        return IdentityMigrationResult(
            fingerprint_sha256=plan.fingerprint,
            users=len(plan.users),
        )

    @staticmethod
    async def _ensure_target_empty(session: AsyncSession) -> None:
        counts = {
            "users": await session.scalar(select(func.count()).select_from(User)),
            "user_roles": await session.scalar(select(func.count()).select_from(UserRole)),
            "otp_challenges": await session.scalar(select(func.count()).select_from(OtpChallenge)),
            "refresh_sessions": await session.scalar(
                select(func.count()).select_from(RefreshSession)
            ),
            "security_audit_events": await session.scalar(
                select(func.count()).select_from(SecurityAuditEvent)
            ),
            "migration_runs": await session.scalar(
                select(func.count()).select_from(IdentityMigrationRun)
            ),
            "legacy_order_claims": await session.scalar(
                select(func.count()).select_from(LegacyOrderClaim)
            ),
        }
        if any(counts.values()):
            rendered = ", ".join(f"{name}={count}" for name, count in counts.items())
            raise TargetIdentityNotEmptyError(
                f"Target identity store must be empty before import ({rendered})"
            )

    @staticmethod
    async def _synchronize_postgresql_sequences(session: AsyncSession) -> None:
        if session.get_bind().dialect.name != "postgresql":
            return
        for table_name in (
            "users",
            "roles",
            "permissions",
            "identity_migration_runs",
        ):
            await session.execute(
                text(
                    "SELECT setval("
                    f"pg_get_serial_sequence('{table_name}', 'id'), "
                    f"COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {table_name}"
                )
            )
