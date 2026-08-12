from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.catalog.models import Product
from app.modules.crm.reference_models import (
    CrmCatalogProductModelLink,
    CrmFabric,
    CrmGarmentModel,
    CrmGarmentSize,
    CrmReferenceEvent,
    CrmTechCard,
    CrmTechCardCheckpoint,
    CrmTechCardRevision,
)
from app.modules.crm.reference_schemas import (
    CrmFabricWrite,
    CrmGarmentModelWrite,
    CrmGarmentSizeWrite,
    CrmTechCardCheckpointWrite,
    CrmTechCardCreate,
    CrmTechCardRevisionWrite,
)
from app.modules.crm.reference_service import (
    CrmReferenceConflictError,
    CrmReferenceService,
    CrmReferenceVersionConflictError,
)
from app.modules.identity.models import User

NOW = datetime(2026, 8, 12, 20, 0, tzinfo=timezone.utc)


def _settings(path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
    )


async def _create_database(path: Path) -> DatabaseManager:
    database = DatabaseManager(_settings(path))
    await database.startup()
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return database


def _fabric_payload(*, name: str = "Italian wool") -> CrmFabricWrite:
    return CrmFabricWrite(
        code="fab_wool_001",
        name=name,
        material_type="Wool",
        color_name="Graphite",
        color_hex="#1a1a1a",
        density_gsm=Decimal("285.50"),
        width_cm=Decimal("150.00"),
        cost_per_meter=Decimal("2450.00"),
    )


def _model_payload(*, include_small: bool = True) -> CrmGarmentModelWrite:
    sizes = [
        CrmGarmentSizeWrite(
            code="M",
            sort_order=20,
            base_price=Decimal("12000.00"),
            min_height_cm=Decimal("165.00"),
            max_height_cm=Decimal("180.00"),
        )
    ]
    if include_small:
        sizes.insert(
            0,
            CrmGarmentSizeWrite(
                code="S",
                sort_order=10,
                base_price=Decimal("11500.00"),
                min_height_cm=Decimal("155.00"),
                max_height_cm=Decimal("170.00"),
            ),
        )
    return CrmGarmentModelWrite(
        code="dress_base_01",
        name="Base dress",
        description="Internal pattern",
        base_height_cm=Decimal("120.00"),
        base_length_cm=Decimal("100.00"),
        base_width_cm=Decimal("45.00"),
        base_weight_g=Decimal("650.00"),
        sizes=sizes,
    )


def _revision_payload(*, suffix: str = "v1") -> CrmTechCardRevisionWrite:
    return CrmTechCardRevisionWrite(
        name=f"Dress production {suffix}",
        description=f"Immutable revision {suffix}",
        checkpoints=[
            CrmTechCardCheckpointWrite(
                position=10,
                stage_code="cutting",
                name=f"Cutting {suffix}",
                standard_minutes=Decimal("35.00"),
                labor_cost=Decimal("500.00"),
            ),
            CrmTechCardCheckpointWrite(
                position=20,
                stage_code="sewing",
                name=f"Sewing {suffix}",
                standard_minutes=Decimal("90.00"),
                labor_cost=Decimal("1500.00"),
            ),
        ],
    )


def test_crm_reference_schemas_normalize_and_reject_ambiguous_ordering() -> None:
    fabric = _fabric_payload()
    model = _model_payload()

    assert fabric.code == "FAB_WOOL_001"
    assert fabric.color_hex == "#1A1A1A"
    assert model.code == "DRESS_BASE_01"
    with pytest.raises(ValidationError, match="range is inverted"):
        CrmGarmentSizeWrite(
            code="S",
            min_height_cm=Decimal("180"),
            max_height_cm=Decimal("160"),
        )
    with pytest.raises(ValidationError, match="sort orders must be unique"):
        CrmGarmentModelWrite(
            code="MODEL",
            name="Model",
            sizes=[
                CrmGarmentSizeWrite(code="S", sort_order=1),
                CrmGarmentSizeWrite(code="M", sort_order=1),
            ],
        )
    with pytest.raises(ValidationError, match="positions must be unique"):
        CrmTechCardRevisionWrite(
            name="Card",
            checkpoints=[
                CrmTechCardCheckpointWrite(position=1, stage_code="cut", name="Cut"),
                CrmTechCardCheckpointWrite(position=1, stage_code="sew", name="Sew"),
            ],
        )


def test_fabrics_are_versioned_without_mutable_stock_counters(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = await _create_database(tmp_path / "crm-fabrics.db")
        service = CrmReferenceService()
        try:
            async with database.session() as session:
                fabric = await service.create_fabric(
                    session,
                    payload=_fabric_payload(),
                    actor_user_id=None,
                    now=NOW,
                )
                assert fabric.version == 1
                await session.commit()

            async with database.session() as session:
                with pytest.raises(CrmReferenceVersionConflictError, match="version has changed"):
                    await service.update_fabric(
                        session,
                        fabric_id=1,
                        expected_version=2,
                        payload=_fabric_payload(name="Wrong stale write"),
                        actor_user_id=None,
                        now=NOW,
                    )
                fabric = await service.update_fabric(
                    session,
                    fabric_id=1,
                    expected_version=1,
                    payload=_fabric_payload(name="Updated wool"),
                    actor_user_id=None,
                    now=NOW,
                )
                assert fabric.version == 2
                await session.commit()

            async with database.session() as session:
                fabric = await session.get(CrmFabric, 1)
                events = list(
                    await session.scalars(
                        select(CrmReferenceEvent).order_by(CrmReferenceEvent.entity_version)
                    )
                )
                assert fabric is not None
                assert fabric.code == "FAB_WOOL_001"
                assert fabric.name == "Updated wool"
                assert "stock_meters" not in CrmFabric.__table__.c
                assert "reserved_meters" not in CrmFabric.__table__.c
                assert [(event.action, event.entity_version) for event in events] == [
                    ("created", 1),
                    ("updated", 2),
                ]
                assert all(len(event.snapshot_sha256) == 64 for event in events)
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_garment_model_updates_preserve_size_identity_and_link_catalog(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        database = await _create_database(tmp_path / "crm-models.db")
        service = CrmReferenceService()
        try:
            async with database.session() as session:
                product = Product(
                    title="Public product",
                    slug="public-product",
                    price=Decimal("15000.00"),
                    sizes=["S", "M"],
                    colors=["black"],
                    is_active=True,
                    product_type="normal",
                    weight_kg=Decimal("0.650"),
                    height_cm=Decimal("10.00"),
                    width_cm=Decimal("30.00"),
                    length_cm=Decimal("40.00"),
                    stock_quantity=10,
                    reserved_quantity=0,
                )
                session.add(product)
                await session.flush()
                garment_model = await service.create_garment_model(
                    session,
                    payload=_model_payload(),
                    actor_user_id=None,
                    now=NOW,
                )
                original_ids = {size.code: size.id for size in garment_model.sizes}
                link = await service.link_catalog_product(
                    session,
                    garment_model_id=garment_model.id,
                    catalog_product_id=product.id,
                    actor_user_id=None,
                    now=NOW,
                )
                replay = await service.link_catalog_product(
                    session,
                    garment_model_id=garment_model.id,
                    catalog_product_id=product.id,
                    actor_user_id=None,
                    now=NOW,
                )
                assert replay.id == link.id
                second_payload = _model_payload().model_copy(
                    update={"code": "DRESS_BASE_02", "name": "Second base dress"}
                )
                second_model = await service.create_garment_model(
                    session,
                    payload=second_payload,
                    actor_user_id=None,
                    now=NOW,
                )
                with pytest.raises(CrmReferenceConflictError, match="another CRM garment model"):
                    await service.link_catalog_product(
                        session,
                        garment_model_id=second_model.id,
                        catalog_product_id=product.id,
                        actor_user_id=None,
                        now=NOW,
                    )
                await session.commit()

            async with database.session() as session:
                updated = await service.update_garment_model(
                    session,
                    garment_model_id=1,
                    expected_version=1,
                    payload=_model_payload(include_small=False),
                    actor_user_id=None,
                    now=NOW,
                )
                sizes = {size.code: size for size in updated.sizes}
                assert sizes["S"].id == original_ids["S"]
                assert not sizes["S"].is_active
                assert sizes["M"].id == original_ids["M"]
                assert sizes["M"].is_active
                assert sizes["M"].version == 2
                await session.commit()

            async with database.session() as session:
                restored = await service.update_garment_model(
                    session,
                    garment_model_id=1,
                    expected_version=2,
                    payload=_model_payload(),
                    actor_user_id=None,
                    now=NOW,
                )
                sizes = {size.code: size for size in restored.sizes}
                assert sizes["S"].id == original_ids["S"]
                assert sizes["S"].is_active
                assert sizes["S"].version == 3
                await session.commit()

            async with database.session() as session:
                model = await session.get(CrmGarmentModel, 1)
                link = await session.scalar(select(CrmCatalogProductModelLink))
                sizes = list(
                    await session.scalars(
                        select(CrmGarmentSize).where(CrmGarmentSize.garment_model_id == model.id)
                    )
                )
                assert model is not None and link is not None
                assert model.version == 3
                assert link.garment_model_id == model.id
                assert link.catalog_product_id == 1
                assert len(sizes) == 2
                assert "items" not in Base.metadata.tables
                assert "item_variants" not in Base.metadata.tables
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_tech_cards_publish_immutable_revisions_and_discard_bad_drafts(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        database = await _create_database(tmp_path / "crm-tech-cards.db")
        service = CrmReferenceService()
        try:
            async with database.session() as session:
                actor = User(
                    email="manager@example.test",
                    email_normalized="manager@example.test",
                    status="active",
                    email_verified_at=NOW,
                    created_at=NOW,
                    updated_at=NOW,
                )
                session.add(actor)
                await session.flush()
                model = await service.create_garment_model(
                    session,
                    payload=_model_payload(),
                    actor_user_id=actor.id,
                    now=NOW,
                )
                card = await service.create_tech_card(
                    session,
                    garment_model_id=model.id,
                    payload=CrmTechCardCreate(
                        code="tc_dress_01",
                        revision=_revision_payload(suffix="v1"),
                    ),
                    actor_user_id=actor.id,
                    now=NOW,
                )
                assert card.latest_revision_number == 1
                with pytest.raises(CrmReferenceConflictError, match="already has a draft"):
                    await service.create_tech_card_revision(
                        session,
                        tech_card_id=card.id,
                        expected_latest_revision=1,
                        payload=_revision_payload(suffix="blocked"),
                        actor_user_id=actor.id,
                        now=NOW,
                    )
                await service.publish_tech_card_revision(
                    session,
                    tech_card_id=card.id,
                    revision_number=1,
                    actor_user_id=actor.id,
                    now=NOW,
                )
                await session.commit()

            async with database.session() as session:
                draft_two = await service.create_tech_card_revision(
                    session,
                    tech_card_id=1,
                    expected_latest_revision=1,
                    payload=_revision_payload(suffix="bad-v2"),
                    actor_user_id=1,
                    now=NOW,
                )
                assert draft_two.based_on_revision_id == 1
                await service.discard_tech_card_draft(
                    session,
                    tech_card_id=1,
                    revision_number=2,
                    actor_user_id=1,
                    now=NOW,
                )
                await session.commit()

            async with database.session() as session:
                revision_three = await service.create_tech_card_revision(
                    session,
                    tech_card_id=1,
                    expected_latest_revision=2,
                    payload=_revision_payload(suffix="v3"),
                    actor_user_id=1,
                    now=NOW,
                )
                assert revision_three.revision_number == 3
                assert revision_three.based_on_revision_id == 1
                await service.publish_tech_card_revision(
                    session,
                    tech_card_id=1,
                    revision_number=3,
                    actor_user_id=1,
                    now=NOW,
                )
                await session.commit()

            async with database.session() as session:
                card = await session.get(CrmTechCard, 1)
                revisions = list(
                    await session.scalars(
                        select(CrmTechCardRevision).order_by(CrmTechCardRevision.revision_number)
                    )
                )
                checkpoints = list(
                    await session.scalars(
                        select(CrmTechCardCheckpoint).order_by(
                            CrmTechCardCheckpoint.tech_card_revision_id,
                            CrmTechCardCheckpoint.position,
                        )
                    )
                )
                events = list(
                    await session.scalars(select(CrmReferenceEvent).order_by(CrmReferenceEvent.id))
                )
                assert card is not None
                assert card.latest_revision_number == 3
                assert [revision.status for revision in revisions] == [
                    "archived",
                    "discarded",
                    "published",
                ]
                assert revisions[0].published_at is not None
                assert revisions[1].published_at is None
                assert revisions[2].published_by_user_id == 1
                assert [checkpoint.name for checkpoint in checkpoints[:2]] == [
                    "Cutting v1",
                    "Sewing v1",
                ]
                assert [checkpoint.name for checkpoint in checkpoints[-2:]] == [
                    "Cutting v3",
                    "Sewing v3",
                ]
                actions = [event.action for event in events]
                assert actions.count("published") == 2
                assert actions.count("revision_created") == 2
                assert actions.count("discarded") == 1
                assert all(len(event.snapshot_sha256) == 64 for event in events)
        finally:
            await database.shutdown()

    asyncio.run(scenario())
