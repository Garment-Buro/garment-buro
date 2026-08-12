from __future__ import annotations

import asyncio
import hashlib
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.orders.models import LegacyOrderImport, Order
from app.modules.payments.models import Payment, PaymentAttempt, PaymentEvent
from app.modules.payments.schemas import (
    ProviderPaymentEventObservation,
    ProviderPaymentSnapshot,
)
from app.modules.payments.security import (
    InvalidPaymentAttemptKeyError,
    digest_payment_attempt_key,
    is_trusted_yookassa_webhook_ip,
)
from app.modules.payments.service import (
    MAX_PAYMENT_WEBHOOK_BYTES,
    InvalidPaymentWebhookError,
    PaymentAttemptInProgressError,
    PaymentEventConflictError,
    PaymentIdempotencyConflictError,
    PaymentProviderMismatchError,
    PaymentService,
    PaymentStateError,
    UntrustedPaymentWebhookError,
)

PROVIDER_KEY_1 = "00000000-0000-4000-8000-000000000001"
PROVIDER_KEY_2 = "00000000-0000-4000-8000-000000000002"


def _settings(path: Path, *, environment: AppEnvironment = AppEnvironment.TEST) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "app_env": environment,
        "database_enabled": True,
        "database_url": f"sqlite+aiosqlite:///{path}",
    }
    if environment in {AppEnvironment.STAGING, AppEnvironment.PRODUCTION}:
        values.update(
            {
                "jwt_secret": "j" * 32,
                "cdek_client_id": "cdek-id",
                "cdek_client_secret": "cdek-secret",
                "yookassa_shop_id": "shop-id",
                "yookassa_api_key": "payment-secret",
                "smtp_password": "smtp-secret",
            }
        )
    return Settings(**values)


def _order(*, payment_method: str = "card", total: Decimal = Decimal("125.50")) -> Order:
    return Order(
        email="customer@example.test",
        email_normalized="customer@example.test",
        phone="+79000000000",
        first_name="Customer",
        delivery_city="Moscow",
        delivery_method="pickup",
        delivery_address="Showroom",
        payment_method=payment_method,
        items_subtotal=total,
        delivery_price=Decimal("0.00"),
        total_price=total,
        currency="RUB",
        status="new",
        payment_status="pending",
        version=1,
        request_fingerprint_sha256="f" * 64,
    )


def _snapshot(
    order_id: int,
    *,
    status: str = "pending",
    amount: str = "125.50",
    provider_payment_id: str = "provider-payment-1",
    test: bool = True,
) -> ProviderPaymentSnapshot:
    values: dict[str, object] = {
        "provider_payment_id": provider_payment_id,
        "status": status,
        "amount": amount,
        "currency": "RUB",
        "metadata_order_id": order_id,
        "payment_method": "bank_card",
        "paid": status in {"waiting_for_capture", "succeeded"},
        "test": test,
        "provider_created_at": "2026-08-11T12:00:00Z",
    }
    if status == "pending":
        values["confirmation_url"] = "https://yoomoney.ru/checkout/payment/1"
    if status == "succeeded":
        values["captured_at"] = "2026-08-11T12:01:00Z"
    if status == "canceled":
        values["cancellation_party"] = "yoo_money"
        values["cancellation_reason"] = "payment_expired"
    return ProviderPaymentSnapshot.model_validate(values)


def _webhook_body(
    order_id: int,
    *,
    amount: str = "125.50",
    provider_payment_id: str = "provider-payment-1",
    extra: str = "",
) -> bytes:
    return (
        "{"
        '"type":"notification",'
        '"event":"payment.succeeded",'
        '"object":{'
        f'"id":"{provider_payment_id}",'
        '"status":"succeeded",'
        f'"amount":{{"value":"{amount}","currency":"RUB"}},'
        f'"metadata":{{"order_id":"{order_id}"}},'
        '"payment_method":{"type":"bank_card","title":"Bank card *0000"},'
        '"paid":true,"test":true,'
        '"created_at":"2026-08-11T12:00:00Z",'
        '"captured_at":"2026-08-11T12:01:00Z"'
        f"{extra}"
        "}}"
    ).encode()


async def _create_schema(database: DatabaseManager) -> None:
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


def test_payment_attempt_is_durable_idempotent_and_fail_closed(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "attempt.db"))
        await database.startup()
        keys = iter((PROVIDER_KEY_1, PROVIDER_KEY_2))
        service = PaymentService(
            database.settings,
            provider_key_factory=lambda: next(keys),
        )
        try:
            await _create_schema(database)
            async with database.session() as session:
                first_order = _order()
                second_order = _order()
                imported_order = _order()
                session.add_all((first_order, second_order, imported_order))
                await session.flush()
                session.add(
                    LegacyOrderImport(
                        order_id=imported_order.id,
                        source_order_id=999,
                        source_row_sha256="a" * 64,
                        raw_cart_items="[]",
                        legacy_total_price=imported_order.total_price,
                        legacy_status="new",
                        legacy_payment_status="pending",
                    )
                )
                await session.commit()

            async with database.session() as session:
                prepared = await service.prepare_attempt(
                    session,
                    order_id=first_order.id,
                    client_attempt_key="payment_attempt_client_0001",
                )
                await session.commit()
            assert prepared.provider_idempotence_key == PROVIDER_KEY_1
            assert prepared.attempt_number == 1 and not prepared.replayed

            async with database.session() as session:
                replayed = await service.prepare_attempt(
                    session,
                    order_id=first_order.id,
                    client_attempt_key="payment_attempt_client_0001",
                )
                await session.commit()
            assert replayed.replayed and replayed.attempt_id == prepared.attempt_id
            assert replayed.provider_idempotence_key == PROVIDER_KEY_1

            with pytest.raises(PaymentIdempotencyConflictError):
                async with database.session() as session:
                    await service.prepare_attempt(
                        session,
                        order_id=second_order.id,
                        client_attempt_key="payment_attempt_client_0001",
                    )

            with pytest.raises(PaymentAttemptInProgressError):
                async with database.session() as session:
                    await service.prepare_attempt(
                        session,
                        order_id=first_order.id,
                        client_attempt_key="payment_attempt_client_0002",
                    )

            async with database.session() as session:
                unknown = await service.mark_creation_unknown(
                    session,
                    attempt_id=prepared.attempt_id,
                    error_code="provider_timeout",
                )
                await session.commit()
            assert unknown.status == "unknown"

            async with database.session() as session:
                pending = await service.record_provider_snapshot(
                    session,
                    attempt_id=prepared.attempt_id,
                    snapshot=_snapshot(first_order.id),
                )
                await session.commit()
            assert pending.status == "pending"

            async with database.session() as session:
                succeeded = await service.record_provider_snapshot(
                    session,
                    attempt_id=prepared.attempt_id,
                    snapshot=_snapshot(first_order.id, status="succeeded"),
                )
                await session.commit()
            assert succeeded.status == "succeeded"

            async with database.session() as session:
                attempt_before = await session.get(PaymentAttempt, prepared.attempt_id)
                assert attempt_before is not None
                first_resolved_at = attempt_before.resolved_at
                replayed_success = await service.record_provider_snapshot(
                    session,
                    attempt_id=prepared.attempt_id,
                    snapshot=_snapshot(first_order.id, status="succeeded"),
                )
                await session.commit()
            assert replayed_success.status == "succeeded"
            async with database.session() as session:
                attempt_after = await session.get(PaymentAttempt, prepared.attempt_id)
                assert attempt_after is not None and attempt_after.resolved_at == first_resolved_at

            with pytest.raises(PaymentStateError):
                async with database.session() as session:
                    await service.record_provider_snapshot(
                        session,
                        attempt_id=prepared.attempt_id,
                        snapshot=_snapshot(first_order.id, status="canceled"),
                    )

            with pytest.raises(PaymentStateError, match="Imported"):
                async with database.session() as session:
                    await service.prepare_attempt(
                        session,
                        order_id=imported_order.id,
                        client_attempt_key="payment_attempt_client_0099",
                    )

            async with database.session() as session:
                payment = await session.scalar(select(Payment))
                attempt = await session.scalar(select(PaymentAttempt))
                assert payment is not None and payment.status == "succeeded"
                assert attempt is not None
                assert attempt.client_key_digest_sha256 == digest_payment_attempt_key(
                    "payment_attempt_client_0001"
                )
                assert "payment_attempt_client_0001" not in repr(attempt.__dict__)
                assert attempt.provider_idempotence_key == PROVIDER_KEY_1
                assert attempt.last_error_code is None
                assert attempt.resolved_at is not None
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_canceled_attempt_allows_a_new_numbered_attempt(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "retry.db"))
        await database.startup()
        keys = iter((PROVIDER_KEY_1, PROVIDER_KEY_2))
        service = PaymentService(database.settings, provider_key_factory=lambda: next(keys))
        try:
            await _create_schema(database)
            async with database.session() as session:
                order = _order()
                session.add(order)
                await session.commit()
            async with database.session() as session:
                first = await service.prepare_attempt(
                    session,
                    order_id=order.id,
                    client_attempt_key="payment_attempt_retry_0001",
                )
                await service.record_provider_snapshot(
                    session,
                    attempt_id=first.attempt_id,
                    snapshot=_snapshot(order.id, status="canceled"),
                )
                await session.commit()
            async with database.session() as session:
                second = await service.prepare_attempt(
                    session,
                    order_id=order.id,
                    client_attempt_key="payment_attempt_retry_0002",
                )
                await session.commit()
            assert second.attempt_number == 2
            assert second.provider_idempotence_key == PROVIDER_KEY_2
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_payment_snapshot_environment_and_evidence_are_validated(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="must be marked paid"):
        ProviderPaymentSnapshot.model_validate(
            {
                **_snapshot(1, status="succeeded").model_dump(mode="json"),
                "paid": False,
            }
        )
    with pytest.raises(ValidationError, match="cancellation evidence"):
        ProviderPaymentSnapshot.model_validate(
            {
                **_snapshot(1, status="canceled").model_dump(mode="json"),
                "cancellation_reason": None,
            }
        )
    with pytest.raises(ValidationError, match="does not match"):
        ProviderPaymentEventObservation.model_validate(
            {
                "event_type": "payment.succeeded",
                "payment": _snapshot(1).model_dump(mode="json"),
            }
        )

    async def environment_scenario(environment: AppEnvironment, *, test: bool) -> None:
        database = DatabaseManager(
            _settings(tmp_path / f"{environment.value}.db", environment=environment)
        )
        await database.startup()
        service = PaymentService(
            database.settings,
            provider_key_factory=lambda: PROVIDER_KEY_1,
        )
        try:
            await _create_schema(database)
            async with database.session() as session:
                order = _order()
                session.add(order)
                await session.commit()
            async with database.session() as session:
                prepared = await service.prepare_attempt(
                    session,
                    order_id=order.id,
                    client_attempt_key=f"payment_attempt_{environment.value}_01",
                )
                with pytest.raises(PaymentProviderMismatchError):
                    await service.record_provider_snapshot(
                        session,
                        attempt_id=prepared.attempt_id,
                        snapshot=_snapshot(order.id, test=test),
                    )
        finally:
            await database.shutdown()

    asyncio.run(environment_scenario(AppEnvironment.STAGING, test=False))
    asyncio.run(environment_scenario(AppEnvironment.PRODUCTION, test=True))


def test_webhook_intake_is_ip_guarded_deduplicated_and_pii_minimized(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "events.db"))
        await database.startup()
        service = PaymentService(
            database.settings,
            provider_key_factory=lambda: PROVIDER_KEY_1,
        )
        try:
            await _create_schema(database)
            async with database.session() as session:
                order = _order()
                session.add(order)
                await session.commit()
            async with database.session() as session:
                prepared = await service.prepare_attempt(
                    session,
                    order_id=order.id,
                    client_attempt_key="payment_webhook_attempt_0001",
                )
                await service.record_provider_snapshot(
                    session,
                    attempt_id=prepared.attempt_id,
                    snapshot=_snapshot(order.id),
                )
                await session.commit()

            raw_body = _webhook_body(order.id, extra=',"secret_note":"do-not-store"')
            async with database.session() as session:
                received = await service.intake_event(
                    session,
                    raw_body=raw_body,
                    source_ip="185.71.76.1",
                )
                await session.commit()
            assert not received.duplicate and received.linked_attempt_id == prepared.attempt_id

            async with database.session() as session:
                duplicate = await service.intake_event(
                    session,
                    raw_body=_webhook_body(order.id, extra=',"ignored":"different-format"'),
                    source_ip="185.71.76.2",
                )
                await session.commit()
            assert duplicate.duplicate and duplicate.event_id == received.event_id

            with pytest.raises(PaymentEventConflictError):
                async with database.session() as session:
                    await service.intake_event(
                        session,
                        raw_body=_webhook_body(order.id, amount="125.51"),
                        source_ip="185.71.76.3",
                    )

            with pytest.raises(UntrustedPaymentWebhookError):
                async with database.session() as session:
                    await service.intake_event(
                        session,
                        raw_body=raw_body,
                        source_ip="203.0.113.10",
                    )
            with pytest.raises(ValueError, match="body size"):
                async with database.session() as session:
                    await service.intake_event(
                        session,
                        raw_body=b"x" * (MAX_PAYMENT_WEBHOOK_BYTES + 1),
                        source_ip="185.71.76.4",
                    )
            with pytest.raises(InvalidPaymentWebhookError):
                async with database.session() as session:
                    await service.intake_event(
                        session,
                        raw_body=b"not-json",
                        source_ip="185.71.76.5",
                    )

            async with database.session() as session:
                event = await session.scalar(select(PaymentEvent))
                count = int(
                    await session.scalar(select(func.count()).select_from(PaymentEvent)) or 0
                )
                assert event is not None and count == 1
                assert event.payload_sha256 == hashlib.sha256(raw_body).hexdigest()
                assert "do-not-store" not in repr(event.__dict__)
                assert event.status == "received" and event.attempts_count == 0
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_payment_security_rejects_invalid_keys_and_untrusted_ips() -> None:
    with pytest.raises(InvalidPaymentAttemptKeyError):
        digest_payment_attempt_key("short")
    assert is_trusted_yookassa_webhook_ip("77.75.156.11")
    assert is_trusted_yookassa_webhook_ip("::ffff:77.75.156.11")
    assert is_trusted_yookassa_webhook_ip("2a02:5180::1")
    assert not is_trusted_yookassa_webhook_ip("77.75.156.12")
    assert not is_trusted_yookassa_webhook_ip("invalid")
