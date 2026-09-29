"""Checkout fabric holds share the production material balance."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.availability import model_fabrics, variant_fabrics
from app.modules.catalog.models import Product
from app.modules.crm.material_repository import CrmMaterialRepository
from app.modules.crm.models import CrmProductionUnit
from app.modules.crm.production_models import CrmProductionPlanRevision
from app.modules.inventory.models import InventoryFabricHold, InventoryReservation
from app.modules.orders.models import Order


async def reserve_fabrics(
    session: AsyncSession,
    order: Order,
    products: dict[int, Product],
    reservations: list[InventoryReservation],
    now: datetime,
) -> None:
    from app.modules.inventory.service import InsufficientStockError

    fabrics_by_model = await model_fabrics(
        session, {p.garment_model_id for p in products.values() if p.garment_model_id is not None}
    )
    demands: dict[int, Decimal] = defaultdict(Decimal)
    holds: list[InventoryFabricHold] = []
    for item, reservation in zip(order.items, reservations, strict=True):
        if reservation.stock_source != "fabric":
            continue
        product = products[item.product_id_snapshot]
        fabrics = fabrics_by_model.get(product.garment_model_id, {})
        variant = next((v for v in product.variants if v.id == item.variant_id_snapshot), None)
        choices = (
            variant_fabrics(variant, fabrics) if variant else (fabrics if len(fabrics) == 1 else {})
        )
        if len(choices) != 1:
            raise InsufficientStockError("У пресета не назначена доступная ткань модели")
        for fabric_id, cost in choices.items():
            meters = cost * item.quantity
            demands[fabric_id] += meters
            holds.append(
                InventoryFabricHold(
                    reservation_id=reservation.id,
                    fabric_id=fabric_id,
                    requested_meters=meters,
                    remaining_meters=meters,
                )
            )
    repository = CrmMaterialRepository()
    for fabric_id in sorted(demands):
        balance = await repository.acquire_balance(session, fabric_id=fabric_id, now=now)
        meters = demands[fabric_id]
        if balance.on_hand_meters - balance.reserved_meters < meters:
            raise InsufficientStockError("Недостаточно свободной ткани для пресета")
        balance.reserved_meters += meters
        balance.version += 1
        balance.updated_at = now
    session.add_all(holds)
    await session.flush()


async def release_fabrics(
    session: AsyncSession,
    reservation_ids: list[int],
    now: datetime,
) -> None:
    holds = list(
        await session.scalars(
            select(InventoryFabricHold)
            .where(
                InventoryFabricHold.reservation_id.in_(reservation_ids),
                InventoryFabricHold.remaining_meters > 0,
            )
            .order_by(InventoryFabricHold.fabric_id, InventoryFabricHold.id)
        )
    )
    for fabric_id in sorted({hold.fabric_id for hold in holds}):
        balance = await CrmMaterialRepository().acquire_balance(
            session, fabric_id=fabric_id, now=now
        )
        for hold in holds:
            if hold.fabric_id == fabric_id:
                balance.reserved_meters -= hold.remaining_meters
                hold.remaining_meters = Decimal(0)
        balance.version += 1
        balance.updated_at = now
    await session.flush()


async def transfer_to_production(
    session: AsyncSession,
    *,
    plan_revision_id: int,
    fabric_id: int,
    quantity: Decimal,
) -> Decimal:
    """Caller holds the fabric balance lock; transfer without reserving twice."""
    order_item_id = await session.scalar(
        select(CrmProductionUnit.order_item_id)
        .join(
            CrmProductionPlanRevision,
            CrmProductionPlanRevision.production_unit_id == CrmProductionUnit.id,
        )
        .where(CrmProductionPlanRevision.id == plan_revision_id)
    )
    if order_item_id is None:
        return Decimal(0)
    holds = list(
        await session.scalars(
            select(InventoryFabricHold)
            .join(
                InventoryReservation,
                InventoryReservation.id == InventoryFabricHold.reservation_id,
            )
            .where(
                InventoryReservation.order_item_id == order_item_id,
                InventoryReservation.status == "confirmed",
                InventoryFabricHold.fabric_id == fabric_id,
                InventoryFabricHold.remaining_meters > 0,
            )
            .order_by(InventoryFabricHold.id)
            .with_for_update()
        )
    )
    remaining = quantity
    for hold in holds:
        transferred = min(hold.remaining_meters, remaining)
        hold.remaining_meters -= transferred
        remaining -= transferred
    return quantity - remaining
