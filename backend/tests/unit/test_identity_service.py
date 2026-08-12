from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.identity.exceptions import (
    EmailAlreadyUsedError,
    InvalidOtpError,
    InvalidSessionError,
    OtpRateLimitError,
    PermissionDeniedError,
    RefreshTokenReuseError,
)
from app.modules.identity.models import (
    SYSTEM_ROLE_PERMISSIONS,
    OtpChallenge,
    PermissionCode,
    RefreshSession,
    Role,
    RoleName,
    SecurityAuditEvent,
    User,
    UserStatus,
)
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.security import OtpSecurity, TokenSecurity
from app.modules.identity.service import IdentityService, ProfileChanges


class DeterministicOtpSecurity(OtpSecurity):
    def generate_code(self) -> str:
        return "1234"

    @staticmethod
    def generate_salt() -> str:
        return "a" * 32


def test_identity_service_enforces_otp_sessions_and_permissions() -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
        )
        database = DatabaseManager(settings)
        repository = IdentityRepository()
        service = IdentityService(
            DeterministicOtpSecurity("p" * 32),
            TokenSecurity("j" * 32),
            repository=repository,
        )
        now = datetime.now(timezone.utc).replace(microsecond=0)

        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with database.session() as session:
            await repository.ensure_system_authorization(session)
            await session.commit()

        async with database.session() as session:
            issued = await service.request_login_otp(
                session,
                email="Customer@Example.TEST",
                now=now,
                client_ip="192.0.2.10",
                user_agent="PWA contract",
            )
            await session.commit()
        assert issued.code == "1234"
        assert issued.target_email == "Customer@Example.TEST"

        async with database.session() as session:
            challenge = await session.scalar(select(OtpChallenge))
            assert challenge is not None
            assert challenge.code_digest != issued.code
            assert challenge.code_salt == "a" * 32
            assert challenge.requested_ip_digest != "192.0.2.10"

        with pytest.raises(OtpRateLimitError) as rate_limit:
            async with database.session() as session:
                await service.request_login_otp(
                    session,
                    email="customer@example.test",
                    now=now + timedelta(seconds=30),
                    client_ip="192.0.2.10",
                )
        assert 29 <= rate_limit.value.retry_after_seconds <= 31

        with pytest.raises(InvalidOtpError):
            async with database.session() as session:
                await service.verify_login_otp(
                    session,
                    email="customer@example.test",
                    code="9999",
                    now=now + timedelta(seconds=31),
                    client_ip="192.0.2.10",
                )
        async with database.session() as session:
            challenge = await session.scalar(select(OtpChallenge))
            assert challenge is not None
            assert challenge.attempts_count == 1

        async with database.session() as session:
            tokens = await service.verify_login_otp(
                session,
                email="customer@example.test",
                code="1234",
                now=now + timedelta(seconds=32),
                client_ip="192.0.2.10",
                user_agent="PWA contract",
            )
            await session.commit()
        claims = service.token_security.decode_access_token(tokens.access_token)
        assert claims.user_id == tokens.user.id
        assert claims.session_id == tokens.session_id
        assert tokens.refresh_token not in service.token_security.digest_refresh_token(
            tokens.refresh_token
        )

        async with database.session() as session:
            await service.require_permission(
                session,
                user_id=tokens.user.id,
                permission=PermissionCode.PROFILE_READ_OWN,
            )
            with pytest.raises(PermissionDeniedError):
                await service.require_permission(
                    session,
                    user_id=tokens.user.id,
                    permission=PermissionCode.CATALOG_WRITE,
                )

            access = await service.get_access_snapshot(
                session,
                user_id=tokens.user.id,
            )
            assert access.roles == (RoleName.CUSTOMER.value,)
            assert set(access.permissions) == {
                permission.value for permission in SYSTEM_ROLE_PERMISSIONS[RoleName.CUSTOMER]
            }

            manager_role = await repository.get_role(session, RoleName.MANAGER)
            assert manager_role is not None
            await repository.assign_role(
                session,
                user_id=tokens.user.id,
                role_id=manager_role.id,
            )
            access = await service.get_access_snapshot(
                session,
                user_id=tokens.user.id,
            )
            assert access.roles == (
                RoleName.CUSTOMER.value,
                RoleName.MANAGER.value,
            )
            assert set(access.permissions) == {
                permission.value for permission in SYSTEM_ROLE_PERMISSIONS[RoleName.MANAGER]
            }

        async with database.session() as session:
            rotated = await service.rotate_refresh_token(
                session,
                refresh_token=tokens.refresh_token,
                now=now + timedelta(minutes=1),
                client_ip="192.0.2.10",
                user_agent="PWA contract",
            )
            await session.commit()
        assert rotated.refresh_token != tokens.refresh_token
        assert rotated.session_id != tokens.session_id

        with pytest.raises(RefreshTokenReuseError):
            async with database.session() as session:
                await service.rotate_refresh_token(
                    session,
                    refresh_token=tokens.refresh_token,
                    now=now + timedelta(minutes=2),
                    client_ip="192.0.2.99",
                )

        async with database.session() as session:
            family_sessions = list(
                await session.scalars(
                    select(RefreshSession).where(
                        RefreshSession.family_id
                        == (
                            select(RefreshSession.family_id)
                            .where(RefreshSession.session_id == tokens.session_id)
                            .scalar_subquery()
                        )
                    )
                )
            )
            assert len(family_sessions) == 2
            assert all(item.revoked_at is not None for item in family_sessions)
            event_types = set(await session.scalars(select(SecurityAuditEvent.event_type)))
        assert {
            "auth.otp_requested",
            "auth.otp_failed",
            "auth.login_succeeded",
            "auth.refresh_rotated",
            "auth.refresh_reuse_detected",
        } <= event_types

        async with database.session() as session:
            roles = {role.name for role in await session.scalars(select(Role))}
        assert roles == {role.value for role in RoleName}
        await database.shutdown()

    asyncio.run(scenario())


def test_otp_attempt_limit_is_durable_across_failed_requests() -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
        )
        database = DatabaseManager(settings)
        repository = IdentityRepository()
        service = IdentityService(
            DeterministicOtpSecurity("p" * 32),
            TokenSecurity("j" * 32),
            repository=repository,
        )
        now = datetime.now(timezone.utc).replace(microsecond=0)
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with database.session() as session:
            await repository.ensure_system_authorization(session)
            await session.commit()
        async with database.session() as session:
            await service.request_login_otp(
                session,
                email="attempts@example.test",
                now=now,
            )
            await session.commit()

        for attempt in range(1, 6):
            with pytest.raises(InvalidOtpError):
                async with database.session() as session:
                    await service.verify_login_otp(
                        session,
                        email="attempts@example.test",
                        code="0000",
                        now=now + timedelta(seconds=attempt),
                    )

        with pytest.raises(InvalidOtpError):
            async with database.session() as session:
                await service.verify_login_otp(
                    session,
                    email="attempts@example.test",
                    code="1234",
                    now=now + timedelta(seconds=6),
                )

        async with database.session() as session:
            challenge = await session.scalar(select(OtpChallenge))
            failed_events = list(
                await session.scalars(
                    select(SecurityAuditEvent).where(
                        SecurityAuditEvent.event_type == "auth.otp_failed"
                    )
                )
            )
        assert challenge is not None
        assert challenge.attempts_count == 5
        assert challenge.active_key is None
        assert challenge.invalidated_at is not None
        assert len(failed_events) == 5
        await database.shutdown()

    asyncio.run(scenario())


def test_profile_email_change_access_resolution_and_soft_delete() -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url="sqlite+aiosqlite:///:memory:",
        )
        database = DatabaseManager(settings)
        repository = IdentityRepository()
        service = IdentityService(
            DeterministicOtpSecurity("p" * 32),
            TokenSecurity("j" * 32),
            repository=repository,
        )
        now = datetime.now(timezone.utc).replace(microsecond=0)
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with database.session() as session:
            await repository.ensure_system_authorization(session)
            await session.commit()

        async with database.session() as session:
            await service.request_login_otp(
                session,
                email="profile@example.test",
                now=now,
            )
            await session.commit()
        async with database.session() as session:
            tokens = await service.verify_login_otp(
                session,
                email="profile@example.test",
                code="1234",
                now=now + timedelta(seconds=1),
            )
            await session.commit()

        async with database.session() as session:
            resolved = await service.resolve_access_token(
                session,
                access_token=tokens.access_token,
                now=now + timedelta(seconds=2),
                allow_legacy=False,
            )
        assert resolved.id == tokens.user.id

        legacy_token = jwt.encode(
            {
                "sub": str(tokens.user.id),
                "exp": now + timedelta(minutes=5),
            },
            "j" * 32,
            algorithm="HS256",
        )
        async with database.session() as session:
            migrated = await service.migrate_legacy_access_token(
                session,
                access_token=legacy_token,
                now=now + timedelta(seconds=2),
            )
            await session.commit()
        assert migrated.session_id != tokens.session_id
        with pytest.raises(InvalidSessionError):
            async with database.session() as session:
                await service.migrate_legacy_access_token(
                    session,
                    access_token=tokens.access_token,
                    now=now + timedelta(seconds=2),
                )

        async with database.session() as session:
            issued = await service.request_email_change_otp(
                session,
                user_id=tokens.user.id,
                email="changed@example.test",
                now=now + timedelta(seconds=3),
            )
            await session.commit()
        assert issued.challenge_id > 0
        with pytest.raises(InvalidOtpError):
            async with database.session() as session:
                await service.verify_email_change_otp(
                    session,
                    user_id=tokens.user.id,
                    email="changed@example.test",
                    code="9999",
                    now=now + timedelta(seconds=4),
                )
        async with database.session() as session:
            changed = await service.verify_email_change_otp(
                session,
                user_id=tokens.user.id,
                email="changed@example.test",
                code="1234",
                now=now + timedelta(seconds=5),
            )
            await session.commit()
        assert changed.user.email_normalized == "changed@example.test"

        async with database.session() as session:
            other = await repository.create_customer(
                session,
                email="used@example.test",
                email_normalized="used@example.test",
            )
            await session.commit()
        with pytest.raises(EmailAlreadyUsedError):
            async with database.session() as session:
                await service.request_email_change_otp(
                    session,
                    user_id=tokens.user.id,
                    email=other.email or "",
                    now=now + timedelta(seconds=6),
                )

        async with database.session() as session:
            updated = await service.update_profile(
                session,
                user_id=tokens.user.id,
                changes=ProfileChanges(
                    first_name="Анна",
                    provided_fields=frozenset({"first_name"}),
                ),
                now=now + timedelta(seconds=7),
            )
            await session.commit()
        assert updated.first_name == "Анна"
        assert updated.email == "changed@example.test"

        async with database.session() as session:
            await service.delete_profile(
                session,
                user_id=tokens.user.id,
                now=now + timedelta(seconds=8),
            )
            await session.commit()
        with pytest.raises(InvalidSessionError):
            async with database.session() as session:
                await service.resolve_access_token(
                    session,
                    access_token=tokens.access_token,
                    now=now + timedelta(seconds=9),
                    allow_legacy=False,
                )
        async with database.session() as session:
            deleted = await session.get(User, tokens.user.id)
        assert deleted is not None
        assert deleted.status == UserStatus.DELETED.value
        assert deleted.email is None
        assert deleted.phone is None
        await database.shutdown()

    asyncio.run(scenario())
