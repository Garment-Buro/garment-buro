from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.identity.models import (
    SYSTEM_ROLE_PERMISSIONS,
    OtpChallenge,
    OtpPurpose,
    Permission,
    PermissionCode,
    RefreshSession,
    Role,
    RoleName,
    RolePermission,
    SecurityAuditEvent,
    User,
    UserRole,
    UserStatus,
)


class IdentityRepository:
    async def get_user_by_email(
        self,
        session: AsyncSession,
        email_normalized: str,
        *,
        for_update: bool = False,
    ) -> User | None:
        statement = select(User).where(User.email_normalized == email_normalized)
        if for_update:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def get_user(
        self,
        session: AsyncSession,
        user_id: int,
        *,
        for_update: bool = False,
    ) -> User | None:
        statement = select(User).where(User.id == user_id)
        if for_update:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def get_active_user_for_session(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        session_id: str,
        now: datetime,
    ) -> User | None:
        return await session.scalar(
            select(User)
            .join(RefreshSession, RefreshSession.user_id == User.id)
            .where(
                User.id == user_id,
                User.status == UserStatus.ACTIVE.value,
                RefreshSession.session_id == session_id,
                RefreshSession.revoked_at.is_(None),
                RefreshSession.expires_at > now,
            )
        )

    async def create_customer(
        self,
        session: AsyncSession,
        *,
        email: str,
        email_normalized: str,
    ) -> User:
        role = await session.scalar(select(Role).where(Role.name == RoleName.CUSTOMER.value))
        if role is None:
            raise RuntimeError("System customer role is missing")
        user = User(email=email, email_normalized=email_normalized)
        session.add(user)
        await session.flush()
        session.add(UserRole(user_id=user.id, role_id=role.id))
        await session.flush()
        return user

    async def get_or_create_customer(
        self,
        session: AsyncSession,
        *,
        email: str,
        email_normalized: str,
    ) -> User:
        user = await self.get_user_by_email(
            session,
            email_normalized,
            for_update=True,
        )
        if user is not None:
            return user
        try:
            async with session.begin_nested():
                return await self.create_customer(
                    session,
                    email=email,
                    email_normalized=email_normalized,
                )
        except IntegrityError:
            user = await self.get_user_by_email(
                session,
                email_normalized,
                for_update=True,
            )
            if user is None:
                raise
            return user

    async def latest_challenge(
        self,
        session: AsyncSession,
        *,
        target_email_normalized: str,
        purpose: OtpPurpose,
    ) -> OtpChallenge | None:
        return await session.scalar(
            select(OtpChallenge)
            .where(
                OtpChallenge.target_email_normalized == target_email_normalized,
                OtpChallenge.purpose == purpose.value,
            )
            .order_by(OtpChallenge.created_at.desc(), OtpChallenge.id.desc())
            .limit(1)
        )

    async def recent_challenge_count(
        self,
        session: AsyncSession,
        *,
        target_email_normalized: str,
        requested_ip_digest: str | None,
        since: datetime,
    ) -> int:
        email_count = await session.scalar(
            select(func.count())
            .select_from(OtpChallenge)
            .where(
                OtpChallenge.target_email_normalized == target_email_normalized,
                OtpChallenge.created_at >= since,
            )
        )
        if requested_ip_digest is None:
            return int(email_count or 0)
        ip_count = await session.scalar(
            select(func.count())
            .select_from(OtpChallenge)
            .where(
                OtpChallenge.requested_ip_digest == requested_ip_digest,
                OtpChallenge.created_at >= since,
            )
        )
        return max(int(email_count or 0), int(ip_count or 0))

    async def replace_active_challenge(
        self,
        session: AsyncSession,
        challenge: OtpChallenge,
        *,
        invalidated_at: datetime,
    ) -> list[int]:
        invalidated_ids = list(
            await session.scalars(
                update(OtpChallenge)
                .where(OtpChallenge.active_key == challenge.active_key)
                .values(active_key=None, invalidated_at=invalidated_at)
                .returning(OtpChallenge.id)
            )
        )
        await session.flush()
        session.add(challenge)
        await session.flush()
        return invalidated_ids

    async def get_active_challenge(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        purpose: OtpPurpose,
    ) -> OtpChallenge | None:
        active_key = self.active_challenge_key(user_id, purpose)
        return await session.scalar(
            select(OtpChallenge).where(OtpChallenge.active_key == active_key).with_for_update()
        )

    async def create_refresh_session(
        self,
        session: AsyncSession,
        refresh_session: RefreshSession,
    ) -> RefreshSession:
        session.add(refresh_session)
        await session.flush()
        return refresh_session

    async def get_refresh_session(
        self,
        session: AsyncSession,
        token_digest: str,
    ) -> RefreshSession | None:
        return await session.scalar(
            select(RefreshSession)
            .where(RefreshSession.token_digest == token_digest)
            .options(selectinload(RefreshSession.user))
            .with_for_update()
        )

    async def revoke_session_family(
        self,
        session: AsyncSession,
        *,
        family_id: str,
        revoked_at: datetime,
    ) -> None:
        await session.execute(
            update(RefreshSession)
            .where(
                RefreshSession.family_id == family_id,
                RefreshSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )

    async def revoke_user_sessions(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        revoked_at: datetime,
    ) -> None:
        await session.execute(
            update(RefreshSession)
            .where(
                RefreshSession.user_id == user_id,
                RefreshSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )

    async def invalidate_user_challenges(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        invalidated_at: datetime,
    ) -> None:
        await session.execute(
            update(OtpChallenge)
            .where(
                OtpChallenge.user_id == user_id,
                OtpChallenge.consumed_at.is_(None),
                OtpChallenge.invalidated_at.is_(None),
            )
            .values(active_key=None, invalidated_at=invalidated_at)
        )

    async def active_session_count(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        now: datetime,
    ) -> int:
        count = await session.scalar(
            select(func.count())
            .select_from(RefreshSession)
            .where(
                RefreshSession.user_id == user_id,
                RefreshSession.revoked_at.is_(None),
                RefreshSession.expires_at > now,
            )
        )
        return int(count or 0)

    async def revoke_oldest_active_sessions(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        now: datetime,
        count: int,
    ) -> None:
        if count <= 0:
            return
        session_ids = list(
            await session.scalars(
                select(RefreshSession.id)
                .where(
                    RefreshSession.user_id == user_id,
                    RefreshSession.revoked_at.is_(None),
                    RefreshSession.expires_at > now,
                )
                .order_by(RefreshSession.created_at, RefreshSession.id)
                .limit(count)
            )
        )
        if session_ids:
            await session.execute(
                update(RefreshSession)
                .where(RefreshSession.id.in_(session_ids))
                .values(revoked_at=now)
            )

    async def user_has_permission(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        permission: PermissionCode,
    ) -> bool:
        match = await session.scalar(
            select(Permission.id)
            .select_from(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(RolePermission, RolePermission.role_id == UserRole.role_id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(
                User.id == user_id,
                User.status == UserStatus.ACTIVE.value,
                Permission.code == permission.value,
            )
            .limit(1)
        )
        return match is not None

    async def get_user_access(
        self,
        session: AsyncSession,
        *,
        user_id: int,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        rows = (
            await session.execute(
                select(Role.name, Permission.code)
                .select_from(User)
                .join(UserRole, UserRole.user_id == User.id)
                .join(Role, Role.id == UserRole.role_id)
                .outerjoin(RolePermission, RolePermission.role_id == Role.id)
                .outerjoin(Permission, Permission.id == RolePermission.permission_id)
                .where(
                    User.id == user_id,
                    User.status == UserStatus.ACTIVE.value,
                )
                .order_by(Role.name, Permission.code)
            )
        ).all()
        roles = tuple(sorted({role_name for role_name, _permission in rows}))
        permissions = tuple(
            sorted({permission for _role_name, permission in rows if permission is not None})
        )
        return roles, permissions

    async def get_role(self, session: AsyncSession, role: RoleName) -> Role | None:
        return await session.scalar(select(Role).where(Role.name == role.value))

    async def user_has_role(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        role_id: int,
    ) -> bool:
        link = await session.get(UserRole, (user_id, role_id))
        return link is not None

    async def assign_role(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        role_id: int,
    ) -> None:
        if not await self.user_has_role(
            session,
            user_id=user_id,
            role_id=role_id,
        ):
            session.add(UserRole(user_id=user_id, role_id=role_id))
            await session.flush()

    async def add_audit_event(
        self,
        session: AsyncSession,
        *,
        event_type: str,
        actor_user_id: int | None = None,
        subject_user_id: int | None = None,
        session_id: str | None = None,
        ip_digest: str | None = None,
        user_agent: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        session.add(
            SecurityAuditEvent(
                event_type=event_type,
                actor_user_id=actor_user_id,
                subject_user_id=subject_user_id,
                session_id=session_id,
                ip_digest=ip_digest,
                user_agent=(user_agent or "")[:512] or None,
                details=details or {},
            )
        )

    async def ensure_system_authorization(self, session: AsyncSession) -> None:
        roles = {role.name: role for role in await session.scalars(select(Role))}
        permissions = {
            permission.code: permission for permission in await session.scalars(select(Permission))
        }
        for role_name in RoleName:
            if role_name.value not in roles:
                role = Role(name=role_name.value, description=role_name.value, is_system=True)
                session.add(role)
                roles[role_name.value] = role
        for permission_code in PermissionCode:
            if permission_code.value not in permissions:
                permission = Permission(
                    code=permission_code.value,
                    description=permission_code.value,
                )
                session.add(permission)
                permissions[permission_code.value] = permission
        await session.flush()

        existing_result = await session.execute(
            select(RolePermission.role_id, RolePermission.permission_id)
        )
        existing_pairs = set(existing_result.tuples())
        for role_name, permission_codes in SYSTEM_ROLE_PERMISSIONS.items():
            role = roles[role_name.value]
            for permission_code in permission_codes:
                permission = permissions[permission_code.value]
                pair = (role.id, permission.id)
                if pair not in existing_pairs:
                    session.add(RolePermission(role_id=role.id, permission_id=permission.id))
                    existing_pairs.add(pair)
        await session.flush()

    @staticmethod
    def active_challenge_key(user_id: int, purpose: OtpPurpose) -> str:
        return f"{purpose.value}:{user_id}"
