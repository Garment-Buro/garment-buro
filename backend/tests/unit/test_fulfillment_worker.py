from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.fulfillment.contracts import FulfillmentHandlerError
from app.modules.fulfillment.handlers import OrderPaymentEmailHandler
from app.modules.fulfillment.models import (
    FulfillmentJob,
    FulfillmentJobAttempt,
    FulfillmentJobAttemptStatus,
    FulfillmentJobKind,
    FulfillmentJobStatus,
)
from app.modules.fulfillment.repository import FulfillmentRepository
from app.modules.fulfillment.service import FulfillmentOutboxService
from app.modules.fulfillment.worker import (
    FulfillmentProcessor,
    FulfillmentWorkerPolicy,
)
from app.modules.notifications.crypto import (
    EncryptedNotificationPayload,
    NotificationPayloadCodec,
)
from app.modules.notifications.models import NotificationOutbox
from app.modules.notifications.rendering import (
    InvalidNotificationPayloadError,
    NotificationRenderer,
    RenderedEmail,
)
from app.modules.notifications.service import (
    NotificationDispatcher,
    NotificationOutboxService,
    NotificationPolicy,
)
from app.modules.orders.models import Order, OrderItem
from app.modules.payments.models import Payment, PaymentAttempt

NOW = datetime(2026, 8, 12, 14, 0, tzinfo=timezone.utc)


def _encoded_key(fill: bytes = b"f") -> str:
    return base64.urlsafe_b64encode(fill * 32).decode()


def _settings(path: Path, *, max_attempts: int = 3) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
        notification_encryption_key=_encoded_key(),
        notification_max_attempts=2,
        fulfillment_outbox_enabled=True,
        fulfillment_email_enabled=True,
        fulfillment_max_attempts=max_attempts,
        fulfillment_retry_base_seconds=30,
        fulfillment_retry_cap_seconds=120,
        fulfillment_processing_timeout_seconds=300,
    )


async def _create_schema(database: DatabaseManager) -> None:
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def _seed_paid_order(
    database: DatabaseManager,
    *,
    sequence: int,
) -> tuple[int, int, dict[str, int]]:
    digest = hashlib.sha256(f"worker-evidence-{sequence}".encode()).hexdigest()
    async with database.session() as session:
        order = Order(
            email="Private@Example.Test",
            email_normalized="private@example.test",
            phone="+79000000000",
            first_name="<Покупатель>",
            delivery_city="Moscow",
            delivery_method="cdek_pickup",
            delivery_address="Private delivery address",
            cdek_point_code="PRIVATE-POINT",
            payment_method="card",
            items_subtotal=Decimal("200.00"),
            delivery_price=Decimal("25.00"),
            total_price=Decimal("225.00"),
            currency="RUB",
            status="processing",
            payment_status="paid",
            version=2,
            request_fingerprint_sha256=digest,
            created_at=NOW,
            updated_at=NOW,
            items=[
                OrderItem(
                    client_item_id=f"line-{sequence}",
                    product_id_snapshot=100 + sequence,
                    variant_id_snapshot=200 + sequence,
                    sku_snapshot=f"SKU-{sequence}",
                    title_snapshot="Платье <script>alert(1)</script>",
                    unit_price=Decimal("100.00"),
                    quantity=2,
                    line_total=Decimal("200.00"),
                    image_url_snapshot="https://cdn.example.test/item.webp",
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
            provider_idempotence_key=f"00000000-0000-4000-8000-{sequence:012d}",
            request_fingerprint_sha256=digest,
            payment_method="bank_card",
            status="succeeded",
            provider_payment_id=f"worker-provider-{sequence}",
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
        await session.commit()
        return order.id, attempt.id, {job.kind: job.id for job in jobs}


def _processor(settings: Settings, codec: NotificationPayloadCodec) -> FulfillmentProcessor:
    notification_service = NotificationOutboxService(
        codec,
        policy=NotificationPolicy(max_attempts=settings.notification_max_attempts),
    )
    return FulfillmentProcessor(
        settings,
        (OrderPaymentEmailHandler(notification_service),),
    )


@dataclass
class CapturingTransport:
    messages: list[RenderedEmail] = field(default_factory=list)

    async def send(self, message: RenderedEmail) -> str:
        self.messages.append(message)
        return f"smtp-{len(self.messages)}"


def test_email_handoff_is_encrypted_atomic_and_does_not_claim_other_kinds(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "email-handoff.db")
        database = DatabaseManager(settings)
        codec = NotificationPayloadCodec.from_base64_key(_encoded_key())
        await database.startup()
        try:
            await _create_schema(database)
            order_id, attempt_id, job_ids = await _seed_paid_order(database, sequence=1)
            processor = _processor(settings, codec)

            async with database.session() as session:
                result = await processor.process_once(
                    session,
                    worker_id="fulfillment-email-1",
                    now=NOW,
                )
            assert result is not None
            assert result.job_id == job_ids["customer_payment_email"]
            assert result.kind == "customer_payment_email"
            assert result.status == "completed"
            assert result.attempt_number == 1
            assert result.result_reference is not None
            assert result.result_reference.startswith("notification:")

            async with database.session() as session:
                jobs = list(
                    await session.scalars(select(FulfillmentJob).order_by(FulfillmentJob.kind))
                )
                attempts = list(await session.scalars(select(FulfillmentJobAttempt)))
                notification = await session.scalar(select(NotificationOutbox))
                assert notification is not None
                assert notification.template == "order_payment_confirmed"
                assert notification.status == "pending"
                assert notification.deduplication_key == (f"order:payment-confirmed:{order_id}")
                assert [attempt.status for attempt in attempts] == ["completed"]
                assert attempts[0].result_reference == result.result_reference
                assert {job.kind: job.status for job in jobs} == {
                    "cdek_order_create": "pending",
                    "crm_order_project": "pending",
                    "customer_payment_email": "completed",
                }
                persisted = repr(
                    {
                        **notification.__dict__,
                        **next(
                            job.__dict__ for job in jobs if job.kind == "customer_payment_email"
                        ),
                    }
                )
                for private_value in (
                    "private@example.test",
                    "+79000000000",
                    "Private delivery address",
                    "PRIVATE-POINT",
                    "<Покупатель>",
                ):
                    assert private_value not in persisted
                payload = codec.decrypt(
                    EncryptedNotificationPayload(
                        ciphertext=notification.payload_ciphertext or "",
                        nonce=notification.payload_nonce or "",
                        tag=notification.payload_tag or "",
                        key_version=notification.encryption_key_version,
                    )
                )
                assert payload["recipient"] == "private@example.test"
                assert payload["order_id"] == order_id
                assert payload["total_price"] == "225.00"
                assert payload["currency"] == "RUB"
                assert "delivery_address" not in payload
                assert "phone" not in payload

            transport = CapturingTransport()
            dispatcher = NotificationDispatcher(codec, transport)
            async with database.session() as session:
                dispatched = await dispatcher.dispatch_once(
                    session,
                    worker_id="smtp-worker-1",
                    now=NOW,
                )
            assert dispatched is not None and dispatched.status == "sent"
            assert len(transport.messages) == 1
            message = transport.messages[0]
            assert message.recipient == "private@example.test"
            assert message.subject == f"Заказ #{order_id} оплачен — garment-buro"
            assert "225.00 ₽" in message.html
            assert "&lt;Покупатель&gt;" in message.html
            assert "&lt;script&gt;alert(1)&lt;/script&gt;" in message.html
            assert "<script>alert(1)</script>" not in message.html

            async with database.session() as session:
                notification = await session.scalar(select(NotificationOutbox))
                assert notification is not None and notification.status == "sent"
                assert notification.payload_ciphertext is None
                assert notification.payload_nonce is None
                assert notification.payload_tag is None
                assert (
                    await processor.process_once(
                        session,
                        worker_id="fulfillment-email-1",
                        now=NOW + timedelta(seconds=1),
                    )
                    is None
                )
                assert (
                    int(
                        await session.scalar(select(func.count()).select_from(NotificationOutbox))
                        or 0
                    )
                    == 1
                )
                payment_attempt = await session.get(PaymentAttempt, attempt_id)
                assert payment_attempt is not None and payment_attempt.status == "succeeded"
        finally:
            await database.shutdown()

    asyncio.run(scenario())


@dataclass
class SequenceHandler:
    outcomes: list[Exception | str]
    kind: FulfillmentJobKind = FulfillmentJobKind.CUSTOMER_PAYMENT_EMAIL
    prepare_calls: int = 0
    apply_calls: int = 0

    async def prepare(self, session, job, *, now):
        del session, job, now
        self.prepare_calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def apply(self, session, job, prepared, *, now):
        del session, job, now
        self.apply_calls += 1
        return prepared


def test_transient_failure_retries_with_backoff_and_history(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "retry.db")
        database = DatabaseManager(settings)
        await database.startup()
        try:
            await _create_schema(database)
            _, _, job_ids = await _seed_paid_order(database, sequence=2)
            handler = SequenceHandler(
                [
                    FulfillmentHandlerError("handoff_temporarily_unavailable", permanent=False),
                    "local:handoff-2",
                ]
            )
            processor = FulfillmentProcessor(
                settings,
                (handler,),
                policy=FulfillmentWorkerPolicy(
                    retry_base=timedelta(seconds=30),
                    retry_cap=timedelta(seconds=120),
                    processing_timeout=timedelta(seconds=300),
                ),
            )

            async with database.session() as session:
                first = await processor.process_once(
                    session,
                    worker_id="retry-worker",
                    now=NOW,
                )
            assert first is not None and first.status == "retry"
            assert first.error_code == "handoff_temporarily_unavailable"

            async with database.session() as session:
                assert (
                    await processor.process_once(
                        session,
                        worker_id="retry-worker",
                        now=NOW + timedelta(seconds=29),
                    )
                    is None
                )
            async with database.session() as session:
                second = await processor.process_once(
                    session,
                    worker_id="retry-worker",
                    now=NOW + timedelta(seconds=30),
                )
            assert second is not None and second.status == "completed"
            assert second.attempt_number == 2
            assert second.result_reference == "local:handoff-2"
            assert handler.prepare_calls == 2 and handler.apply_calls == 1

            async with database.session() as session:
                attempts = list(
                    await session.scalars(
                        select(FulfillmentJobAttempt).order_by(FulfillmentJobAttempt.attempt_number)
                    )
                )
                assert [attempt.status for attempt in attempts] == [
                    "retry",
                    "completed",
                ]
                assert attempts[0].error_code == "handoff_temporarily_unavailable"
                assert attempts[1].result_reference == "local:handoff-2"
                other_jobs = list(
                    await session.scalars(
                        select(FulfillmentJob).where(
                            FulfillmentJob.id != job_ids["customer_payment_email"]
                        )
                    )
                )
                assert {job.status for job in other_jobs} == {"pending"}
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_stale_claim_is_abandoned_and_exhausted_claim_becomes_dead(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "stale.db", max_attempts=2)
        database = DatabaseManager(settings)
        repository = FulfillmentRepository()
        await database.startup()
        try:
            await _create_schema(database)
            _, _, first_jobs = await _seed_paid_order(database, sequence=3)
            _, _, second_jobs = await _seed_paid_order(database, sequence=4)
            async with database.session() as session:
                first_claim = await repository.claim_next(
                    session,
                    kinds=(FulfillmentJobKind.CUSTOMER_PAYMENT_EMAIL,),
                    now=NOW,
                    stale_before=NOW - timedelta(minutes=5),
                    worker_id="crashed-worker",
                )
                assert first_claim is not None
                await session.commit()

            handler = SequenceHandler(["local:recovered"])
            processor = FulfillmentProcessor(settings, (handler,), repository=repository)
            recovered_at = NOW + timedelta(seconds=301)
            async with database.session() as session:
                recovered = await processor.process_once(
                    session,
                    worker_id="healthy-worker",
                    now=recovered_at,
                )
            assert recovered is not None and recovered.status == "completed"
            assert recovered.job_id == first_jobs["customer_payment_email"]
            assert recovered.attempt_number == 2

            async with database.session() as session:
                second_job = await session.get(
                    FulfillmentJob,
                    second_jobs["customer_payment_email"],
                )
                assert second_job is not None
                second_job.max_attempts = 1
                await session.commit()
            async with database.session() as session:
                exhausted_claim = await repository.claim_next(
                    session,
                    kinds=(FulfillmentJobKind.CUSTOMER_PAYMENT_EMAIL,),
                    now=recovered_at,
                    stale_before=recovered_at - timedelta(minutes=5),
                    worker_id="last-crashed-worker",
                )
                assert exhausted_claim is not None
                await session.commit()
            async with database.session() as session:
                exhausted = await processor.process_once(
                    session,
                    worker_id="healthy-worker",
                    now=recovered_at + timedelta(seconds=301),
                )
            assert exhausted is not None
            assert exhausted.job_id == second_jobs["customer_payment_email"]
            assert exhausted.status == "dead"
            assert exhausted.error_code == "fulfillment_stale_exhausted"
            assert exhausted.attempt_number == 1
            assert handler.prepare_calls == 1

            async with database.session() as session:
                attempts = list(
                    await session.scalars(
                        select(FulfillmentJobAttempt)
                        .where(
                            FulfillmentJobAttempt.job_id.in_(
                                (
                                    first_jobs["customer_payment_email"],
                                    second_jobs["customer_payment_email"],
                                )
                            )
                        )
                        .order_by(
                            FulfillmentJobAttempt.job_id,
                            FulfillmentJobAttempt.attempt_number,
                        )
                    )
                )
                assert [attempt.status for attempt in attempts] == [
                    FulfillmentJobAttemptStatus.ABANDONED.value,
                    FulfillmentJobAttemptStatus.COMPLETED.value,
                    FulfillmentJobAttemptStatus.ABANDONED.value,
                ]
                assert attempts[0].error_code == "worker_stale"
                assert attempts[2].error_code == "worker_stale"
        finally:
            await database.shutdown()

    asyncio.run(scenario())


class EnqueueThenFailHandler(OrderPaymentEmailHandler):
    async def apply(self, session, job, prepared, *, now):
        await super().apply(session, job, prepared, now=now)
        raise FulfillmentHandlerError("local_handoff_failed", permanent=False)


def test_notification_handoff_rolls_back_with_failed_fulfillment_attempt(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "atomic-handoff.db")
        database = DatabaseManager(settings)
        codec = NotificationPayloadCodec.from_base64_key(_encoded_key())
        notification_service = NotificationOutboxService(codec)
        await database.startup()
        try:
            await _create_schema(database)
            await _seed_paid_order(database, sequence=5)
            failing = FulfillmentProcessor(
                settings,
                (EnqueueThenFailHandler(notification_service),),
            )
            async with database.session() as session:
                failed = await failing.process_once(
                    session,
                    worker_id="atomic-worker",
                    now=NOW,
                )
            assert failed is not None and failed.status == FulfillmentJobStatus.RETRY.value
            assert failed.error_code == "local_handoff_failed"
            async with database.session() as session:
                assert (
                    int(
                        await session.scalar(select(func.count()).select_from(NotificationOutbox))
                        or 0
                    )
                    == 0
                )

            healthy = _processor(settings, codec)
            async with database.session() as session:
                completed = await healthy.process_once(
                    session,
                    worker_id="atomic-worker",
                    now=NOW + timedelta(seconds=30),
                )
            assert completed is not None and completed.status == "completed"
            async with database.session() as session:
                assert (
                    int(
                        await session.scalar(select(func.count()).select_from(NotificationOutbox))
                        or 0
                    )
                    == 1
                )
                attempts = list(
                    await session.scalars(
                        select(FulfillmentJobAttempt).order_by(FulfillmentJobAttempt.attempt_number)
                    )
                )
                assert [attempt.status for attempt in attempts] == [
                    "retry",
                    "completed",
                ]
                assert attempts[0].error_code == "local_handoff_failed"
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_order_payment_renderer_rejects_invalid_money_and_item_contract() -> None:
    renderer = NotificationRenderer()
    payload: dict[str, object] = {
        "recipient": "customer@example.test",
        "order_id": 77,
        "first_name": "Customer",
        "items": [
            {
                "title": "Платье",
                "size": "M",
                "color": "black",
                "quantity": 2,
                "unit_price": "100.00",
                "line_total": "200.00",
            }
        ],
        "items_subtotal": "200.00",
        "delivery_price": "25.00",
        "total_price": "225.00",
        "currency": "RUB",
    }
    rendered = renderer.render_email("order_payment_confirmed", payload)
    assert rendered.recipient == "customer@example.test"
    assert "Итого: 225.00 ₽" in rendered.html

    invalid_total = copy.deepcopy(payload)
    invalid_total["total_price"] = "224.99"
    with pytest.raises(InvalidNotificationPayloadError, match="totals"):
        renderer.render_email("order_payment_confirmed", invalid_total)

    invalid_line = copy.deepcopy(payload)
    assert isinstance(invalid_line["items"], list)
    invalid_line["items"][0]["line_total"] = "199.99"
    with pytest.raises(InvalidNotificationPayloadError, match="item totals"):
        renderer.render_email("order_payment_confirmed", invalid_line)

    invalid_money = copy.deepcopy(payload)
    invalid_money["delivery_price"] = "NaN"
    with pytest.raises(InvalidNotificationPayloadError, match="money"):
        renderer.render_email("order_payment_confirmed", invalid_money)
