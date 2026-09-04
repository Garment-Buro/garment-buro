from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.exceptions import InvalidEmailError
from app.modules.identity.models import RoleName, UserStatus
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.security import normalize_email


class RoleBootstrapError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RoleBootstrapPlan:
    user_id: int
    role: RoleName
    already_assigned: bool


class RoleBootstrapService:
    def __init__(self, repository: IdentityRepository | None = None) -> None:
        self.repository = repository or IdentityRepository()

    async def inspect(
        self,
        session: AsyncSession,
        *,
        email: str,
        role: RoleName,
    ) -> RoleBootstrapPlan:
        if role not in {RoleName.PARTNER, RoleName.MANAGER, RoleName.ADMIN}:
            raise RoleBootstrapError("Only partner, manager, or admin can be bootstrapped")
        try:
            _, normalized_email = normalize_email(email)
        except InvalidEmailError as error:
            raise RoleBootstrapError("Target email is invalid") from error
        user = await self.repository.get_user_by_email(session, normalized_email)
        if user is None or user.status != UserStatus.ACTIVE.value:
            raise RoleBootstrapError("Active target user was not found")
        target_role = await self.repository.get_role(session, role)
        if target_role is None:
            raise RoleBootstrapError("System role was not initialized")
        return RoleBootstrapPlan(
            user_id=user.id,
            role=role,
            already_assigned=await self.repository.user_has_role(
                session,
                user_id=user.id,
                role_id=target_role.id,
            ),
        )

    async def apply(
        self,
        session: AsyncSession,
        *,
        plan: RoleBootstrapPlan,
        expected_user_id: int,
    ) -> RoleBootstrapPlan:
        if plan.user_id != expected_user_id:
            raise RoleBootstrapError("Expected user ID does not match the inspected target")
        if plan.already_assigned:
            return plan
        target_role = await self.repository.get_role(session, plan.role)
        if target_role is None:
            raise RoleBootstrapError("System role was not initialized")
        await self.repository.assign_role(
            session,
            user_id=plan.user_id,
            role_id=target_role.id,
        )
        await self.repository.add_audit_event(
            session,
            event_type="authorization.role_bootstrapped",
            subject_user_id=plan.user_id,
            details={"role": plan.role.value},
        )
        await session.flush()
        return RoleBootstrapPlan(
            user_id=plan.user_id,
            role=plan.role,
            already_assigned=True,
        )
