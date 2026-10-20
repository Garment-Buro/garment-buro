from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from test_inventory_reservations import _command, _seed, _settings

from app.db.session import DatabaseManager
from app.modules.catalog.mapper import CatalogResponseMapper
from app.modules.catalog.models import Product, ProductVariant
from app.modules.catalog.schemas import ProductWriteRequest
from app.modules.catalog.service import CatalogService
from app.modules.crm.assortment_models import CrmGarmentFabricRequirement
from app.modules.crm.material_models import CrmMaterialBalance
from app.modules.crm.material_service import CrmMaterialService
from app.modules.crm.models import CrmProductionUnit
from app.modules.crm.production_models import CrmProductionPlanRevision
from app.modules.crm.reference_models import CrmFabric, CrmGarmentModel
from app.modules.inventory.models import InventoryFabricHold, InventoryReservation
from app.modules.inventory.service import InsufficientStockError, InventoryReservationService
from app.modules.orders.service import OrderCreationService, OrderLifecycleService


def test_tags_are_normalized_and_validated():
    payload = ProductWriteRequest(
        title="Preset", price=100, tags=[" Спорт ", "спорт", "АНИМЕ", "два   слова"]
    )
    assert payload.tags == ["спорт", "аниме", "два слова"]
    for tags in [[" "], ["x" * 65], [None], "спорт"]:
        with pytest.raises(ValidationError):
            ProductWriteRequest(title="Preset", price=100, tags=tags)


@pytest.mark.parametrize("confirm", [False, True])
def test_presets_share_fabric_stock_and_reserve_release_or_confirm(tmp_path, confirm):
    async def scenario():
        settings = _settings(tmp_path / "presets.db")
        database = DatabaseManager(settings)
        await database.startup()
        now = datetime(2026, 9, 29, tzinfo=timezone.utc)
        try:
            product_id, variant_id, _ = await _seed(database)
            async with database.session() as session:
                model = CrmGarmentModel(code="BLANK", name="Blank")
                fabric = CrmFabric(code="COTTON", name="Cotton", color_name="black", width_cm=150)
                session.add_all([model, fabric])
                await session.flush()
                session.add_all(
                    [
                        CrmGarmentFabricRequirement(
                            garment_model_id=model.id,
                            fabric_id=fabric.id,
                            meters_per_unit=Decimal("2"),
                            waste_percent=10,
                        ),
                        CrmMaterialBalance(
                            fabric_id=fabric.id,
                            on_hand_meters=Decimal("6.6"),
                            reserved_meters=0,
                            updated_at=now,
                        ),
                    ]
                )
                product = await session.get(Product, product_id)
                product.garment_model_id = model.id
                product.stock_quantity = 0
                variant = await session.get(ProductVariant, variant_id)
                variant.fabric_id = fabric.id
                variant.stock_quantity = 0
                second = Product(
                    title="Anime",
                    price=100,
                    garment_model_id=model.id,
                    tags=["аниме"],
                    preset_source="user",
                    stock_quantity=999,
                )
                second.variants = [
                    ProductVariant(size="M", color="black", fabric_id=fabric.id),
                    ProductVariant(size="L", color="black", fabric_id=fabric.id),
                ]
                session.add(second)
                await session.commit()
                second_id, fabric_id = second.id, fabric.id
            catalog = CatalogService(CatalogResponseMapper(settings))
            async with database.session() as session:
                preset = await catalog.get_product(session, second_id)
                assert preset.stock_quantity == 3  # Two sizes do not double capacity.
                assert [v.stock_quantity for v in preset.variants] == [3, 3]
                assert preset.tags == ["аниме"] and preset.preset_source == "user"
                created = await OrderCreationService(settings).create(
                    session,
                    idempotency_key="preset_checkout_00001",
                    command=_command(product_id),
                    now=now,
                )
                await session.commit()
            async with database.session() as session:
                assert (await catalog.get_product(session, second_id)).stock_quantity == 1
                with pytest.raises(InsufficientStockError):
                    await OrderCreationService(settings).create(
                        session,
                        idempotency_key="preset_checkout_00002",
                        command=_command(product_id),
                        now=now,
                    )
                await session.rollback()
            async with database.session() as session:
                lifecycle = OrderLifecycleService(settings)
                if confirm:
                    await lifecycle.confirm_payment(
                        session, order_id=created.order_id, now=now + timedelta(seconds=1)
                    )
                else:
                    from app.modules.orders.models import Order

                    order = await session.get(Order, created.order_id)
                    await InventoryReservationService(settings).release_order(
                        session, order=order, reason="test", now=now
                    )
                await session.commit()
            async with database.session() as session:
                assert (await catalog.get_product(session, second_id)).stock_quantity == (
                    1 if confirm else 3
                )
                balance = await session.get(CrmMaterialBalance, fabric_id)
                assert balance.on_hand_meters == Decimal("6.6")
                assert balance.reserved_meters == (Decimal("4.4") if confirm else 0)
                holds = list(await session.scalars(select(InventoryFabricHold)))
                assert len(holds) == 1
                assert holds[0].remaining_meters == (Decimal("4.4") if confirm else 0)
                assert (await session.get(Product, product_id)).stock_quantity == 0
                if confirm:
                    reservation = await session.get(InventoryReservation, holds[0].reservation_id)
                    unit = CrmProductionUnit(
                        project_id=1,
                        order_item_id=reservation.order_item_id,
                        product_id_snapshot=product_id,
                        unit_number=1,
                        status="queued",
                    )
                    session.add(unit)
                    await session.flush()
                    plan = CrmProductionPlanRevision(
                        production_unit_id=unit.id,
                        revision_number=1,
                        garment_model_id=model.id,
                        tech_card_revision_id=1,
                        status="active",
                        evidence_sha256="a" * 64,
                        planned_at=now,
                    )
                    session.add(plan)
                    await session.flush()
                    service = CrmMaterialService()
                    material, _ = await service.reserve(
                        session,
                        plan_revision_id=plan.id,
                        fabric_id=fabric_id,
                        quantity_meters=Decimal("2.2"),
                        idempotency_key="preset-production-1",
                        actor_user_id=None,
                        now=now,
                    )
                    await session.commit()
                    assert balance.reserved_meters == Decimal("4.4")
                    assert holds[0].remaining_meters == Decimal("2.2")
                    replay, _ = await service.reserve(
                        session,
                        plan_revision_id=plan.id,
                        fabric_id=fabric_id,
                        quantity_meters=Decimal("2.2"),
                        idempotency_key="preset-production-1",
                        actor_user_id=None,
                        now=now,
                    )
                    assert replay.id == material.id
                    assert holds[0].remaining_meters == Decimal("2.2")
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_preset_migration_preserves_existing_catalog_and_blocks_unsafe_downgrade():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, text

    path = Path(__file__).resolve().parents[2] / "migrations/versions/20260929_0055_presets.py"
    spec = importlib.util.spec_from_file_location("preset_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE products (id INTEGER PRIMARY KEY, title TEXT)"))
        connection.execute(text("CREATE TABLE inventory_reservations (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE crm_fabrics (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO products VALUES (1, 'Existing')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert connection.execute(
                text("SELECT title, preset_source, tags FROM products")
            ).one() == ("Existing", "garment_buro", "[]")
            connection.execute(text("INSERT INTO inventory_fabric_holds VALUES (1, 1, 1, 2, 2)"))
            with pytest.raises(RuntimeError, match="Resolve fabric checkout holds"):
                migration.downgrade()
            connection.execute(text("UPDATE inventory_fabric_holds SET remaining_meters = 0"))
            migration.downgrade()
            assert connection.scalar(text("SELECT title FROM products")) == "Existing"
