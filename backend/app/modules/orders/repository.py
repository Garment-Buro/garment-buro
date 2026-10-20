from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import case, exists, func, literal, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Load, selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.modules.delivery.models import CdekShipment
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
from app.modules.orders.workflow_models import OrderWorkflow
from app.modules.payments.models import Payment, PaymentAttempt, PaymentEvent


@dataclass(frozen=True)
class OrderHistoryRecord:
    id: int
    total_price: Decimal
    created_at: datetime
    status: str
    payment_status: str
    workflow_state: str | None
    cdek_number: str | None
    cdek_status: str | None


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
        email_normalized: str,
        identifier_digest: str,
    ) -> None:
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            statement = postgresql_insert(LegacyOrderClaim)
        elif dialect_name == "sqlite":
            statement = sqlite_insert(LegacyOrderClaim)
        else:
            raise RuntimeError("Legacy order claims require PostgreSQL or SQLite")
        unclaimed = (
            select(
                literal(user_id),
                Order.id,
                literal(LegacyOrderClaimSource.VERIFIED_EMAIL.value),
                literal(identifier_digest),
            )
            .join(LegacyOrderImport, LegacyOrderImport.order_id == Order.id)
            .where(
                Order.email_normalized == email_normalized,
                ~exists(
                    select(LegacyOrderClaim.id).where(LegacyOrderClaim.legacy_order_id == Order.id)
                ),
            )
        )
        await session.execute(
            statement.from_select(
                ["user_id", "legacy_order_id", "source", "identifier_digest"],
                unclaimed,
            ).on_conflict_do_nothing(
                index_elements=[LegacyOrderClaim.legacy_order_id],
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
    async def list_owned_summaries(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        limit: int,
        before_id: int | None,
    ) -> list[OrderHistoryRecord]:
        rows = await session.execute(
            self.history_statement(user_id=user_id, limit=limit, before_id=before_id)
        )
        return [OrderHistoryRecord(**row) for row in rows.mappings()]

    @staticmethod
    def history_statement(*, user_id: int, limit: int, before_id: int | None):
        # Bound each indexed owner branch before merging. OR + correlated EXISTS
        # over all orders can otherwise scan an unrelated account's entire history.
        # Keep the owner in the ordered range. With only owner = X / id < cursor,
        # PostgreSQL can choose the global primary key and filter thousands of
        # foreign rows when this owner's branch is exhausted (verified by EXPLAIN).
        direct_key = tuple_(Order.user_id, Order.id)
        claimed_key = tuple_(LegacyOrderClaim.user_id, LegacyOrderClaim.legacy_order_id)
        direct = select(Order.id).where(direct_key >= (user_id, 1))
        claimed = select(LegacyOrderClaim.legacy_order_id.label("id")).where(
            claimed_key >= (user_id, 1)
        )
        if before_id is not None:
            direct = direct.where(direct_key < (user_id, before_id))
            claimed = claimed.where(claimed_key < (user_id, before_id))
        else:
            direct = direct.where(direct_key <= (user_id, 2147483647))
            claimed = claimed.where(claimed_key <= (user_id, 2147483647))
        direct = direct.order_by(Order.user_id.desc(), Order.id.desc()).limit(limit).subquery()
        claimed = (
            claimed.order_by(
                LegacyOrderClaim.user_id.desc(), LegacyOrderClaim.legacy_order_id.desc()
            )
            .limit(limit)
            .subquery()
        )
        candidates = select(direct.c.id).union(select(claimed.c.id)).subquery()
        page = select(candidates.c.id).order_by(candidates.c.id.desc()).limit(limit).subquery()
        return (
            select(
                Order.id,
                Order.total_price,
                Order.created_at,
                Order.status,
                Order.payment_status,
                OrderWorkflow.state.label("workflow_state"),
                case(
                    (CdekShipment.id.is_not(None), CdekShipment.provider_cdek_number),
                    else_=LegacyOrderImport.delivery_provider_number,
                ).label("cdek_number"),
                case(
                    (CdekShipment.id.is_not(None), CdekShipment.provider_status_code),
                    else_=LegacyOrderImport.delivery_provider_status,
                ).label("cdek_status"),
            )
            .join(page, page.c.id == Order.id)
            .outerjoin(OrderWorkflow, OrderWorkflow.order_id == Order.id)
            .outerjoin(CdekShipment, CdekShipment.order_id == Order.id)
            .outerjoin(LegacyOrderImport, LegacyOrderImport.order_id == Order.id)
            .order_by(Order.id.desc())
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
    def _read_options() -> tuple[Load, ...]:
        return (
            selectinload(Order.items),
            selectinload(Order.legacy_import),
            selectinload(Order.workflow),
            selectinload(Order.cdek_shipment),
        )
