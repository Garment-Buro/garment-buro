from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.fulfillment.models import FulfillmentJob
from app.modules.fulfillment.repository import FulfillmentEvidenceConflictError
from app.modules.fulfillment.service import (
    FulfillmentOutboxService,
    FulfillmentStateError,
)
from app.modules.orders.models import LegacyOrderImport, Order
from app.modules.payments.models import Payment, PaymentAttempt

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)


def _settings(path: Path, *, enabled: bool = True) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        public_base_url="https://shop.example.test",
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
        minio_enabled=True,
        minio_access_key="test-access",
        minio_secret_key="test-secret",
        minio_public_base_url="https://cdn.example.test",
        catalog_reads_enabled=True,
        catalog_migration_fingerprint="a" * 64,
        identity_api_enabled=True,
        identity_migration_fingerprint="b" * 64,
        jwt_secret="j" * 32,
        identity_otp_pepper="p" * 32,
        notification_encryption_key=("bm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm4="),
        order_reads_enabled=True,
        order_migration_fingerprint="c" * 64,
        yookassa_shop_id="shop-id",
        yookassa_api_key="payment-secret",
        payment_creation_enabled=True,
        yookassa_receipt_tax_system_code=1,
        yookassa_receipt_product_vat_code=1,
        yookassa_receipt_delivery_vat_code=1,
        yookassa_receipt_product_payment_mode="full_payment",
        yookassa_receipt_delivery_payment_mode="full_payment",
        yookassa_receipt_product_subject="non_marked",
        yookassa_receipt_delivery_subject="service",
        checkout_v2_enabled=True,
        fulfillment_outbox_enabled=enabled,
    )


async def _create_schema(database: DatabaseManager) -> None:
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def _seed_paid_order(
    database: DatabaseManager,
    *,
    sequence: int,
    email: str | None = "customer@example.test",
    delivery_method: str = "cdek_pickup",
    legacy: bool = False,
) -> tuple[int, int]:
    digest = hashlib.sha256(f"evidence-{sequence}".encode()).hexdigest()
    async with database.session() as session:
        order = Order(
            email=email,
            email_normalized=email,
            phone=f"+790000000{sequence:02d}",
            first_name="Customer",
            delivery_city="Moscow",
            delivery_method=delivery_method,
            delivery_address="Private address",
            cdek_point_code=f"POINT-{sequence}",
            payment_method="card",
            items_subtotal=Decimal("100.00"),
            delivery_price=Decimal("25.00"),
            total_price=Decimal("125.00"),
            currency="RUB",
            status="processing",
            payment_status="paid",
            version=2,
            request_fingerprint_sha256=digest,
            created_at=NOW,
            updated_at=NOW,
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
            provider_payment_id=f"provider-payment-{sequence}",
            provider_created_at=NOW,
            captured_at=NOW,
            resolved_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(attempt)
        await session.flush()
        if legacy:
            session.add(
                LegacyOrderImport(
                    order_id=order.id,
                    source_order_id=sequence,
                    source_row_sha256=hashlib.sha256(f"legacy-{sequence}".encode()).hexdigest(),
                    raw_cart_items="[]",
                    legacy_total_price=order.total_price,
                )
            )
        await session.commit()
        return order.id, attempt.id


def test_outbox_selects_commands_without_pii_and_replays_idempotently(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "fulfillment.db"))
        await database.startup()
        try:
            await _create_schema(database)
            order_id, attempt_id = await _seed_paid_order(database, sequence=1)
            service = FulfillmentOutboxService(database.settings)

            for _ in range(2):
                async with database.session() as session:
                    order = await session.get(Order, order_id)
                    assert order is not None
                    jobs = await service.schedule_paid_order(
                        session,
                        order=order,
                        payment_attempt_id=attempt_id,
                        now=NOW,
                    )
                    await session.commit()
                    assert {job.kind for job in jobs} == {
                        "cdek_order_create",
                        "crm_order_project",
                        "customer_payment_email",
                    }

            async with database.session() as session:
                jobs = list(await session.scalars(select(FulfillmentJob)))
                assert len(jobs) == 3
                assert {job.source_payment_attempt_id for job in jobs} == {attempt_id}
                persisted = repr([job.__dict__ for job in jobs])
                for private_value in (
                    "customer@example.test",
                    "+79000000001",
                    "Private address",
                    "POINT-1",
                ):
                    assert private_value not in persisted
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_outbox_requires_verified_payment_evidence_and_keeps_original_source(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "evidence.db"))
        await database.startup()
        try:
            await _create_schema(database)
            order_id, attempt_id = await _seed_paid_order(database, sequence=2)
            service = FulfillmentOutboxService(database.settings)
            async with database.session() as session:
                order = await session.get(Order, order_id)
                assert order is not None
                with pytest.raises(FulfillmentStateError, match="evidence is missing"):
                    await service.schedule_paid_order(
                        session,
                        order=order,
                        payment_attempt_id=attempt_id + 10_000,
                    )
                await session.rollback()

            async with database.session() as session:
                order = await session.get(Order, order_id)
                assert order is not None
                await service.schedule_paid_order(
                    session,
                    order=order,
                    payment_attempt_id=attempt_id,
                )
                payment = await session.scalar(select(Payment).where(Payment.order_id == order_id))
                assert payment is not None
                conflicting = PaymentAttempt(
                    payment_id=payment.id,
                    attempt_number=2,
                    client_key_digest_sha256="d" * 64,
                    provider_idempotence_key="00000000-0000-4000-8000-000000000222",
                    request_fingerprint_sha256="e" * 64,
                    payment_method="bank_card",
                    status="succeeded",
                    provider_payment_id="provider-payment-conflict",
                    provider_created_at=NOW,
                    captured_at=NOW,
                    resolved_at=NOW,
                    created_at=NOW,
                    updated_at=NOW,
                )
                session.add(conflicting)
                await session.flush()
                with pytest.raises(FulfillmentEvidenceConflictError):
                    await service.schedule_paid_order(
                        session,
                        order=order,
                        payment_attempt_id=conflicting.id,
                    )
                await session.rollback()
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_seeder_is_bounded_idempotent_and_excludes_legacy_orders(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = DatabaseManager(_settings(tmp_path / "seed.db"))
        await database.startup()
        try:
            await _create_schema(database)
            target_id, _ = await _seed_paid_order(database, sequence=3)
            minimal_id, _ = await _seed_paid_order(
                database,
                sequence=4,
                email=None,
                delivery_method="courier",
            )
            legacy_id, _ = await _seed_paid_order(
                database,
                sequence=5,
                legacy=True,
            )
            service = FulfillmentOutboxService(database.settings)

            async with database.session() as session:
                assert await service.seed_paid_orders(session, limit=100, now=NOW) == 4
                await session.commit()
            async with database.session() as session:
                assert await service.seed_paid_orders(session, limit=100, now=NOW) == 0
                await session.commit()
                rows = await session.execute(
                    select(FulfillmentJob.order_id, func.count())
                    .group_by(FulfillmentJob.order_id)
                    .order_by(FulfillmentJob.order_id)
                )
                grouped = dict(rows.tuples().all())
                assert grouped == {target_id: 3, minimal_id: 1}
                assert legacy_id not in grouped

            with pytest.raises(ValueError, match="between 1 and 1000"):
                async with database.session() as session:
                    await service.seed_paid_orders(session, limit=0)
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_disabled_outbox_is_a_compatibility_noop(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "disabled.db", enabled=False)
        database = DatabaseManager(settings)
        await database.startup()
        try:
            await _create_schema(database)
            order_id, _ = await _seed_paid_order(database, sequence=6)
            async with database.session() as session:
                order = await session.get(Order, order_id)
                assert order is not None
                assert (
                    await FulfillmentOutboxService(settings).schedule_paid_order(
                        session,
                        order=order,
                        payment_attempt_id=None,
                    )
                    == []
                )
                assert (
                    int(await session.scalar(select(func.count()).select_from(FulfillmentJob)) or 0)
                    == 0
                )
        finally:
            await database.shutdown()

    asyncio.run(scenario())
