from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Load, selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.modules.inventory.models import InventoryReservation
from app.modules.orders.models import (
    LegacyOrderClaim,
    LegacyOrderClaimSource,
    LegacyOrderImport,
    Order,
    OrderCreationRequest,
    OrderGuestAccess,
    OrderItem,
    OrderMigrationRun,
    OrderStatusHistory,
)
from app.modules.payments.models import Payment, PaymentAttempt, PaymentEvent


class OrderRepository:
    async def acquire_creation_request(
        self,
        session: AsyncSession,
        *,
        key_digest_sha256: str,
        request_fingerprint_sha256: str,
    ) -> OrderCreationRequest:
        values = {
            "key_digest_sha256": key_digest_sha256,
            "request_fingerprint_sha256": request_fingerprint_sha256,
            "order_id": None,
        }
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = postgresql_insert(OrderCreationRequest).values(**values)
        elif dialect_name == "sqlite":
            statement = sqlite_insert(OrderCreationRequest).values(**values)
        else:
            raise RuntimeError("Order creation requires PostgreSQL or SQLite")
        await session.execute(
            statement.on_conflict_do_nothing(
                index_elements=[OrderCreationRequest.key_digest_sha256],
            )
        )
        request = await session.scalar(
            select(OrderCreationRequest)
            .where(OrderCreationRequest.key_digest_sha256 == key_digest_sha256)
            .with_for_update()
        )
        if request is None:
            raise RuntimeError("Order creation request could not be acquired")
        return request

    async def get_order(self, session: AsyncSession, order_id: int) -> Order | None:
        return await session.scalar(
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_history),
            )
        )

    async def get_order_for_update(
        self,
        session: AsyncSession,
        *,
        order_id: int,
    ) -> Order | None:
        return await session.scalar(select(Order).where(Order.id == order_id).with_for_update())

    @staticmethod
    async def add_order(session: AsyncSession, order: Order) -> None:
        session.add(order)
        await session.flush()


class LegacyOrderClaimRepository:
    async def claim_verified_email_orders(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        legacy_order_ids: Sequence[int],
        identifier_digest: str,
    ) -> None:
        values = [
            {
                "user_id": user_id,
                "legacy_order_id": order_id,
                "source": LegacyOrderClaimSource.VERIFIED_EMAIL.value,
                "identifier_digest": identifier_digest,
            }
            for order_id in sorted(set(legacy_order_ids))
            if order_id > 0
        ]
        if not values:
            return
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = postgresql_insert(LegacyOrderClaim).values(values)
        elif dialect_name == "sqlite":
            statement = sqlite_insert(LegacyOrderClaim).values(values)
        else:
            raise RuntimeError("Legacy order claims require PostgreSQL or SQLite")
        await session.execute(
            statement.on_conflict_do_nothing(
                index_elements=[LegacyOrderClaim.legacy_order_id],
            )
        )

    async def list_claimed_order_ids(
        self,
        session: AsyncSession,
        *,
        user_id: int,
    ) -> list[int]:
        return list(
            await session.scalars(
                select(LegacyOrderClaim.legacy_order_id)
                .where(LegacyOrderClaim.user_id == user_id)
                .order_by(LegacyOrderClaim.legacy_order_id.desc())
            )
        )


class OrderMigrationRepository:
    async def get_run(
        self,
        session: AsyncSession,
        *,
        fingerprint_sha256: str,
    ) -> OrderMigrationRun | None:
        return await session.scalar(
            select(OrderMigrationRun).where(
                OrderMigrationRun.fingerprint_sha256 == fingerprint_sha256
            )
        )

    async def target_counts(self, session: AsyncSession) -> dict[str, int]:
        models = {
            "orders": Order,
            "order_items": OrderItem,
            "order_status_history": OrderStatusHistory,
            "order_creation_requests": OrderCreationRequest,
            "inventory_reservations": InventoryReservation,
            "order_guest_access": OrderGuestAccess,
            "payments": Payment,
            "payment_attempts": PaymentAttempt,
            "payment_events": PaymentEvent,
            "legacy_order_imports": LegacyOrderImport,
            "order_migration_runs": OrderMigrationRun,
        }
        return {
            name: int(await session.scalar(select(func.count()).select_from(model)) or 0)
            for name, model in models.items()
        }


class TargetOrderReadRepository:
    async def find_imported_ids_by_verified_email(
        self,
        session: AsyncSession,
        *,
        email_normalized: str,
    ) -> list[int]:
        return list(
            await session.scalars(
                select(Order.id)
                .join(LegacyOrderImport, LegacyOrderImport.order_id == Order.id)
                .where(Order.email_normalized == email_normalized)
                .order_by(Order.id)
            )
        )

    async def list_owned(
        self,
        session: AsyncSession,
        *,
        user_id: int,
    ) -> list[Order]:
        return list(
            await session.scalars(
                select(Order)
                .where(self._owned_expression(user_id))
                .options(*self._read_options())
                .order_by(Order.id.desc())
            )
        )

    async def get_owned(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        user_id: int,
    ) -> Order | None:
        return await session.scalar(
            select(Order)
            .where(Order.id == order_id, self._owned_expression(user_id))
            .options(*self._read_options())
        )

    async def list_all(
        self,
        session: AsyncSession,
        *,
        limit: int,
        offset: int,
    ) -> list[Order]:
        return list(
            await session.scalars(
                select(Order)
                .options(*self._read_options())
                .order_by(Order.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )

    async def get(self, session: AsyncSession, *, order_id: int) -> Order | None:
        return await session.scalar(
            select(Order).where(Order.id == order_id).options(*self._read_options())
        )

    async def get_by_guest_digest(
        self,
        session: AsyncSession,
        *,
        token_digest_sha256: str,
        now: datetime,
    ) -> Order | None:
        return await session.scalar(
            select(Order)
            .join(OrderGuestAccess, OrderGuestAccess.order_id == Order.id)
            .where(
                OrderGuestAccess.token_digest_sha256 == token_digest_sha256,
                OrderGuestAccess.revoked_at.is_(None),
                OrderGuestAccess.expires_at > now,
            )
            .options(*self._read_options())
        )

    async def get_guest_access_for_update(
        self,
        session: AsyncSession,
        *,
        order_id: int,
    ) -> OrderGuestAccess | None:
        return await session.scalar(
            select(OrderGuestAccess).where(OrderGuestAccess.order_id == order_id).with_for_update()
        )

    async def is_legacy_import(
        self,
        session: AsyncSession,
        *,
        order_id: int,
    ) -> bool:
        return bool(
            await session.scalar(
                select(LegacyOrderImport.id).where(LegacyOrderImport.order_id == order_id)
            )
        )

    @staticmethod
    async def add_guest_access(
        session: AsyncSession,
        access: OrderGuestAccess,
    ) -> None:
        session.add(access)
        await session.flush()

    @staticmethod
    def _owned_expression(user_id: int) -> ColumnElement[bool]:
        claimed = exists(
            select(LegacyOrderClaim.id).where(
                LegacyOrderClaim.legacy_order_id == Order.id,
                LegacyOrderClaim.user_id == user_id,
            )
        )
        return or_(Order.user_id == user_id, claimed)

    @staticmethod
    def _read_options() -> tuple[Load, Load]:
        return (
            selectinload(Order.items),
            selectinload(Order.legacy_import),
        )
