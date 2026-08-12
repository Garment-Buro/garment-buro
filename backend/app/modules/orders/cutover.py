from __future__ import annotations

from sqlalchemy import func, or_, select

from app.core.exceptions import ConfigurationError
from app.db.session import DatabaseManager
from app.modules.inventory.models import InventoryReservation
from app.modules.orders.models import (
    LegacyOrderImport,
    Order,
    OrderGuestAccess,
    OrderItem,
    OrderMigrationRun,
    OrderStatusHistory,
)
from app.modules.payments.models import Payment


async def verify_order_read_cutover(
    database: DatabaseManager,
    expected_fingerprint: str,
) -> None:
    async with database.session() as session:
        run = await session.scalar(
            select(OrderMigrationRun).where(
                OrderMigrationRun.fingerprint_sha256 == expected_fingerprint
            )
        )
        if run is None:
            raise ConfigurationError(
                "ORDER_MIGRATION_FINGERPRINT is not present in the target database"
            )

        imported_order_ids = select(LegacyOrderImport.order_id)
        actual = {
            "migration_runs": int(
                await session.scalar(select(func.count()).select_from(OrderMigrationRun)) or 0
            ),
            "imports": int(
                await session.scalar(select(func.count()).select_from(LegacyOrderImport)) or 0
            ),
            "imported_orders": int(
                await session.scalar(
                    select(func.count()).select_from(Order).where(Order.id.in_(imported_order_ids))
                )
                or 0
            ),
            "imported_items": int(
                await session.scalar(
                    select(func.count())
                    .select_from(OrderItem)
                    .where(OrderItem.order_id.in_(imported_order_ids))
                )
                or 0
            ),
            "imported_history": int(
                await session.scalar(
                    select(func.count())
                    .select_from(OrderStatusHistory)
                    .where(OrderStatusHistory.order_id.in_(imported_order_ids))
                )
                or 0
            ),
            "payment_references": int(
                await session.scalar(
                    select(func.count())
                    .select_from(LegacyOrderImport)
                    .where(LegacyOrderImport.payment_provider_id.is_not(None))
                )
                or 0
            ),
            "delivery_references": int(
                await session.scalar(
                    select(func.count())
                    .select_from(LegacyOrderImport)
                    .where(
                        or_(
                            LegacyOrderImport.delivery_provider_uuid.is_not(None),
                            LegacyOrderImport.delivery_provider_number.is_not(None),
                        )
                    )
                )
                or 0
            ),
            "imported_reservations": int(
                await session.scalar(
                    select(func.count())
                    .select_from(InventoryReservation)
                    .where(InventoryReservation.order_id.in_(imported_order_ids))
                )
                or 0
            ),
            "imported_guest_access": int(
                await session.scalar(
                    select(func.count())
                    .select_from(OrderGuestAccess)
                    .where(OrderGuestAccess.order_id.in_(imported_order_ids))
                )
                or 0
            ),
            "imported_payments": int(
                await session.scalar(
                    select(func.count())
                    .select_from(Payment)
                    .where(Payment.order_id.in_(imported_order_ids))
                )
                or 0
            ),
            "source_id_mismatches": int(
                await session.scalar(
                    select(func.count())
                    .select_from(LegacyOrderImport)
                    .where(LegacyOrderImport.order_id != LegacyOrderImport.source_order_id)
                )
                or 0
            ),
        }
        expected = {
            "migration_runs": 1,
            "imports": run.orders_count,
            "imported_orders": run.orders_count,
            "imported_items": run.items_count,
            "payment_references": run.payment_references_count,
            "delivery_references": run.delivery_references_count,
            "imported_reservations": 0,
            "imported_guest_access": 0,
            "imported_payments": 0,
            "source_id_mismatches": 0,
        }
        for name, count in expected.items():
            if actual[name] != count:
                raise ConfigurationError(
                    "Order read target does not match the reviewed migration run"
                )
        if actual["imported_history"] < run.orders_count:
            raise ConfigurationError("Order read target has incomplete imported status history")
