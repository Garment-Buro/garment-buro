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
from app.modules.crm.models import (
    CrmOrderProject,
    CrmProductionUnit,
    CrmProductionUnitStatus,
    CrmProjectEvent,
)
from app.modules.crm.production_models import CrmProductionUnitEvent
from app.modules.crm.repository import (
    CrmProductionUnitSnapshot,
    CrmProjectEvidenceConflictError,
    CrmProjectRepository,
)
from app.modules.crm.service import (
    CrmProjectService,
    CrmProjectStateError,
    CrmProjectStatus,
    CrmProjectVersionConflictError,
)
from app.modules.fulfillment.factory import build_fulfillment_processor
from app.modules.fulfillment.models import FulfillmentJob, FulfillmentJobAttempt
from app.modules.fulfillment.service import FulfillmentOutboxService
from app.modules.fulfillment.worker import FulfillmentProcessor
from app.modules.orders.models import Order, OrderItem
from app.modules.payments.models import Payment, PaymentAttempt

NOW = datetime(2026, 8, 12, 18, 0, tzinfo=timezone.utc)


def _settings(path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
        fulfillment_outbox_enabled=True,
        fulfillment_crm_enabled=True,
        fulfillment_max_attempts=3,
    )


async def _seed_paid_order(database: DatabaseManager) -> tuple[int, int, int]:
    digest = hashlib.sha256(b"crm-paid-order-evidence").hexdigest()
    async with database.session() as session:
        order = Order(
            email="private@example.test",
            email_normalized="private@example.test",
            phone="+79000000000",
            first_name="Private First",
            last_name="Private Last",
            delivery_city="Private City",
            delivery_method="courier",
            delivery_address="Private address",
            payment_method="card",
            items_subtotal=Decimal("350.00"),
            delivery_price=Decimal("50.00"),
            total_price=Decimal("400.00"),
            currency="RUB",
            status="processing",
            payment_status="paid",
            version=2,
            request_fingerprint_sha256=digest,
            created_at=NOW,
            updated_at=NOW,
            items=[
                OrderItem(
                    client_item_id="crm-line-1",
                    product_id_snapshot=101,
                    variant_id_snapshot=201,
                    sku_snapshot="PRIVATE-SKU-1",
                    title_snapshot="Private garment title",
                    unit_price=Decimal("100.00"),
                    quantity=2,
                    line_total=Decimal("200.00"),
                    image_url_snapshot="/private-1.webp",
                    size_snapshot="M",
                    color_snapshot="black",
                    customization_snapshot={"private_measurement": "secret"},
                    sort_order=0,
                ),
                OrderItem(
                    client_item_id="crm-line-2",
                    product_id_snapshot=102,
                    variant_id_snapshot=None,
                    sku_snapshot=None,
                    title_snapshot="Private accessory title",
                    unit_price=Decimal("150.00"),
                    quantity=1,
                    line_total=Decimal("150.00"),
                    image_url_snapshot="/private-2.webp",
                    size_snapshot="",
                    color_snapshot="",
                    customization_snapshot=None,
                    sort_order=1,
                ),
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
            provider_idempotence_key="00000000-0000-4000-8000-000000000281",
            request_fingerprint_sha256=digest,
            payment_method="bank_card",
            status="succeeded",
            provider_payment_id="private-provider-payment-id",
            provider_created_at=NOW,
            captured_at=NOW,
            resolved_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(attempt)
        await session.flush()
        jobs = await FulfillmentOutboxService(database.settings).schedule_paid_order(
            session,
            order=order,
            payment_attempt_id=attempt.id,
            now=NOW,
        )
        crm_job = next(job for job in jobs if job.kind == "crm_order_project")
        await session.commit()
        return order.id, attempt.id, crm_job.id


def test_fulfillment_factory_can_enable_only_crm_intake(tmp_path: Path) -> None:
    processor = build_fulfillment_processor(_settings(tmp_path / "crm-factory.db"))

    assert tuple(kind.value for kind in processor.handlers) == ("crm_order_project",)


def test_crm_handoff_is_atomic_idempotent_and_pii_free(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "crm-intake.db")
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            order_id, payment_attempt_id, crm_job_id = await _seed_paid_order(database)
            processor: FulfillmentProcessor = build_fulfillment_processor(settings)

            async with database.session() as session:
                result = await processor.process_once(
                    session,
                    worker_id="crm-intake-1",
                    now=NOW,
                )
            assert result is not None
            assert result.job_id == crm_job_id
            assert result.kind == "crm_order_project"
            assert result.status == "completed"
            assert result.result_reference == "crm-project:1"

            async with database.session() as session:
                project = await session.scalar(select(CrmOrderProject))
                units = list(
                    await session.scalars(
                        select(CrmProductionUnit).order_by(
                            CrmProductionUnit.order_item_id,
                            CrmProductionUnit.unit_number,
                        )
                    )
                )
                events = list(await session.scalars(select(CrmProjectEvent)))
                unit_events = list(
                    await session.scalars(
                        select(CrmProductionUnitEvent).order_by(
                            CrmProductionUnitEvent.production_unit_id
                        )
                    )
                )
                job = await session.get(FulfillmentJob, crm_job_id)
                attempts = list(await session.scalars(select(FulfillmentJobAttempt)))
                assert project is not None and job is not None
                assert project.order_id == order_id
                assert project.source_fulfillment_job_id == crm_job_id
                assert project.source_payment_attempt_id == payment_attempt_id
                assert project.status == "queued"
                assert project.version == 1
                assert project.order_version_snapshot == 2
                assert project.items_count == 2
                assert project.units_count == 3
                assert project.total_price_snapshot == Decimal("400.00")
                assert project.currency == "RUB"
                assert [(unit.product_id_snapshot, unit.variant_id_snapshot) for unit in units] == [
                    (101, 201),
                    (101, 201),
                    (102, None),
                ]
                assert [unit.unit_number for unit in units] == [1, 2, 1]
                assert {unit.status for unit in units} == {"queued"}
                assert {unit.version for unit in units} == {1}
                assert len(unit_events) == 3
                assert {event.event_type for event in unit_events} == {"initialized"}
                assert {event.version for event in unit_events} == {1}
                assert len(events) == 1
                assert events[0].event_key == "project:1:version:1"
                assert events[0].from_status is None
                assert events[0].to_status == "queued"
                assert events[0].reason_code == "paid_order_intake"
                assert [attempt.status for attempt in attempts] == ["completed"]

                persisted = repr(
                    {
                        **project.__dict__,
                        **job.__dict__,
                        "units": [unit.__dict__ for unit in units],
                        "events": [event.__dict__ for event in events],
                    }
                )
                for private_value in (
                    "private@example.test",
                    "+79000000000",
                    "Private First",
                    "Private Last",
                    "Private address",
                    "Private garment title",
                    "private_measurement",
                    "private-provider-payment-id",
                ):
                    assert private_value not in persisted

                snapshots = tuple(
                    CrmProductionUnitSnapshot(
                        order_item_id=unit.order_item_id,
                        product_id_snapshot=unit.product_id_snapshot,
                        variant_id_snapshot=unit.variant_id_snapshot,
                        unit_number=unit.unit_number,
                    )
                    for unit in units
                )
                replay = await CrmProjectRepository().acquire_from_paid_order(
                    session,
                    order_id=project.order_id,
                    source_fulfillment_job_id=project.source_fulfillment_job_id,
                    source_payment_attempt_id=project.source_payment_attempt_id,
                    order_version_snapshot=project.order_version_snapshot,
                    total_price_snapshot=project.total_price_snapshot,
                    currency=project.currency,
                    payment_succeeded_at_snapshot=project.payment_succeeded_at_snapshot,
                    units=snapshots,
                    now=NOW,
                )
                assert replay.id == project.id

            async with database.session() as session:
                project = await session.scalar(select(CrmOrderProject))
                units = list(await session.scalars(select(CrmProductionUnit)))
                assert project is not None
                with pytest.raises(CrmProjectEvidenceConflictError, match="immutable evidence"):
                    await CrmProjectRepository().acquire_from_paid_order(
                        session,
                        order_id=project.order_id,
                        source_fulfillment_job_id=project.source_fulfillment_job_id,
                        source_payment_attempt_id=project.source_payment_attempt_id,
                        order_version_snapshot=project.order_version_snapshot,
                        total_price_snapshot=Decimal("401.00"),
                        currency=project.currency,
                        payment_succeeded_at_snapshot=project.payment_succeeded_at_snapshot,
                        units=tuple(
                            CrmProductionUnitSnapshot(
                                order_item_id=unit.order_item_id,
                                product_id_snapshot=unit.product_id_snapshot,
                                variant_id_snapshot=unit.variant_id_snapshot,
                                unit_number=unit.unit_number,
                            )
                            for unit in units
                        ),
                        now=NOW,
                    )
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_crm_project_lifecycle_is_versioned_and_audited(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "crm-lifecycle.db")
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            await _seed_paid_order(database)
            async with database.session() as session:
                result = await build_fulfillment_processor(settings).process_once(
                    session,
                    worker_id="crm-lifecycle-intake",
                    now=NOW,
                )
                assert result is not None and result.status == "completed"

            service = CrmProjectService()
            async with database.session() as session:
                started = await service.transition(
                    session,
                    project_id=1,
                    expected_version=1,
                    to_status=CrmProjectStatus.IN_PROGRESS,
                    reason_code="production_started",
                    actor_user_id=None,
                    now=NOW,
                )
                assert started.version == 2
                assert started.started_at is not None
                await session.commit()

            async with database.session() as session:
                with pytest.raises(CrmProjectVersionConflictError, match="version has changed"):
                    await service.transition(
                        session,
                        project_id=1,
                        expected_version=1,
                        to_status=CrmProjectStatus.ON_HOLD,
                        reason_code="material_missing",
                        actor_user_id=None,
                        now=NOW,
                    )
                units = list(await session.scalars(select(CrmProductionUnit)))
                for unit in units:
                    unit.status = CrmProductionUnitStatus.COMPLETED.value
                    unit.started_at = NOW
                    unit.closed_at = NOW
                completed = await service.transition(
                    session,
                    project_id=1,
                    expected_version=2,
                    to_status=CrmProjectStatus.COMPLETED,
                    reason_code="production_completed",
                    actor_user_id=None,
                    now=NOW,
                )
                assert completed.version == 3
                assert completed.closed_at is not None
                await session.commit()

            async with database.session() as session:
                with pytest.raises(CrmProjectStateError, match="cannot transition"):
                    await service.transition(
                        session,
                        project_id=1,
                        expected_version=3,
                        to_status=CrmProjectStatus.ON_HOLD,
                        reason_code="late_hold",
                        actor_user_id=None,
                        now=NOW,
                    )
                events = list(
                    await session.scalars(select(CrmProjectEvent).order_by(CrmProjectEvent.version))
                )
                assert [event.version for event in events] == [1, 2, 3]
                assert [event.to_status for event in events] == [
                    "queued",
                    "in_progress",
                    "completed",
                ]
                assert [event.reason_code for event in events] == [
                    "paid_order_intake",
                    "production_started",
                    "production_completed",
                ]
        finally:
            await database.shutdown()

    asyncio.run(scenario())
