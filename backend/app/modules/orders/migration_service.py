from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orders.migration_types import (
    InvalidOrderMigrationPlanError,
    OrderMigrationPlan,
    OrderMigrationResult,
    TargetOrderStoreNotEmptyError,
)
from app.modules.orders.models import (
    LegacyOrderImport,
    Order,
    OrderItem,
    OrderMigrationRun,
    OrderStatusHistory,
)
from app.modules.orders.repository import OrderMigrationRepository


class OrderMigrationService:
    def __init__(
        self,
        repository: OrderMigrationRepository | None = None,
    ) -> None:
        self.repository = repository or OrderMigrationRepository()

    async def apply(
        self,
        session: AsyncSession,
        plan: OrderMigrationPlan,
    ) -> OrderMigrationResult:
        if not plan.valid or plan.source_orders_count != len(plan.orders):
            raise InvalidOrderMigrationPlanError("Order migration plan contains validation errors")
        existing_run = await self.repository.get_run(
            session,
            fingerprint_sha256=plan.fingerprint,
        )
        if existing_run is not None:
            await self._verify_existing_run(session, existing_run)
            return self._result(existing_run)

        counts = await self.repository.target_counts(session)
        if any(counts.values()):
            rendered = ", ".join(f"{name}={count}" for name, count in counts.items())
            raise TargetOrderStoreNotEmptyError(
                f"Target order store must be empty before import ({rendered})"
            )

        for record in plan.orders:
            order = Order(
                id=record.id,
                user_id=None,
                email=record.email,
                email_normalized=record.email_normalized,
                phone=record.phone,
                first_name=record.first_name,
                last_name=record.last_name,
                patronymic=record.patronymic,
                delivery_city=record.delivery_city,
                delivery_method=record.delivery_method,
                delivery_address=record.delivery_address,
                cdek_point_code=record.cdek_point_code,
                payment_method=record.payment_method,
                items_subtotal=record.items_subtotal,
                delivery_price=record.delivery_price,
                total_price=record.total_price,
                currency="RUB",
                status=record.status,
                payment_status=record.payment_status,
                version=1,
                request_fingerprint_sha256=record.source_row_sha256,
                created_at=record.created_at,
                updated_at=record.created_at,
            )
            order.items.extend(
                OrderItem(
                    client_item_id=item.client_item_id,
                    product_id_snapshot=item.product_id,
                    variant_id_snapshot=item.variant_id,
                    sku_snapshot=item.sku,
                    title_snapshot=item.title,
                    unit_price=item.unit_price,
                    quantity=item.quantity,
                    line_total=item.line_total,
                    image_url_snapshot=item.image_url,
                    size_snapshot=item.size,
                    color_snapshot=item.color,
                    customization_snapshot=item.customization,
                    sort_order=item.sort_order,
                    created_at=record.created_at,
                )
                for item in record.items
            )
            order.status_history.append(
                OrderStatusHistory(
                    version=1,
                    from_status=None,
                    to_status=record.status,
                    reason_code="legacy.imported",
                    actor_user_id=None,
                    details={"source_order_id": record.id},
                    created_at=record.created_at,
                )
            )
            order.legacy_import = LegacyOrderImport(
                source_order_id=record.id,
                source_row_sha256=record.source_row_sha256,
                raw_cart_items=record.raw_cart_items,
                legacy_total_price=record.total_price,
                legacy_status=record.legacy_status,
                legacy_payment_status=record.legacy_payment_status,
                payment_provider_id=record.payment_provider_id,
                delivery_provider_uuid=record.delivery_provider_uuid,
                delivery_provider_number=record.delivery_provider_number,
                delivery_provider_status=record.delivery_provider_status,
            )
            session.add(order)

        run = OrderMigrationRun(
            fingerprint_sha256=plan.fingerprint,
            orders_count=len(plan.orders),
            items_count=plan.items_count,
            payment_references_count=plan.payment_references_count,
            delivery_references_count=plan.delivery_references_count,
        )
        session.add(run)
        await session.flush()
        await self._synchronize_postgresql_sequences(session)
        return self._result(run)

    @staticmethod
    def _result(run: OrderMigrationRun) -> OrderMigrationResult:
        return OrderMigrationResult(
            fingerprint_sha256=run.fingerprint_sha256,
            orders=run.orders_count,
            items=run.items_count,
            payment_references=run.payment_references_count,
            delivery_references=run.delivery_references_count,
        )

    async def _verify_existing_run(
        self,
        session: AsyncSession,
        run: OrderMigrationRun,
    ) -> None:
        counts = await self.repository.target_counts(session)
        expected = {
            "orders": run.orders_count,
            "order_items": run.items_count,
            "order_status_history": run.orders_count,
            "order_creation_requests": 0,
            "inventory_reservations": 0,
            "order_guest_access": 0,
            "payments": 0,
            "payment_attempts": 0,
            "payment_events": 0,
            "legacy_order_imports": run.orders_count,
            "order_migration_runs": 1,
        }
        if counts != expected:
            raise TargetOrderStoreNotEmptyError(
                "Existing order migration run does not match target counts"
            )

    @staticmethod
    async def _synchronize_postgresql_sequences(session: AsyncSession) -> None:
        if session.get_bind().dialect.name != "postgresql":
            return
        for table_name in (
            "orders",
            "order_items",
            "order_status_history",
            "legacy_order_imports",
            "order_migration_runs",
        ):
            await session.execute(
                text(
                    "SELECT setval("
                    f"pg_get_serial_sequence('{table_name}', 'id'), "
                    f"COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {table_name}"
                )
            )
