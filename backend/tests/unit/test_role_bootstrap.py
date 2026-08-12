from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.identity.models import (
    RoleName,
    SecurityAuditEvent,
    User,
    UserStatus,
)
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.role_bootstrap import RoleBootstrapError, RoleBootstrapService


def test_role_bootstrap_requires_reviewed_user_id_and_audits_once(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env=AppEnvironment.TEST,
            database_enabled=True,
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'roles.db'}",
        )
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                repository = IdentityRepository()
                await repository.ensure_system_authorization(session)
                session.add(
                    User(
                        id=7,
                        email="Manager@Example.TEST",
                        email_normalized="manager@example.test",
                        status=UserStatus.ACTIVE.value,
                    )
                )
                await session.commit()

            service = RoleBootstrapService()
            async with database.session() as session:
                plan = await service.inspect(
                    session,
                    email="manager@example.test",
                    role=RoleName.MANAGER,
                )
                assert not plan.already_assigned
                with pytest.raises(RoleBootstrapError, match="Expected user ID"):
                    await service.apply(session, plan=plan, expected_user_id=8)
                await session.rollback()

            async with database.session() as session:
                plan = await service.inspect(
                    session,
                    email="manager@example.test",
                    role=RoleName.MANAGER,
                )
                applied = await service.apply(session, plan=plan, expected_user_id=7)
                await session.commit()
                assert applied.already_assigned

            async with database.session() as session:
                repeated = await service.inspect(
                    session,
                    email="manager@example.test",
                    role=RoleName.MANAGER,
                )
                await service.apply(session, plan=repeated, expected_user_id=7)
                await session.commit()
                events = list(
                    await session.scalars(
                        select(SecurityAuditEvent).where(
                            SecurityAuditEvent.event_type == "authorization.role_bootstrapped"
                        )
                    )
                )
                assert len(events) == 1
                assert events[0].details == {"role": "manager"}
        finally:
            await database.shutdown()

    asyncio.run(scenario())
