from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.payments.models import PaymentAttempt, PaymentOperation


class PaymentOperationRepository:
    async def get_by_client_digest(
        self,
        session: AsyncSession,
        *,
        client_key_digest_sha256: str,
        for_update: bool = False,
    ) -> PaymentOperation | None:
        statement = (
            select(PaymentOperation)
            .where(PaymentOperation.client_key_digest_sha256 == client_key_digest_sha256)
            .options(selectinload(PaymentOperation.attempt).selectinload(PaymentAttempt.payment))
        )
        if for_update:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def get_by_attempt(
        self,
        session: AsyncSession,
        *,
        payment_attempt_id: int,
        for_update: bool = False,
    ) -> PaymentOperation | None:
        statement = (
            select(PaymentOperation)
            .where(
                PaymentOperation.payment_attempt_id == payment_attempt_id,
            )
            .options(selectinload(PaymentOperation.attempt).selectinload(PaymentAttempt.payment))
        )
        if for_update:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def get_for_update(
        self,
        session: AsyncSession,
        *,
        operation_id: int,
    ) -> PaymentOperation | None:
        return await session.scalar(
            select(PaymentOperation)
            .where(PaymentOperation.id == operation_id)
            .options(selectinload(PaymentOperation.attempt).selectinload(PaymentAttempt.payment))
            .with_for_update()
        )

    async def add(
        self,
        session: AsyncSession,
        operation: PaymentOperation,
    ) -> tuple[PaymentOperation, bool]:
        try:
            async with session.begin_nested():
                session.add(operation)
                await session.flush()
            return operation, True
        except IntegrityError:
            existing = await self.get_by_client_digest(
                session,
                client_key_digest_sha256=operation.client_key_digest_sha256,
                for_update=True,
            )
            if existing is None:
                existing = await self.get_by_attempt(
                    session,
                    payment_attempt_id=operation.payment_attempt_id,
                    for_update=True,
                )
            if existing is None:
                raise
            return existing, False
