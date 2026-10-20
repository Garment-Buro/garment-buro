from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.modules.catalog.models import Product, ProductVariant
from app.modules.crm.assortment_models import CrmGarmentFabricRequirement
from app.modules.crm.material_models import CrmMaterialBalance
from app.modules.crm.reference_models import CrmFabric, CrmGarmentModel


async def seed(database):
    async with database.session() as session:
        single = CrmGarmentModel(code="SINGLE", name="Single")
        multi = CrmGarmentModel(code="MULTI", name="Multi")
        inactive = CrmGarmentModel(code="INACTIVE", name="Inactive", is_active=False)
        fabrics = [
            CrmFabric(code=f"F{i}", name=f"Fabric{i}", color_name="black", width_cm=150)
            for i in range(3)
        ]
        session.add_all([single, multi, inactive, *fabrics])
        await session.flush()
        for model, fabric, meters, waste in [
            (single, fabrics[0], "2", "10"),
            (multi, fabrics[0], "2", "10"),
            (multi, fabrics[1], "0.333", "0.01"),
            (inactive, fabrics[0], "2", "10"),
        ]:
            session.add(
                CrmGarmentFabricRequirement(
                    garment_model_id=model.id,
                    fabric_id=fabric.id,
                    meters_per_unit=Decimal(meters),
                    waste_percent=Decimal(waste),
                )
            )
        for fabric, meters, reserved in [(fabrics[0], "8.8", "2.2"), (fabrics[1], "1.001", "0")]:
            session.add(
                CrmMaterialBalance(
                    fabric_id=fabric.id,
                    on_hand_meters=Decimal(meters),
                    reserved_meters=Decimal(reserved),
                    updated_at=datetime.now(timezone.utc),
                )
            )
        products = [
            Product(title="Alpha", price=10, stock_quantity=2),
            Product(title="Alpha", price=10, stock_quantity=0, preset_source="user"),
            Product(title="literal_%\\", price=15, stock_quantity=4, is_active=False),
        ]
        # Duplicate sizes must not count the same fabric twice. A fractional
        # cost rounds up to .334, so 1.001m makes two items, not three.
        for title, model, refs in [
            ("Same fabric", single, [fabrics[0].id, fabrics[0].id]),
            ("Single no variants", single, []),
            ("Inferred single", single, [None]),
            ("Two fabrics", multi, [fabrics[0].id, fabrics[1].id, fabrics[0].id]),
            ("Ambiguous", multi, [None]),
            ("Multi no variants", multi, []),
            ("Inactive model", inactive, [fabrics[0].id]),
            ("Unrelated fabric", single, [fabrics[2].id]),
        ]:
            product = Product(title=title, price=10, stock_quantity=999, garment_model_id=model.id)
            product.variants = [
                ProductVariant(size=str(i), fabric_id=fid, stock_quantity=999)
                for i, fid in enumerate(refs)
            ]
            products.append(product)
        session.add_all([*products, Product(title="Hidden demo", price=10, is_demo=True)])
        await session.commit()
        return {p.id: p.title for p in products}
