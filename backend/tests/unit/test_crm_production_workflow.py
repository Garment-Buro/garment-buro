from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.catalog.models import Product
from app.modules.crm.material_models import (
    CrmMaterialBalance,
    CrmMaterialReservation,
    CrmMaterialReservationStatus,
)
from app.modules.crm.material_service import CrmMaterialService
from app.modules.crm.models import (
    CrmProductionUnit,
    CrmProductionUnitStatus,
    CrmProjectStatus,
)
from app.modules.crm.production_models import (
    CrmProductionPlanRevision,
    CrmProductionUnitEvent,
)
from app.modules.crm.production_service import (
    CrmProductionConflictError,
    CrmProductionService,
)
from app.modules.crm.reconciliation import CrmReconciliationService
from app.modules.crm.reference_models import CrmFabric, CrmGarmentSize, CrmTechCardRevision
from app.modules.crm.reference_schemas import (
    CrmGarmentModelWrite,
    CrmGarmentSizeWrite,
    CrmTechCardCheckpointWrite,
    CrmTechCardCreate,
    CrmTechCardRevisionWrite,
)
from app.modules.crm.reference_service import CrmReferenceService
from app.modules.crm.service import CrmProjectService, CrmProjectStateError
from app.modules.fulfillment.factory import build_fulfillment_processor
from app.modules.fulfillment.service import FulfillmentOutboxService
from app.modules.identity.models import User
from app.modules.orders.models import Order, OrderItem
from app.modules.payments.models import Payment, PaymentAttempt

NOW = datetime(2026, 8, 12, 22, 0, tzinfo=timezone.utc)


def _settings(path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
        fulfillment_outbox_enabled=True,
        fulfillment_crm_enabled=True,
    )


def _card_revision(name: str) -> CrmTechCardRevisionWrite:
    return CrmTechCardRevisionWrite(
        name=name,
        checkpoints=[
            CrmTechCardCheckpointWrite(
                position=1,
                stage_code="sewing",
                name=f"Sew {name}",
                standard_minutes=Decimal("60.00"),
                labor_cost=Decimal("1000.00"),
            )
        ],
    )


async def _seed_unit_and_reference_data(database: DatabaseManager) -> tuple[int, int, int, int]:
    digest = hashlib.sha256(b"crm-production-workflow").hexdigest()
    async with database.session() as session:
        actor = User(
            email="manager@example.test",
            email_normalized="manager@example.test",
            status="active",
            email_verified_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        )
        product = Product(
            id=101,
            title="Public dress",
            slug="public-dress",
            price=Decimal("100.00"),
            sizes=["S", "M"],
            colors=["black"],
            is_active=True,
            product_type="normal",
            weight_kg=Decimal("0.500"),
            height_cm=Decimal("10.00"),
            width_cm=Decimal("20.00"),
            length_cm=Decimal("30.00"),
            stock_quantity=1,
            reserved_quantity=0,
        )
        session.add_all([actor, product])
        await session.flush()
        order = Order(
            delivery_method="courier",
            items_subtotal=Decimal("100.00"),
            delivery_price=Decimal("0.00"),
            total_price=Decimal("100.00"),
            currency="RUB",
            status="processing",
            payment_status="paid",
            version=2,
            request_fingerprint_sha256=digest,
            created_at=NOW,
            updated_at=NOW,
            items=[
                OrderItem(
                    client_item_id="production-line",
                    product_id_snapshot=101,
                    variant_id_snapshot=None,
                    title_snapshot="Dress",
                    unit_price=Decimal("100.00"),
                    quantity=1,
                    line_total=Decimal("100.00"),
                    image_url_snapshot="",
                    size_snapshot="M",
                    color_snapshot="black",
                    customization_snapshot=None,
                    sort_order=0,
                )
            ],
        )
        session.add(order)
        await session.flush()
        payment = Payment(
            order_id=order.id,
            status="succeeded",
            amount=order.total_price,
            currency="RUB",
            succeeded_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(payment)
        await session.flush()
        attempt = PaymentAttempt(
            payment_id=payment.id,
            attempt_number=1,
            client_key_digest_sha256=digest,
            provider_idempotence_key="00000000-0000-4000-8000-000000000301",
            request_fingerprint_sha256=digest,
            payment_method="bank_card",
            status="succeeded",
            provider_payment_id="provider-production-301",
            provider_created_at=NOW,
            captured_at=NOW,
            resolved_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(attempt)
        await session.flush()
        await FulfillmentOutboxService(database.settings).schedule_paid_order(
            session,
            order=order,
            payment_attempt_id=attempt.id,
            now=NOW,
        )
        await session.commit()

    async with database.session() as session:
        result = await build_fulfillment_processor(database.settings).process_once(
            session,
            worker_id="production-intake",
            now=NOW,
        )
        assert result is not None and result.status == "completed"

    reference = CrmReferenceService()
    async with database.session() as session:
        model = await reference.create_garment_model(
            session,
            payload=CrmGarmentModelWrite(
                code="DRESS_01",
                name="Dress",
                sizes=[
                    CrmGarmentSizeWrite(code="S", sort_order=1),
                    CrmGarmentSizeWrite(code="M", sort_order=2),
                ],
            ),
            actor_user_id=1,
            now=NOW,
        )
        await reference.link_catalog_product(
            session,
            garment_model_id=model.id,
            catalog_product_id=101,
            actor_user_id=1,
            now=NOW,
        )
        card = await reference.create_tech_card(
            session,
            garment_model_id=model.id,
            payload=CrmTechCardCreate(code="TC_DRESS_01", revision=_card_revision("v1")),
            actor_user_id=1,
            now=NOW,
        )
        revision = await reference.publish_tech_card_revision(
            session,
            tech_card_id=card.id,
            revision_number=1,
            actor_user_id=1,
            now=NOW,
        )
        sizes = list(
            await session.scalars(
                select(CrmGarmentSize).where(CrmGarmentSize.garment_model_id == model.id)
            )
        )
        size_by_code = {size.code: size.id for size in sizes}
        unit_id = await session.scalar(select(CrmProductionUnit.id))
        assert unit_id is not None
        await session.commit()
        return unit_id, size_by_code["S"], size_by_code["M"], revision.id


def test_production_plan_pins_published_revision_and_unit_workflow(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "crm-production.db")
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            (
                unit_id,
                small_size_id,
                medium_size_id,
                revision_one_id,
            ) = await _seed_unit_and_reference_data(database)
            production = CrmProductionService()

            async with database.session() as session:
                with pytest.raises(CrmProductionConflictError, match="active plan"):
                    await production.transition_unit(
                        session,
                        production_unit_id=unit_id,
                        expected_version=1,
                        to_status=CrmProductionUnitStatus.IN_PROGRESS,
                        reason_code="work_started",
                        actor_user_id=1,
                        now=NOW,
                    )
                with pytest.raises(CrmProductionConflictError, match="immutable order evidence"):
                    await production.plan_unit(
                        session,
                        production_unit_id=unit_id,
                        expected_version=1,
                        garment_size_id=small_size_id,
                        tech_card_revision_id=revision_one_id,
                        actor_user_id=1,
                        now=NOW,
                    )
                plan_one = await production.plan_unit(
                    session,
                    production_unit_id=unit_id,
                    expected_version=1,
                    garment_size_id=medium_size_id,
                    tech_card_revision_id=revision_one_id,
                    actor_user_id=1,
                    now=NOW,
                )
                assert plan_one.revision_number == 1
                await session.commit()

            async with database.session() as session:
                replay = await production.plan_unit(
                    session,
                    production_unit_id=unit_id,
                    expected_version=1,
                    garment_size_id=medium_size_id,
                    tech_card_revision_id=revision_one_id,
                    actor_user_id=1,
                    now=NOW,
                )
                assert replay.id == 1

            reference = CrmReferenceService()
            async with database.session() as session:
                revision_two = await reference.create_tech_card_revision(
                    session,
                    tech_card_id=1,
                    expected_latest_revision=1,
                    payload=_card_revision("v2"),
                    actor_user_id=1,
                    now=NOW,
                )
                await reference.publish_tech_card_revision(
                    session,
                    tech_card_id=1,
                    revision_number=2,
                    actor_user_id=1,
                    now=NOW,
                )
                revision_two_id = revision_two.id
                await session.commit()

            material = CrmMaterialService()
            async with database.session() as session:
                session.add(
                    CrmFabric(
                        code="FAB-PLAN",
                        name="Plan fabric",
                        color_name="Black",
                        width_cm=Decimal("150"),
                        currency="RUB",
                        is_active=True,
                        version=1,
                    )
                )
                await session.flush()
                await material.receive(
                    session,
                    fabric_id=1,
                    quantity_meters=Decimal("5"),
                    idempotency_key="plan-receipt",
                    reason_code="supplier_receipt",
                    actor_user_id=1,
                    now=NOW,
                )
                reservation, _ = await material.reserve(
                    session,
                    plan_revision_id=1,
                    fabric_id=1,
                    quantity_meters=Decimal("2"),
                    idempotency_key="plan-reserve",
                    actor_user_id=1,
                    now=NOW,
                )
                reservation_id = reservation.id
                await session.commit()

            async with database.session() as session:
                with pytest.raises(
                    CrmProductionConflictError,
                    match="Release active material reservations",
                ):
                    await production.plan_unit(
                        session,
                        production_unit_id=unit_id,
                        expected_version=2,
                        garment_size_id=medium_size_id,
                        tech_card_revision_id=revision_two_id,
                        actor_user_id=1,
                        now=NOW,
                    )
                with pytest.raises(
                    CrmProductionConflictError,
                    match="release active material reservations",
                ):
                    await production.transition_unit(
                        session,
                        production_unit_id=unit_id,
                        expected_version=2,
                        to_status=CrmProductionUnitStatus.CANCELLED,
                        reason_code="production_cancelled",
                        actor_user_id=1,
                        now=NOW,
                    )
                await material.release(
                    session,
                    reservation_id=reservation_id,
                    quantity_meters=Decimal("2"),
                    idempotency_key="plan-release",
                    reason_code="replan_release",
                    actor_user_id=1,
                    now=NOW,
                )
                await session.commit()

            async with database.session() as session:
                plan_two = await production.plan_unit(
                    session,
                    production_unit_id=unit_id,
                    expected_version=2,
                    garment_size_id=medium_size_id,
                    tech_card_revision_id=revision_two_id,
                    actor_user_id=1,
                    now=NOW,
                )
                assert plan_two.revision_number == 2
                assert plan_two.based_on_plan_revision_id == 1
                await session.commit()

            async with database.session() as session:
                started = await production.transition_unit(
                    session,
                    production_unit_id=unit_id,
                    expected_version=3,
                    to_status=CrmProductionUnitStatus.IN_PROGRESS,
                    reason_code="work_started",
                    actor_user_id=1,
                    now=NOW,
                )
                assert started.version == 4 and started.started_at is not None
                await session.commit()
            async with database.session() as session:
                quality = await production.transition_unit(
                    session,
                    production_unit_id=unit_id,
                    expected_version=4,
                    to_status=CrmProductionUnitStatus.QUALITY_CONTROL,
                    reason_code="sent_to_quality",
                    actor_user_id=1,
                    now=NOW,
                )
                assert quality.version == 5
                await session.commit()
            async with database.session() as session:
                completed = await production.transition_unit(
                    session,
                    production_unit_id=unit_id,
                    expected_version=5,
                    to_status=CrmProductionUnitStatus.COMPLETED,
                    reason_code="quality_accepted",
                    actor_user_id=1,
                    now=NOW,
                )
                assert completed.version == 6 and completed.closed_at is not None
                await session.commit()

            project_service = CrmProjectService()
            async with database.session() as session:
                started_project = await project_service.transition(
                    session,
                    project_id=1,
                    expected_version=1,
                    to_status=CrmProjectStatus.IN_PROGRESS,
                    reason_code="production_started",
                    actor_user_id=1,
                    now=NOW,
                )
                assert started_project.version == 2
                await session.commit()

            async with database.session() as session:
                balance = await session.get(CrmMaterialBalance, 1)
                assert balance is not None
                balance.reserved_meters = Decimal("1.000")
                balance.version += 1
                balance.updated_at = NOW
                session.add(
                    CrmMaterialReservation(
                        production_plan_revision_id=2,
                        fabric_id=1,
                        requested_meters=Decimal("1.000"),
                        remaining_meters=Decimal("1.000"),
                        consumed_meters=Decimal("0.000"),
                        released_meters=Decimal("0.000"),
                        status=CrmMaterialReservationStatus.ACTIVE.value,
                        version=1,
                        created_by_user_id=1,
                        created_at=NOW,
                        updated_at=NOW,
                    )
                )
                await session.commit()

            async with database.session() as session:
                with pytest.raises(CrmProjectStateError, match="Active material reservations"):
                    await project_service.transition(
                        session,
                        project_id=1,
                        expected_version=2,
                        to_status=CrmProjectStatus.COMPLETED,
                        reason_code="production_completed",
                        actor_user_id=1,
                        now=NOW,
                    )
                reservation = await session.scalar(
                    select(CrmMaterialReservation).where(
                        CrmMaterialReservation.production_plan_revision_id == 2
                    )
                )
                balance = await session.get(CrmMaterialBalance, 1)
                assert reservation is not None and balance is not None
                reservation.remaining_meters = Decimal("0.000")
                reservation.released_meters = Decimal("1.000")
                reservation.status = CrmMaterialReservationStatus.CLOSED.value
                reservation.version += 1
                balance.reserved_meters = Decimal("0.000")
                balance.version = 4
                await session.delete(reservation)
                await session.commit()

            async with database.session() as session:
                completed_project = await project_service.transition(
                    session,
                    project_id=1,
                    expected_version=2,
                    to_status=CrmProjectStatus.COMPLETED,
                    reason_code="production_completed",
                    actor_user_id=1,
                    now=NOW,
                )
                assert completed_project.version == 3
                await session.commit()

            async with database.session() as session:
                with pytest.raises(CrmProductionConflictError, match="cannot transition"):
                    await production.transition_unit(
                        session,
                        production_unit_id=unit_id,
                        expected_version=6,
                        to_status=CrmProductionUnitStatus.QUALITY_CONTROL,
                        reason_code="late_reopen",
                        actor_user_id=1,
                        now=NOW,
                    )
                plans = list(
                    await session.scalars(
                        select(CrmProductionPlanRevision).order_by(
                            CrmProductionPlanRevision.revision_number
                        )
                    )
                )
                revisions = list(
                    await session.scalars(
                        select(CrmTechCardRevision).order_by(CrmTechCardRevision.revision_number)
                    )
                )
                events = list(
                    await session.scalars(
                        select(CrmProductionUnitEvent).order_by(CrmProductionUnitEvent.version)
                    )
                )
                assert [plan.status for plan in plans] == ["superseded", "active"]
                assert [revision.status for revision in revisions] == ["archived", "published"]
                assert plans[0].tech_card_revision_id == revisions[0].id
                assert [event.version for event in events] == [1, 2, 3, 4, 5, 6]
                assert [event.event_type for event in events] == [
                    "initialized",
                    "planned",
                    "planned",
                    "status_changed",
                    "status_changed",
                    "status_changed",
                ]
                assert [event.to_status for event in events] == [
                    "queued",
                    "queued",
                    "queued",
                    "in_progress",
                    "quality_control",
                    "completed",
                ]

            async with database.session() as session:
                report = await CrmReconciliationService().inspect(
                    session,
                    private_bucket=settings.minio_crm_bucket,
                    now=NOW,
                )
                assert report.healthy
                assert report.total_issues == 0
        finally:
            await database.shutdown()

    asyncio.run(scenario())
