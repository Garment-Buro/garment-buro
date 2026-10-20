import asyncio
import os

import pytest
from sqlalchemy import event, select

from app.modules.catalog.models import Product, ProductVariant
from app.modules.crm.assortment_models import CrmGarmentFabricRequirement
from app.modules.crm.file_models import CrmFileAttachment
from app.modules.crm.material_models import CrmMaterialReservation
from app.modules.crm.models import CrmProductionUnit
from app.modules.crm.production_models import CrmProductionPlanRevision
from app.modules.crm.reference_models import CrmFabric, CrmTechCard, CrmTechCardRevision
from app.modules.crm.reference_schemas import (
    CrmGarmentModelWrite,
    CrmGarmentSizeWrite,
    CrmTechCardCreate,
)
from app.modules.crm.reference_service import CrmReferenceService
from app.modules.media.models import MediaObject
from app.modules.orders.models import OrderItem
from app.modules.production.evidence import digest
from app.modules.production.models import ProductionSpecification
from app.modules.production.read_service import ProductionReadService
from tests.unit.test_crm_production_workflow import NOW, _card_revision
from tests.unit.test_production_terminal import execute, setup


@pytest.mark.parametrize("dialect", ["sqlite", "postgres"])
@pytest.mark.parametrize("planned", [False, True])
def test_order_detail_batches_repeated_models_and_specifications(tmp_path, dialect, planned):
    postgres = os.environ.get("PRODUCTION_TEST_POSTGRES_URL") if dialect == "postgres" else None
    if dialect == "postgres" and not postgres:
        pytest.skip("PRODUCTION_TEST_POSTGRES_URL is required")

    async def measure(quantity):
        directory = tmp_path / str(quantity)
        directory.mkdir()
        async with setup(directory, postgres_url=postgres, quantity=quantity) as (
            db,
            service,
            spec,
        ):
            if planned:
                async with db.session() as session:
                    pattern = await session.get(CrmFileAttachment, 1)
                    pattern.production_unit_id = None
                    pattern.tech_card_revision_id = spec["tech_card_revision_id"]
                    pattern.role = "pattern"
                    await session.commit()
                for unit_id in range(1, quantity + 1):
                    await execute(
                        db,
                        service,
                        "plan",
                        unit_id=unit_id,
                        specification=spec
                        | {
                            "print_file_ids": [],
                            "route": [stage for stage in spec["route"] if stage != "application"],
                        },
                    )
            queries = []

            def count(_connection, _cursor, statement, _parameters, _context, _many):
                if statement.lstrip().upper().startswith(("SELECT", "WITH")):
                    queries.append(statement)

            event.listen(db.engine.sync_engine, "before_cursor_execute", count)
            try:
                async with db.session() as session:
                    detail = await ProductionReadService().detail(
                        session, project_id=1, stations=["tech", "cut", "packing"]
                    )
            finally:
                event.remove(db.engine.sync_engine, "before_cursor_execute", count)
            assert len(detail["units"]) == quantity
            assert all(len(unit["sizes"]) == 2 for unit in detail["units"])
            assert all(len(unit["cards"]) == 1 for unit in detail["units"])
            if planned:
                assert all(unit["blockers"] == [] for unit in detail["units"])
                assert all(
                    unit["cutting"]["pattern_code"] == "PAT-DRESS-M-001" for unit in detail["units"]
                )
            # An attachment for unit1 must not leak into other units in the batch.
            assert [file["id"] for file in detail["units"][0]["files"]] == [1, 2]
            assert all(
                [file["id"] for file in unit["files"]] == ([1] if planned else [])
                for unit in detail["units"][1:]
            )
            return len(queries)

    async def scenario():
        small, large = await measure(1), await measure(32)
        assert large <= small + 2, (dialect, planned, small, large)
        assert large <= 22, (dialect, planned, small, large)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "change,message",
    [
        ("order", "Данные заказа изменились"),
        ("specification", "Нарушена целостность"),
        ("plan", "план больше не активен"),
        ("public", "Файл не готов"),
        ("pending", "Файл не готов"),
        ("checksum", "отличаются от утверждённых"),
        ("foreign", "другой вещи или техкарте"),
        ("missing", "Не все файлы сохранены"),
        ("overlap", "должны быть отдельными"),
    ],
)
def test_batched_detail_keeps_specification_blockers(tmp_path, change, message):
    async def scenario():
        async with setup(tmp_path, quantity=2) as (db, service, spec):
            await execute(db, service, "plan", unit_id=1, specification=spec)
            async with db.session() as session:
                saved = await session.scalar(select(ProductionSpecification))
                if change == "order":
                    item = await session.get(OrderItem, 1)
                    item.title_snapshot = "Changed"
                elif change in {"specification", "overlap"}:
                    saved.specification = saved.specification | {
                        "instructions": "Changed",
                        **({"print_file_ids": [1]} if change == "overlap" else {}),
                    }
                    if change == "overlap":
                        saved.specification_digest = digest(saved.specification)
                elif change == "plan":
                    plan = await session.get(CrmProductionPlanRevision, saved.plan_id)
                    plan.status = "superseded"
                elif change in {"public", "pending", "checksum"}:
                    media = await session.get(MediaObject, 2)
                    if change == "public":
                        media.is_public = True
                    elif change == "pending":
                        media.status = "pending"
                    else:
                        media.checksum_sha256 = "e" * 64
                else:
                    attachment = await session.get(CrmFileAttachment, 2)
                    if change == "missing":
                        await session.delete(attachment)
                    else:
                        attachment.production_unit_id = 2
                await session.commit()
            async with db.session() as session:
                detail = await ProductionReadService().detail(
                    session, project_id=1, stations=["tech"]
                )
                assert message in detail["units"][0]["blockers"][0]
                if change in {"public", "pending", "missing", "foreign"}:
                    assert 2 not in [file["id"] for file in detail["units"][0]["files"]]
                if change == "foreign":
                    assert [file["id"] for file in detail["units"][1]["files"]] == [2]

    asyncio.run(scenario())


def test_archived_pinned_card_still_has_its_files_and_checkpoints(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, service, spec):
            async with db.session() as session:
                attachment = await session.get(CrmFileAttachment, 1)
                attachment.production_unit_id = None
                attachment.tech_card_revision_id = spec["tech_card_revision_id"]
                attachment.role = "pattern"
                await session.commit()
            await execute(db, service, "plan", unit_id=1, specification=spec)
            async with db.session() as session:
                revision = await session.get(CrmTechCardRevision, spec["tech_card_revision_id"])
                card = await session.get(CrmTechCard, revision.tech_card_id)
                card.is_active = False
                revision.status = "archived"
                await session.commit()
            async with db.session() as session:
                detail = await ProductionReadService().detail(
                    session, project_id=1, stations=["tech"]
                )
                unit = detail["units"][0]
                assert unit["cards"] == []
                assert unit["tech_card"]["id"] == spec["tech_card_revision_id"]
                assert unit["tech_card"]["checkpoints"]
                assert unit["blockers"] == []
                assert [file["id"] for file in unit["files"]] == [1, 2]

    asyncio.run(scenario())


def test_detail_refreshes_preloaded_media_after_another_transaction(tmp_path):
    postgres = os.environ.get("PRODUCTION_TEST_POSTGRES_URL")
    if not postgres:
        pytest.skip("PRODUCTION_TEST_POSTGRES_URL is required")

    async def scenario():
        async with setup(tmp_path, postgres_url=postgres) as (db, service, spec):
            await execute(db, service, "plan", unit_id=1, specification=spec)
            async with db.session() as reader:
                held = await reader.get(MediaObject, 2)
                assert held.status == "ready"
                first = await ProductionReadService().detail(
                    reader, project_id=1, stations=["tech"]
                )
                assert first["units"][0]["blockers"] == []
                async with db.session() as writer:
                    media = await writer.get(MediaObject, 2)
                    media.status = "pending"
                    await writer.commit()
                second = await ProductionReadService().detail(
                    reader, project_id=1, stations=["tech"]
                )
                assert "Файл не готов" in second["units"][0]["blockers"][0]
                assert held.status == "pending"
                assert [file["id"] for file in second["units"][0]["files"]] == [1]

    asyncio.run(scenario())


@pytest.mark.parametrize("dialect", ["sqlite", "postgres"])
def test_detail_handles_more_units_than_one_id_batch(tmp_path, dialect):
    postgres = os.environ.get("PRODUCTION_TEST_POSTGRES_URL") if dialect == "postgres" else None
    if dialect == "postgres" and not postgres:
        pytest.skip("PRODUCTION_TEST_POSTGRES_URL is required")

    async def scenario():
        async with setup(tmp_path, postgres_url=postgres, quantity=300) as (db, _service, _spec):
            parameters_per_query = []

            def count(_connection, _cursor, statement, parameters, _context, _many):
                if statement.lstrip().upper().startswith(("SELECT", "WITH")):
                    parameters_per_query.append(len(parameters))

            event.listen(db.engine.sync_engine, "before_cursor_execute", count)
            try:
                async with db.session() as session:
                    detail = await ProductionReadService().detail(
                        session, project_id=1, stations=["tech"]
                    )
            finally:
                event.remove(db.engine.sync_engine, "before_cursor_execute", count)
            assert [unit["id"] for unit in detail["units"]] == list(range(1, 301))
            assert all(unit["files"] == [] for unit in detail["units"][1:])
            assert len(parameters_per_query) <= 22
            assert max(parameters_per_query) <= 256

    asyncio.run(scenario())


def test_models_sizes_cards_and_files_stay_with_their_own_unit(tmp_path):
    async def scenario():
        async with setup(tmp_path, quantity=2) as (db, _service, spec):
            references = CrmReferenceService()
            async with db.session() as session:
                model = await references.create_garment_model(
                    session,
                    payload=CrmGarmentModelWrite(
                        code="OTHER", name="Other", sizes=[CrmGarmentSizeWrite(code="XL")]
                    ),
                    actor_user_id=1,
                )
                session.add(Product(id=102, title="Other", price=100, garment_model_id=model.id))
                await session.flush()
                card = await references.create_tech_card(
                    session,
                    garment_model_id=model.id,
                    payload=CrmTechCardCreate(code="OTHER_CARD", revision=_card_revision("Other")),
                    actor_user_id=1,
                )
                revision = await references.publish_tech_card_revision(
                    session, tech_card_id=card.id, revision_number=1, actor_user_id=1
                )
                unit = await session.get(CrmProductionUnit, 2)
                unit.product_id_snapshot = 102
                for file_id, card_id in [(1, spec["tech_card_revision_id"]), (2, revision.id)]:
                    file = await session.get(CrmFileAttachment, file_id)
                    file.production_unit_id = None
                    file.tech_card_revision_id = card_id
                    file.role = "pattern"
                second_card = revision.id
                await session.commit()
            async with db.session() as session:
                detail = await ProductionReadService().detail(
                    session, project_id=1, stations=["tech"]
                )
                first, second = detail["units"]
                assert [size["code"] for size in first["sizes"]] == ["S", "M"]
                assert [size["code"] for size in second["sizes"]] == ["XL"]
                assert [card["id"] for card in first["cards"]] == [spec["tech_card_revision_id"]]
                assert [card["id"] for card in second["cards"]] == [second_card]
                assert [file["id"] for file in first["files"]] == [1]
                assert [file["id"] for file in second["files"]] == [2]

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "choice,expected",
    [
        ("reserve", "RESERVED"),
        ("variant", "VARIANT"),
        ("primary", "PRIMARY"),
        ("inactive", "FAB-BLACK-01"),
    ],
)
def test_cutting_fabric_keeps_reservation_variant_and_primary_priority(tmp_path, choice, expected):
    async def scenario():
        async with setup(tmp_path) as (db, service, spec):
            async with db.session() as session:
                fabric_ids = {}
                for code in ["VARIANT", "RESERVED", "PRIMARY"]:
                    fabric = CrmFabric(
                        code=code,
                        name=code,
                        color_name="Black",
                        width_cm=180,
                        is_active=(code != "PRIMARY" or choice != "inactive"),
                    )
                    session.add(fabric)
                    await session.flush()
                    fabric_ids[code] = fabric.id
                previous = await session.scalar(select(CrmGarmentFabricRequirement))
                previous.is_primary = False
                session.add(
                    CrmGarmentFabricRequirement(
                        garment_model_id=previous.garment_model_id,
                        fabric_id=fabric_ids["PRIMARY"],
                        meters_per_unit=2,
                        is_primary=True,
                    )
                )
                if choice in {"reserve", "variant"}:
                    variant = ProductVariant(
                        product_id=101, fabric_id=fabric_ids["VARIANT"], size="M", color="Black"
                    )
                    session.add(variant)
                    await session.flush()
                    item = await session.get(OrderItem, 1)
                    item.variant_id_snapshot = variant.id
                await session.commit()
            await execute(db, service, "plan", unit_id=1, specification=spec)
            if choice == "reserve":
                async with db.session() as session:
                    plan = await session.scalar(select(CrmProductionPlanRevision))
                    for code in ["RESERVED", "PRIMARY"]:
                        session.add(
                            CrmMaterialReservation(
                                production_plan_revision_id=plan.id,
                                fabric_id=fabric_ids[code],
                                requested_meters=1,
                                remaining_meters=1,
                                created_at=NOW,
                                updated_at=NOW,
                            )
                        )
                    await session.commit()
            async with db.session() as session:
                detail = await ProductionReadService().detail(
                    session, project_id=1, stations=["cut"]
                )
                assert detail["units"][0]["cutting"]["fabric"]["code"] == expected
                assert detail["units"][0]["blockers"] == []

    asyncio.run(scenario())
