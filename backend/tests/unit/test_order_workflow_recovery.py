import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.modules.delivery.models import CdekShipment, CdekShipmentAttempt
from app.modules.delivery.provider import CdekOrderSnapshot
from app.modules.delivery.recovery import recover_shipment
from app.modules.fulfillment.models import FulfillmentJob
from app.modules.orders.models import Order
from app.modules.orders.workflow import OrderWorkflowConflict
from app.modules.orders.workflow_models import OrderWorkflow, OrderWorkflowJob
from app.modules.orders.workflow_operations import inspect_orders, requeue
from app.modules.orders.workflow_worker import OrderWorkflowProcessor
from app.modules.payments.models import PaymentReconciliationJob
from app.modules.payments.provider import YooKassaProviderError
from app.modules.payments.reconciliation import PaymentReconciliationProcessor
from tests.unit.test_order_workflow import NOW, decide, setup, work


def test_healthy_long_hold_does_not_exhaust_reconciliation_budget(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, provider, _, _):
            async with db.session() as session:
                job = await session.scalar(select(PaymentReconciliationJob))
                job.max_attempts = 1
                await session.commit()
            for offset in (1, 2, 3):
                async with db.session() as session:
                    result = await PaymentReconciliationProcessor(
                        db.settings, provider
                    ).process_once(session, worker_id="test", now=NOW + timedelta(days=offset))
                    assert result.status == "scheduled"
                    assert (await session.get(OrderWorkflow, 1)).state == "moderation"

    asyncio.run(scenario())


def test_capture_window_and_operator_recovery_keep_original_key(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, provider, _, _):
            await decide(db)
            await work(db, provider)
            provider.capture_error = YooKassaProviderError(
                "unauthorized", retryable=False, outcome_unknown=False
            )
            await work(db, provider)
            async with db.session() as session:
                report = (await inspect_orders(session, order_id=1))[0]
                assert report["workflow_jobs"][1]["status"] == "dead"
                assert "email" not in str(report)
                with pytest.raises(OrderWorkflowConflict):
                    await requeue(
                        session, family="workflow", job_id=2, expected_generation=99, actor_id=1
                    )
            async with db.session() as session:
                await requeue(
                    session, family="workflow", job_id=2, expected_generation=1, actor_id=1
                )
                await session.commit()
            provider.capture_error = None
            # Still replay-safe after operator fixes credentials, not a new operation.
            await work(db, provider, NOW + timedelta(minutes=6))
            async with db.session() as session:
                assert (await session.get(Order, 1)).status == "processing"
            assert len(provider.captures) == 2
            assert provider.captures[0] == provider.captures[1]

    asyncio.run(scenario())


def test_capture_post_is_not_replayed_after_provider_idempotence_window(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, provider, _, _):
            await decide(db)
            await work(db, provider)
            provider.capture_error = YooKassaProviderError(
                "timeout", retryable=True, outcome_unknown=True
            )
            await work(db, provider)
            provider.capture_error = None
            await work(db, provider, NOW + timedelta(hours=24))
            async with db.session() as session:
                job = await session.get(OrderWorkflowJob, 2)
                assert job.status == "dead"
                assert job.last_error_code == "idempotence_window_expired"
                assert (await session.get(Order, 1)).status == "new"
            assert len(provider.captures) == 1

    asyncio.run(scenario())


def test_delivery_recovery_verifies_identity_and_polling_survives_restart(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, payments, _, _):
            await decide(db)
            await work(db, payments)
            await work(db, payments)
            async with db.session() as session:
                job = await session.scalar(
                    select(FulfillmentJob).where(FulfillmentJob.kind == "cdek_order_create")
                )
                shipment = CdekShipment(
                    order_id=1,
                    source_fulfillment_job_id=job.id,
                    source_payment_attempt_id=1,
                    client_order_number="GB-1",
                    request_sha256="a" * 64,
                    request_schema_version=1,
                    request_ciphertext="test",
                    request_nonce="test",
                    request_tag="test",
                    encryption_key_version=1,
                    status="unknown",
                    max_attempts=4,
                    attempts_count=1,
                    available_at=NOW,
                )
                session.add(shipment)
                await session.flush()
                session.add(
                    CdekShipmentAttempt(
                        shipment_id=shipment.id,
                        attempt_number=1,
                        status="unknown",
                        worker_id="old-worker",
                        request_sha256="a" * 64,
                        started_at=NOW,
                        completed_at=NOW,
                    )
                )
                await session.commit()
                version = (await session.get(OrderWorkflow, 1)).version

            class Delivery:
                order_number = "OTHER-ORDER"

                async def get_order(self, provider_uuid):
                    return CdekOrderSnapshot(
                        provider_uuid, self.order_number, "123456", "DELIVERED", "Delivered", NOW
                    )

            delivery = Delivery()
            async with db.session() as session:
                with pytest.raises(OrderWorkflowConflict):
                    await recover_shipment(
                        session,
                        delivery,
                        order_id=1,
                        expected_version=version,
                        provider_uuid="cdek-1",
                        actor_id=1,
                    )
            delivery.order_number = "GB-1"
            async with db.session() as session:
                await recover_shipment(
                    session,
                    delivery,
                    order_id=1,
                    expected_version=version,
                    provider_uuid="cdek-1",
                    actor_id=1,
                )
                await session.commit()
                assert (await session.get(Order, 1)).status == "processing"
            processor = OrderWorkflowProcessor(
                db.settings.model_copy(update={"cdek_tracking_enabled": True}), payments, delivery
            )
            async with db.session() as session:
                await processor.process_once(session, now=NOW + timedelta(minutes=5))
            async with db.session() as session:
                assert (await session.get(Order, 1)).status == "completed"
                assert (await session.get(OrderWorkflowJob, 3)).status == "completed"

    asyncio.run(scenario())
