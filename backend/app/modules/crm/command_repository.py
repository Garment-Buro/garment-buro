from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.command_models import (
    CrmAssignmentEvent,
    CrmStaffCommand,
    CrmStaffCommandStatus,
)


class CrmCommandIdempotencyConflictError(ValueError):
    pass


class CrmCommandInProgressError(RuntimeError):
    pass


class CrmCommandRepository:
    async def acquire(
        self,
        session: AsyncSession,
        *,
        idempotency_key_sha256: str,
        command_sha256: str,
        command_type: str,
        target_id: int,
        actor_user_id: int,
        now: datetime,
    ) -> tuple[CrmStaffCommand, bool]:
        values = {
            "idempotency_key_sha256": idempotency_key_sha256,
            "command_sha256": command_sha256,
            "command_type": command_type,
            "target_id": target_id,
            "status": CrmStaffCommandStatus.PROCESSING.value,
            "actor_user_id": actor_user_id,
            "created_at": now,
        }
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = postgresql_insert(CrmStaffCommand).values(**values)
        elif dialect_name == "sqlite":
            statement = sqlite_insert(CrmStaffCommand).values(**values)
        else:
            raise RuntimeError("CRM staff commands require PostgreSQL or SQLite")
        inserted_id = await session.scalar(
            statement.on_conflict_do_nothing(
                index_elements=[CrmStaffCommand.idempotency_key_sha256]
            ).returning(CrmStaffCommand.id)
        )
        command = await session.scalar(
            select(CrmStaffCommand)
            .where(CrmStaffCommand.idempotency_key_sha256 == idempotency_key_sha256)
            .with_for_update()
        )
        if command is None:
            raise RuntimeError("CRM staff command could not be acquired")
        if command.command_sha256 != command_sha256:
            raise CrmCommandIdempotencyConflictError(
                "CRM idempotency key was already used for another command"
            )
        replayed = inserted_id is None
        if replayed and command.status != CrmStaffCommandStatus.COMPLETED.value:
            raise CrmCommandInProgressError("CRM command is still processing")
        return command, replayed

    @staticmethod
    async def complete(
        session: AsyncSession,
        command: CrmStaffCommand,
        *,
        result_version: int,
        now: datetime,
    ) -> None:
        command.status = CrmStaffCommandStatus.COMPLETED.value
        command.result_version = result_version
        command.completed_at = now
        await session.flush()

    @staticmethod
    async def add_assignment_event(
        session: AsyncSession,
        event: CrmAssignmentEvent,
    ) -> None:
        session.add(event)
        await session.flush()
