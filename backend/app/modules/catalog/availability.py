"""One fabric capacity calculation for preset reads and checkout."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_CEILING, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Product, ProductVariant
from app.modules.crm.assortment_models import CrmGarmentFabricRequirement
from app.modules.crm.material_models import CrmMaterialBalance
from app.modules.crm.reference_models import CrmFabric, CrmGarmentModel


def unit_meters(requirement: CrmGarmentFabricRequirement) -> Decimal:
    return (requirement.meters_per_unit * (1 + requirement.waste_percent / 100)).quantize(
        Decimal("0.001"), rounding=ROUND_CEILING
    )


async def model_fabrics(
    session: AsyncSession, model_ids: set[int]
) -> dict[int, dict[int, Decimal]]:
    if not model_ids:
        return {}
    rows = await session.scalars(
        select(CrmGarmentFabricRequirement)
        .join(CrmFabric, CrmFabric.id == CrmGarmentFabricRequirement.fabric_id)
        .join(CrmGarmentModel, CrmGarmentModel.id == CrmGarmentFabricRequirement.garment_model_id)
        .where(
            CrmGarmentFabricRequirement.garment_model_id.in_(model_ids),
            CrmFabric.is_active.is_(True),
            CrmGarmentModel.is_active.is_(True),
        )
    )
    result: dict[int, dict[int, Decimal]] = {}
    for row in rows:
        result.setdefault(row.garment_model_id, {})[row.fabric_id] = unit_meters(row)
    return result


def variant_fabrics(variant: ProductVariant, fabrics: dict[int, Decimal]) -> dict[int, Decimal]:
    if variant.fabric_id is not None:
        return (
            {variant.fabric_id: fabrics[variant.fabric_id]} if variant.fabric_id in fabrics else {}
        )
    # A missing fabric reference is unambiguous only for a single-fabric model.
    return fabrics if len(fabrics) == 1 else {}


async def load_availability(session: AsyncSession, products: Sequence[Product]) -> None:
    for product in products:
        product.__dict__.pop("_fabric_stock_quantity", None)
        for variant in product.variants:
            variant.__dict__.pop("_fabric_stock_quantity", None)
    linked = [product for product in products if product.garment_model_id is not None]
    fabrics_by_model = await model_fabrics(session, {p.garment_model_id for p in linked})
    fabric_ids = {fid for fabrics in fabrics_by_model.values() for fid in fabrics}
    balances = (
        list(
            await session.scalars(
                select(CrmMaterialBalance).where(CrmMaterialBalance.fabric_id.in_(fabric_ids))
            )
        )
        if fabric_ids
        else []
    )
    available = {row.fabric_id: row.on_hand_meters - row.reserved_meters for row in balances}
    for product in linked:
        fabrics = fabrics_by_model.get(product.garment_model_id, {})
        used: dict[int, Decimal] = {}
        for variant in product.variants:
            choices = variant_fabrics(variant, fabrics)
            used.update(choices)
            variant._fabric_stock_quantity = sum(
                int(max(Decimal(0), available.get(fid, Decimal(0))) / cost)
                for fid, cost in choices.items()
            )
        if not product.variants:
            used = fabrics if len(fabrics) == 1 else {}
        # Sizes and presets share fabric: never sum the same fabric twice.
        product._fabric_stock_quantity = sum(
            int(max(Decimal(0), available.get(fid, Decimal(0))) / cost)
            for fid, cost in used.items()
        )


def available_stock(row: Product | ProductVariant) -> int:
    return getattr(row, "_fabric_stock_quantity", row.stock_quantity - row.reserved_quantity)
