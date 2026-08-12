from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.delivery.crypto import (
    CdekRequestCodec,
    CdekRequestDecryptionError,
    EncryptedCdekRequest,
)
from app.modules.delivery.factory import build_cdek_request_codec
from app.modules.delivery.handlers import CdekShipmentHandoffHandler
from app.modules.delivery.models import CdekShipment, CdekShipmentAttempt, CdekShipmentEvent
from app.modules.delivery.provider import CdekOrderSnapshot, CdekProviderError
from app.modules.delivery.repository import CdekShipmentRepository
from app.modules.delivery.worker import CdekCreationDisabledError, CdekShipmentProcessor
from app.modules.fulfillment.factory import build_fulfillment_processor
from app.modules.fulfillment.models import FulfillmentJob, FulfillmentJobAttempt
from app.modules.fulfillment.service import FulfillmentOutboxService
from app.modules.fulfillment.worker import FulfillmentProcessor
from app.modules.orders.models import Order, OrderItem
from app.modules.payments.models import Payment, PaymentAttempt

NOW = datetime(2026, 8, 12, 16, 0, tzinfo=timezone.utc)


def _encoded_key(fill: bytes = b"c") -> str:
    return base64.urlsafe_b64encode(fill * 32).decode()


def _settings(
    path: Path,
    *,
    fulfillment_cdek_enabled: bool = False,
    cdek_creation_enabled: bool = False,
) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
        fulfillment_outbox_enabled=True,
        fulfillment_cdek_enabled=(fulfillment_cdek_enabled or cdek_creation_enabled),
        cdek_creation_enabled=cdek_creation_enabled,
        fulfillment_max_attempts=3,
        cdek_request_encryption_key=_encoded_key(),
        cdek_client_id="cdek-test-client",
        cdek_client_secret="cdek-test-secret",
        cdek_sender_name="GARMENT BURO",
        cdek_sender_city_code=245,
        cdek_warehouse_to_warehouse_tariff=136,
        cdek_warehouse_to_door_tariff=137,
        cdek_max_packages=10,
        cdek_creation_max_attempts=4,
    )


def test_fulfillment_factory_can_enable_only_the_cdek_handoff(tmp_path: Path) -> None:
    settings = _settings(
        tmp_path / "cdek-factory.db",
        fulfillment_cdek_enabled=True,
    )

    processor = build_fulfillment_processor(settings)

    assert tuple(kind.value for kind in processor.handlers) == ("cdek_order_create",)


def test_cdek_request_encryption_detects_tampering_and_row_swaps() -> None:
    body = b'{"number":"GB-0000000026"}'
    digest = hashlib.sha256(body).hexdigest()
    codec = CdekRequestCodec.from_base64_key(_encoded_key())
    encrypted = codec.encrypt(
        body,
        order_id=26,
        request_sha256=digest,
        schema_version=1,
    )

    assert (
        codec.decrypt(
            encrypted,
            order_id=26,
            request_sha256=digest,
            schema_version=1,
        )
        == body
    )
    with pytest.raises(CdekRequestDecryptionError, match="authentication"):
        codec.decrypt(
            encrypted,
            order_id=27,
            request_sha256=digest,
            schema_version=1,
        )
    replacement = "A" if encrypted.tag[0] != "A" else "B"
    with pytest.raises(CdekRequestDecryptionError, match="authentication"):
        codec.decrypt(
            EncryptedCdekRequest(
                ciphertext=encrypted.ciphertext,
                nonce=encrypted.nonce,
                tag=f"{replacement}{encrypted.tag[1:]}",
                key_version=encrypted.key_version,
            ),
            order_id=26,
            request_sha256=digest,
            schema_version=1,
        )


async def _seed_paid_order(database: DatabaseManager) -> tuple[int, int, int]:
    digest = hashlib.sha256(b"cdek-foundation-payment").hexdigest()
    async with database.session() as session:
        order = Order(
            email="Private@Example.Test",
            email_normalized="private@example.test",
            phone="+7 (900) 000-00-00",
            first_name="Иван",
            last_name="Иванов",
            patronymic="Иванович",
            delivery_city="Москва",
            delivery_method="cdek_pickup",
            delivery_address="Private pickup address",
            cdek_point_code="MSK123",
            payment_method="card",
            items_subtotal=Decimal("200.50"),
            delivery_price=Decimal("50.00"),
            total_price=Decimal("250.50"),
            currency="RUB",
            status="processing",
            payment_status="paid",
            version=2,
            request_fingerprint_sha256=digest,
            created_at=NOW,
            updated_at=NOW,
            items=[
                OrderItem(
                    client_item_id="cdek-line-1",
                    product_id_snapshot=101,
                    variant_id_snapshot=201,
                    sku_snapshot="SKU-CDEK-1",
                    title_snapshot="Платье",
                    unit_price=Decimal("100.25"),
                    quantity=2,
                    line_total=Decimal("200.50"),
                    image_url_snapshot="/media/private.webp",
                    size_snapshot="M",
                    color_snapshot="black",
                    customization_snapshot=None,
                    delivery_weight_kg_snapshot=Decimal("0.425"),
                    delivery_height_cm_snapshot=Decimal("9.10"),
                    delivery_width_cm_snapshot=Decimal("21.20"),
                    delivery_length_cm_snapshot=Decimal("30.30"),
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
            provider_idempotence_key="00000000-0000-4000-8000-000000000260",
            request_fingerprint_sha256=digest,
            payment_method="bank_card",
            status="succeeded",
            provider_payment_id="payment-for-cdek-26",
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
        cdek_job = next(job for job in jobs if job.kind == "cdek_order_create")
        await session.commit()
        return order.id, attempt.id, cdek_job.id


def test_cdek_handoff_persists_encrypted_canonical_request_once(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "cdek-handoff.db")
        database = DatabaseManager(settings)
        codec = build_cdek_request_codec(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            order_id, payment_attempt_id, cdek_job_id = await _seed_paid_order(database)
            processor = FulfillmentProcessor(
                settings,
                (CdekShipmentHandoffHandler(settings, codec),),
            )

            async with database.session() as session:
                result = await processor.process_once(
                    session,
                    worker_id="cdek-handoff-1",
                    now=NOW,
                )
            assert result is not None
            assert result.job_id == cdek_job_id
            assert result.kind == "cdek_order_create"
            assert result.status == "completed"
            assert result.result_reference == "cdek-shipment:1"

            async with database.session() as session:
                shipment = await session.scalar(select(CdekShipment))
                event = await session.scalar(select(CdekShipmentEvent))
                job = await session.get(FulfillmentJob, cdek_job_id)
                attempts = list(await session.scalars(select(FulfillmentJobAttempt)))
                assert shipment is not None and event is not None and job is not None
                assert shipment.order_id == order_id
                assert shipment.source_fulfillment_job_id == cdek_job_id
                assert shipment.source_payment_attempt_id == payment_attempt_id
                assert shipment.client_order_number == f"GB-{order_id:010d}"
                assert shipment.status == "pending"
                assert shipment.attempts_count == 0
                assert shipment.max_attempts == 4
                assert event.event_type == "prepared"
                assert event.event_key == f"prepared:{shipment.request_sha256}"
                assert job.status == "completed"
                assert [attempt.status for attempt in attempts] == ["completed"]

                persisted = repr({**shipment.__dict__, **event.__dict__, **job.__dict__})
                for private_value in (
                    "private@example.test",
                    "+79000000000",
                    "Private pickup address",
                    "Иван Иванов Иванович",
                ):
                    assert private_value not in persisted

                body = codec.decrypt(
                    EncryptedCdekRequest(
                        ciphertext=shipment.request_ciphertext,
                        nonce=shipment.request_nonce,
                        tag=shipment.request_tag,
                        key_version=shipment.encryption_key_version,
                    ),
                    order_id=shipment.order_id,
                    request_sha256=shipment.request_sha256,
                    schema_version=shipment.request_schema_version,
                )
                assert hashlib.sha256(body).hexdigest() == shipment.request_sha256
                payload = json.loads(body)
                assert payload["number"] == shipment.client_order_number
                assert payload["tariff_code"] == 136
                assert payload["delivery_point"] == "MSK123"
                assert payload["recipient"] == {
                    "email": "private@example.test",
                    "name": "Иван Иванов Иванович",
                    "phones": [{"number": "+79000000000"}],
                }
                assert len(payload["packages"]) == 2
                assert [package["number"] for package in payload["packages"]] == [
                    f"GB-{order_id:010d}-001-001",
                    f"GB-{order_id:010d}-001-002",
                ]
                assert payload["packages"][0] == {
                    "height": 10,
                    "items": [
                        {
                            "amount": 1,
                            "cost": 100.25,
                            "name": "Платье",
                            "payment": {"value": 0},
                            "ware_key": "SKU-CDEK-1",
                            "weight": 425,
                        }
                    ],
                    "length": 31,
                    "number": f"GB-{order_id:010d}-001-001",
                    "weight": 425,
                    "width": 22,
                }

            async with database.session() as session:
                assert (
                    await processor.process_once(
                        session,
                        worker_id="cdek-handoff-1",
                        now=NOW,
                    )
                    is None
                )
                assert (
                    int(await session.scalar(select(func.count()).select_from(CdekShipment)) or 0)
                    == 1
                )
                assert (
                    int(
                        await session.scalar(select(func.count()).select_from(CdekShipmentEvent))
                        or 0
                    )
                    == 1
                )
        finally:
            await database.shutdown()

    asyncio.run(scenario())


class FakeCdekProvider:
    def __init__(self, outcomes: list[CdekOrderSnapshot | Exception]) -> None:
        self.outcomes = list(outcomes)
        self.created_bodies: list[bytes] = []

    async def create_order(self, request_body: bytes) -> CdekOrderSnapshot:
        self.created_bodies.append(request_body)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def get_order(self, provider_uuid: str) -> CdekOrderSnapshot:
        raise AssertionError(f"Unexpected CDEK GET for {provider_uuid}")


def test_cdek_worker_refuses_to_run_while_default_off(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "cdek-worker-disabled.db")
        database = DatabaseManager(settings)
        processor = CdekShipmentProcessor(
            settings,
            FakeCdekProvider([]),
            build_cdek_request_codec(settings),
        )
        await database.startup()
        try:
            with pytest.raises(CdekCreationDisabledError, match="disabled"):
                async with database.session() as session:
                    await processor.process_once(
                        session,
                        worker_id="disabled-cdek-worker",
                        now=NOW,
                    )
        finally:
            await database.shutdown()

    asyncio.run(scenario())


async def _prepare_cdek_shipment(
    database: DatabaseManager,
    settings: Settings,
    codec: CdekRequestCodec,
) -> int:
    await _seed_paid_order(database)
    handoff = FulfillmentProcessor(
        settings,
        (CdekShipmentHandoffHandler(settings, codec),),
    )
    async with database.session() as session:
        result = await handoff.process_once(
            session,
            worker_id="cdek-handoff-for-provider",
            now=NOW,
        )
        assert result is not None and result.status == "completed"
    async with database.session() as session:
        shipment_id = await session.scalar(select(CdekShipment.id))
        assert shipment_id is not None
        return shipment_id


def test_cdek_worker_retries_only_known_safe_failures_with_exact_bytes(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(
            tmp_path / "cdek-worker-retry.db",
            cdek_creation_enabled=True,
        )
        database = DatabaseManager(settings)
        codec = build_cdek_request_codec(settings)
        provider = FakeCdekProvider(
            [
                CdekProviderError("oauth_unavailable", retryable=True),
                CdekOrderSnapshot(
                    provider_uuid="cdek-created-260",
                    cdek_number="1106153417",
                    status_code="ACCEPTED",
                    status_name="Принят",
                ),
            ]
        )
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            shipment_id = await _prepare_cdek_shipment(database, settings, codec)
            processor = CdekShipmentProcessor(settings, provider, codec)

            async with database.session() as session:
                first = await processor.process_once(
                    session,
                    worker_id="cdek-provider-1",
                    now=NOW,
                )
            assert first is not None
            assert first.status == "retry"
            assert first.error_code == "oauth_unavailable"

            async with database.session() as session:
                assert (
                    await processor.process_once(
                        session,
                        worker_id="cdek-provider-1",
                        now=NOW + timedelta(seconds=29),
                    )
                    is None
                )
                second = await processor.process_once(
                    session,
                    worker_id="cdek-provider-1",
                    now=NOW + timedelta(seconds=30),
                )
            assert second is not None
            assert second.status == "created"
            assert second.provider_uuid == "cdek-created-260"
            assert provider.created_bodies[0] == provider.created_bodies[1]

            async with database.session() as session:
                shipment = await session.get(CdekShipment, shipment_id)
                attempts = list(
                    await session.scalars(
                        select(CdekShipmentAttempt).order_by(CdekShipmentAttempt.attempt_number)
                    )
                )
                assert shipment is not None
                assert shipment.status == "created"
                assert shipment.provider_uuid == "cdek-created-260"
                assert shipment.provider_cdek_number == "1106153417"
                assert shipment.provider_status_code == "ACCEPTED"
                assert [attempt.status for attempt in attempts] == ["retry", "created"]
                assert [attempt.request_sha256 for attempt in attempts] == [
                    shipment.request_sha256,
                    shipment.request_sha256,
                ]
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_cdek_worker_quarantines_ambiguous_create_without_replay(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(
            tmp_path / "cdek-worker-unknown.db",
            cdek_creation_enabled=True,
        )
        database = DatabaseManager(settings)
        codec = build_cdek_request_codec(settings)
        provider = FakeCdekProvider(
            [
                CdekProviderError(
                    "timeout",
                    retryable=True,
                    outcome_unknown=True,
                )
            ]
        )
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            shipment_id = await _prepare_cdek_shipment(database, settings, codec)
            processor = CdekShipmentProcessor(settings, provider, codec)

            async with database.session() as session:
                result = await processor.process_once(
                    session,
                    worker_id="cdek-provider-unknown",
                    now=NOW,
                )
            assert result is not None
            assert result.status == "unknown"
            assert result.error_code == "timeout"

            async with database.session() as session:
                assert (
                    await processor.process_once(
                        session,
                        worker_id="cdek-provider-unknown",
                        now=NOW + timedelta(days=1),
                    )
                    is None
                )
                shipment = await session.get(CdekShipment, shipment_id)
                attempts = list(await session.scalars(select(CdekShipmentAttempt)))
                assert shipment is not None
                assert shipment.status == "unknown"
                assert shipment.attempts_count == 1
                assert [attempt.status for attempt in attempts] == ["unknown"]
            assert len(provider.created_bodies) == 1
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_cdek_worker_marks_provider_rejection_dead_without_replay(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(
            tmp_path / "cdek-worker-rejected.db",
            cdek_creation_enabled=True,
        )
        database = DatabaseManager(settings)
        codec = build_cdek_request_codec(settings)
        provider = FakeCdekProvider(
            [
                CdekProviderError(
                    "request_rejected",
                    retryable=False,
                    rejected=True,
                    provider_uuid="cdek-rejected-260",
                )
            ]
        )
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            shipment_id = await _prepare_cdek_shipment(database, settings, codec)
            processor = CdekShipmentProcessor(settings, provider, codec)

            async with database.session() as session:
                result = await processor.process_once(
                    session,
                    worker_id="cdek-provider-rejected",
                    now=NOW,
                )
            assert result is not None
            assert result.status == "dead"
            assert result.provider_uuid == "cdek-rejected-260"
            assert result.error_code == "request_rejected"

            async with database.session() as session:
                assert (
                    await processor.process_once(
                        session,
                        worker_id="cdek-provider-rejected",
                        now=NOW + timedelta(days=1),
                    )
                    is None
                )
                shipment = await session.get(CdekShipment, shipment_id)
                attempt = await session.scalar(select(CdekShipmentAttempt))
                assert shipment is not None and attempt is not None
                assert shipment.status == "dead"
                assert attempt.status == "dead"
                assert attempt.provider_uuid == "cdek-rejected-260"
            assert len(provider.created_bodies) == 1
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_cdek_worker_quarantines_stale_processing_before_provider_call(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(
            tmp_path / "cdek-worker-stale.db",
            cdek_creation_enabled=True,
        )
        database = DatabaseManager(settings)
        codec = build_cdek_request_codec(settings)
        provider = FakeCdekProvider([])
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            shipment_id = await _prepare_cdek_shipment(database, settings, codec)
            async with database.session() as session:
                claimed = await CdekShipmentRepository().claim_next(
                    session,
                    now=NOW,
                    worker_id="crashed-cdek-worker",
                )
                assert claimed is not None
                await session.commit()

            processor = CdekShipmentProcessor(settings, provider, codec)
            async with database.session() as session:
                result = await processor.process_once(
                    session,
                    worker_id="replacement-cdek-worker",
                    now=NOW + timedelta(seconds=settings.cdek_processing_timeout_seconds),
                )
            assert result is not None
            assert result.shipment_id == shipment_id
            assert result.status == "unknown"
            assert result.error_code == "processing_stale_unknown"
            assert provider.created_bodies == []

            async with database.session() as session:
                shipment = await session.get(CdekShipment, shipment_id)
                attempts = list(await session.scalars(select(CdekShipmentAttempt)))
                assert shipment is not None
                assert shipment.status == "unknown"
                assert shipment.locked_at is None
                assert shipment.locked_by is None
                assert [attempt.status for attempt in attempts] == ["unknown"]
        finally:
            await database.shutdown()

    asyncio.run(scenario())
