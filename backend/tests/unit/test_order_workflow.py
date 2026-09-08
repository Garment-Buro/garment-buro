import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import Settings
from app.db.session import DatabaseManager
from app.modules.catalog.models import Product
from app.modules.checkout.service import (
    CheckoutPaymentError,
    CheckoutPaymentMethodError,
    CheckoutService,
)
from app.modules.delivery.models import CdekShipment
from app.modules.delivery.provider import CdekOrderSnapshot
from app.modules.delivery.provider import _snapshot as cdek_snapshot
from app.modules.delivery.tracking import apply_tracking
from app.modules.fulfillment.models import FulfillmentJob
from app.modules.identity.models import RoleName, User, UserRole
from app.modules.identity.repository import IdentityRepository
from app.modules.inventory.models import InventoryReservation
from app.modules.orders.models import Order
from app.modules.orders.repository import TargetOrderReadRepository
from app.modules.orders.security import generate_order_guest_access_token
from app.modules.orders.service import (
    InvalidOrderTransitionError,
    OrderLifecycleService,
    TargetOrderReadService,
)
from app.modules.orders.workflow import OrderModerationService, OrderWorkflowConflict
from app.modules.orders.workflow_models import OrderWorkflow, OrderWorkflowEvent, OrderWorkflowJob
from app.modules.orders.workflow_repository import claim
from app.modules.orders.workflow_worker import OrderWorkflowProcessor, WorkflowLeaseLost
from app.modules.payments.creation import PaymentCreationService
from app.modules.payments.models import PaymentAttempt, PaymentOperation
from app.modules.payments.operation_service import (
    PaymentOperationConflictError,
    PaymentOperationService,
)
from app.modules.payments.provider import YooKassaProviderError
from app.modules.payments.reconciliation import PaymentReconciliationProcessor
from app.modules.payments.service import PaymentService
from tests.unit.test_checkout_service import _command, _seed_catalog, _settings, _snapshot

NOW = datetime.now(timezone.utc) + timedelta(seconds=5)


class CrashAfterProviderAccepted(BaseException):
    pass


class Provider:
    def __init__(self):
        self.state = "waiting_for_capture"
        self.create_error = None
        self.capture_error = None
        self.capture_committed = False
        self.creates, self.captures, self.cancels = [], [], []
        self.order_id = 1

    def snapshot(self):
        result = _snapshot(
            self.order_id, status="pending" if self.state == "canceled" else self.state
        )
        if self.state == "canceled":
            result = result.model_copy(
                update={
                    "status": "canceled",
                    "paid": False,
                    "cancellation_party": "yoo_money",
                    "cancellation_reason": "expired_on_capture",
                }
            )
        if self.state == "waiting_for_capture":
            result = result.model_copy(update={"expires_at": NOW + timedelta(days=6)})
        return result

    async def create_payment(self, *, idempotence_key, request_body):
        self.creates.append((idempotence_key, request_body))
        self.order_id = int(json.loads(request_body)["metadata"]["order_id"])
        if self.create_error:
            raise self.create_error
        return self.snapshot()

    async def get_payment(self, provider_payment_id):
        return self.snapshot()

    async def capture_payment(self, provider_payment_id, *, idempotence_key, request_body):
        self.captures.append((idempotence_key, request_body))
        if self.capture_committed or self.capture_error is None:
            self.state = "succeeded"
        if self.capture_error:
            raise self.capture_error
        return self.snapshot()

    async def cancel_payment(self, provider_payment_id, *, idempotence_key):
        self.cancels.append(idempotence_key)
        self.state = "canceled"
        return self.snapshot()


@asynccontextmanager
async def setup(tmp_path, *, postgres_url=None, checkout=True, provider=None):
    values = _settings(tmp_path / "workflow.db", fulfillment_enabled=True).model_dump()
    values.update(
        order_moderation_enabled=True,
        payment_management_enabled=True,
        payment_reconciliation_enabled=True,
        fulfillment_crm_enabled=True,
    )
    if postgres_url:
        values["database_url"] = postgres_url
    settings = Settings(_env_file=None, **values)
    db = DatabaseManager(settings)
    await db.startup()
    schema = "workflow_test_" + uuid.uuid4().hex if postgres_url else None
    try:
        if schema:
            async with db.engine.begin() as conn:
                await conn.execute(CreateSchema(schema))
            db.engine.update_execution_options(schema_translate_map={None: schema})
        product_id = await _seed_catalog(db)
        async with db.session() as session:
            repo = IdentityRepository()
            await repo.ensure_system_authorization(session)
            admin = User(
                email="staff@example.test", email_normalized="staff@example.test", status="active"
            )
            session.add(admin)
            await session.flush()
            role = await repo.get_role(session, RoleName.ADMIN)
            session.add(UserRole(user_id=admin.id, role_id=role.id))
            await session.commit()
        provider = provider or Provider()
        service = CheckoutService(settings, PaymentCreationService(settings, provider))
        if checkout:
            async with db.session() as session:
                await service.checkout(
                    session,
                    idempotency_key="workflow-checkout-0001",
                    command=_command(product_id),
                    guest_access_token=generate_order_guest_access_token(),
                    now=NOW,
                )
        yield db, provider, service, product_id
    finally:
        if schema:
            async with db.engine.begin() as conn:
                await conn.execute(DropSchema(schema, cascade=True))
        await db.shutdown()


async def decide(
    db, decision="approve", version=2, key="moderation-command-0001", actor=1, commit=True
):
    async with db.session() as session:
        flow = await OrderModerationService(db.settings).decide(
            session,
            order_id=1,
            expected_version=version,
            actor_user_id=actor,
            decision=decision,
            key=key,
            note="Reviewed specification",
            now=NOW,
        )
        if commit:
            await session.commit()
        return flow.state


async def work(db, provider, now=NOW):
    async with db.session() as session:
        return await OrderWorkflowProcessor(db.settings, provider).process_once(session, now=now)


def test_hold_moderation_capture_production_and_delivery(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, provider, _, _):
            assert json.loads(provider.creates[0][1])["capture"] is False
            async with db.session() as session:
                flow = await session.get(OrderWorkflow, 1)
                assert (flow.state, flow.version) == ("moderation", 2)
                assert await session.scalar(select(func.count()).select_from(FulfillmentJob)) == 0
                assert (
                    await OrderLifecycleService(db.settings).expire_pending(
                        session, now=NOW + timedelta(days=1)
                    )
                    == 0
                )
                order = await TargetOrderReadRepository().get_owned(session, order_id=1, user_id=1)
                assert order is None
                orders = await TargetOrderReadRepository().list_all(session, limit=10, offset=0)
                assert (
                    TargetOrderReadService.map_order(orders[0]).customer_stage_label == "Модерация"
                )
            # Decision + task roll back together if command transaction fails.
            await decide(db, commit=False)
            async with db.session() as session:
                assert (await session.get(OrderWorkflow, 1)).decision is None
                assert await session.scalar(select(func.count()).select_from(OrderWorkflowJob)) == 1
            assert await decide(db) == "capture_pending"
            assert await decide(db) == "capture_pending"
            with pytest.raises(OrderWorkflowConflict):
                await decide(db, "reject")
            await work(db, provider)  # persisted checkout recovery task
            await work(db, provider)  # committed moderation command
            async with db.session() as session:
                order = await session.get(Order, 1)
                assert (order.status, order.payment_status) == ("processing", "paid")
                assert (await session.get(OrderWorkflow, 1)).state == "production"
                assert (await session.scalar(select(InventoryReservation))).status == "confirmed"
                jobs = list(await session.scalars(select(FulfillmentJob)))
                assert len(jobs) == 3
                job = next(j for j in jobs if j.kind == "cdek_order_create")
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
                    status="created",
                    max_attempts=4,
                    available_at=NOW,
                    provider_uuid="cdek-1",
                    provider_cdek_number="123456",
                    provider_created_at=NOW,
                )
                session.add(shipment)
                await session.commit()
            assert len(provider.captures) == 1
            for code, offset, expected in [
                ("ACCEPTED", 0, "production"),
                ("RECEIVED_AT_SHIPMENT_WAREHOUSE", 1, "shipped"),
                ("ACCEPTED_AT_PICK_UP_POINT", 2, "shipped"),
                ("NOT_DELIVERED", 3, "shipped"),
                ("DELIVERED", 4, "completed"),
                ("ACCEPTED", 1, "completed"),
            ]:
                async with db.session() as session:
                    snap = CdekOrderSnapshot(
                        "cdek-1", "GB-1", "123456", code, code, NOW + timedelta(seconds=offset)
                    )
                    await apply_tracking(
                        session,
                        db.settings,
                        shipment_id=1,
                        snapshot=snap,
                        now=NOW + timedelta(minutes=5),
                    )
                    await session.commit()
                    assert (await session.get(OrderWorkflow, 1)).state == expected
            async with db.session() as session:
                assert (await session.get(Order, 1)).status == "completed"
                assert len(list(await session.scalars(select(FulfillmentJob)))) == 3

    asyncio.run(scenario())


@pytest.mark.parametrize("decision", ["reject", "provider_expiry"])
def test_cancelled_hold_releases_reservation_without_production(tmp_path, decision):
    async def scenario():
        async with setup(tmp_path) as (db, provider, _, _):
            if decision == "reject":
                await decide(db, "reject")
                await work(db, provider)
                await work(db, provider)
                assert len(provider.cancels) == 1
            else:
                provider.state = "canceled"
                async with db.session() as session:
                    await PaymentReconciliationProcessor(db.settings, provider).process_once(
                        session, worker_id="expiry", now=NOW + timedelta(days=7)
                    )
            async with db.session() as session:
                assert (await session.get(OrderWorkflow, 1)).state == "cancelled"
                assert (await session.get(Order, 1)).status == "cancelled"
                assert (await session.scalar(select(InventoryReservation))).status == "released"
                assert (await session.get(Product, 1)).reserved_quantity == 0
                assert await session.scalar(select(func.count()).select_from(FulfillmentJob)) == 0

    asyncio.run(scenario())


@pytest.mark.parametrize("accepted", [True, False])
def test_capture_crash_or_timeout_recovers_same_operation(tmp_path, accepted):
    async def scenario():
        async with setup(tmp_path) as (db, provider, _, _):
            await decide(db)
            await work(db, provider)
            provider.capture_committed = accepted
            provider.capture_error = (
                CrashAfterProviderAccepted()
                if accepted
                else YooKassaProviderError("timeout", retryable=True, outcome_unknown=True)
            )
            if accepted:
                with pytest.raises(CrashAfterProviderAccepted):
                    await work(db, provider)
            else:
                await work(db, provider)
            async with db.session() as session:
                operation = await session.scalar(select(PaymentOperation))
                assert operation is not None
                assert (await session.get(Order, 1)).status == "new"
            provider.capture_error = None
            await work(db, provider, NOW + timedelta(minutes=6))
            async with db.session() as session:
                assert (await session.get(Order, 1)).status == "processing"
                assert await session.scalar(select(func.count()).select_from(PaymentOperation)) == 1
                assert (await session.get(OrderWorkflowJob, 2)).status == "completed"
            assert len(provider.captures) == (1 if accepted else 2)
            assert len({key for key, _ in provider.captures}) == 1

    asyncio.run(scenario())


def test_unknown_creation_is_resumed_without_customer_retry(tmp_path):
    async def scenario():
        async with setup(tmp_path, checkout=False) as (db, provider, checkout, product_id):
            provider.create_error = YooKassaProviderError(
                "timeout", retryable=True, outcome_unknown=True
            )
            async with db.session() as session:
                with pytest.raises(CheckoutPaymentError):
                    await checkout.checkout(
                        session,
                        idempotency_key="workflow-checkout-0001",
                        command=_command(product_id),
                        guest_access_token=generate_order_guest_access_token(),
                        now=NOW,
                    )
            provider.create_error = None
            await work(db, provider, NOW + timedelta(minutes=3))
            async with db.session() as session:
                assert (await session.get(OrderWorkflow, 1)).state == "moderation"
                assert await session.scalar(select(func.count()).select_from(Order)) == 1
            assert len(provider.creates) == 2
            assert provider.creates[0] == provider.creates[1]

    asyncio.run(scenario())


def test_wrong_actor_bypass_and_unapproved_capture_are_blocked(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, provider, _, _):
            with pytest.raises(PermissionError):
                await decide(db, actor=999)
            with pytest.raises(OrderWorkflowConflict):
                await decide(db, version=99)
            async with db.session() as session:
                with pytest.raises(PaymentOperationConflictError):
                    await PaymentOperationService(db.settings, provider).capture_order(
                        session,
                        order_id=1,
                        client_key="bypass-operation-0001",
                        actor_user_id=1,
                        now=NOW,
                    )
            async with db.session() as session:
                with pytest.raises(InvalidOrderTransitionError):
                    await OrderLifecycleService(db.settings).mark_completed(
                        session, order_id=1, actor_user_id=1
                    )
            provider.state = "succeeded"
            async with db.session() as session:
                await PaymentService(db.settings).record_provider_snapshot(
                    session, attempt_id=1, snapshot=provider.snapshot(), now=NOW
                )
                await OrderLifecycleService(db.settings).confirm_payment(
                    session, order_id=1, payment_attempt_id=1, now=NOW
                )
                await session.commit()
                assert (await session.get(PaymentAttempt, 1)).status == "succeeded"
                assert (
                    await session.get(OrderWorkflow, 1)
                ).attention_code == "captured_without_approval"
                assert (await session.get(Order, 1)).status == "new"
                assert await session.scalar(select(func.count()).select_from(FulfillmentJob)) == 0

    asyncio.run(scenario())


def test_sbp_is_rejected_before_any_order_is_created(tmp_path):
    async def scenario():
        async with setup(tmp_path, checkout=False) as (db, provider, checkout, product_id):
            async with db.session() as session:
                with pytest.raises(CheckoutPaymentMethodError, match="SBP"):
                    await checkout.checkout(
                        session,
                        idempotency_key="workflow-checkout-0001",
                        command=_command(product_id, payment_method="qr"),
                        guest_access_token=generate_order_guest_access_token(),
                        now=NOW,
                    )
                assert await session.scalar(select(func.count()).select_from(Order)) == 0
            assert provider.creates == []

    asyncio.run(scenario())


def test_stale_worker_cannot_acknowledge_new_generation(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, _, _, _):
            async with db.session() as session:
                first = await claim(session, NOW)
                old_token = first.lease_token
                await session.commit()
            async with db.session() as session:
                second = await claim(session, NOW + timedelta(minutes=6))
                assert second.lease_token != old_token
                await session.commit()
            async with db.session() as session:
                with pytest.raises(WorkflowLeaseLost):
                    await OrderWorkflowProcessor._owned(session, 1, old_token)

    asyncio.run(scenario())


def test_cdek_parser_uses_timestamp_not_array_order():
    snapshot = cdek_snapshot(
        {
            "entity": {
                "uuid": "test-1",
                "statuses": [
                    {"code": "DELIVERED", "date_time": "2026-09-08T12:00:00+03:00"},
                    {"code": "CREATED", "date_time": "2026-09-07T12:00:00+03:00"},
                ],
            }
        },
        expected_uuid="test-1",
    )
    assert snapshot.status_code == "DELIVERED"
    assert snapshot.status_at == datetime(2026, 9, 8, 9, tzinfo=timezone.utc)


@pytest.mark.skipif(
    not os.getenv("ORDER_WORKFLOW_TEST_POSTGRES_URL"), reason="Requires isolated PostgreSQL schema"
)
def test_postgres_concurrent_moderation_and_job_claims(tmp_path):
    async def scenario():
        async with setup(tmp_path, postgres_url=os.environ["ORDER_WORKFLOW_TEST_POSTGRES_URL"]) as (
            db,
            provider,
            _,
            _,
        ):
            results = await asyncio.gather(*(decide(db) for _ in range(5)))
            assert results == ["capture_pending"] * 5
            with pytest.raises(OrderWorkflowConflict):
                await decide(db, "reject", key="different-command-key")
            await asyncio.gather(*(work(db, provider) for _ in range(5)))
            async with db.session() as session:
                assert await session.scalar(select(func.count()).select_from(PaymentOperation)) == 1
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(OrderWorkflowEvent)
                        .where(OrderWorkflowEvent.reason == "moderation.approve")
                    )
                    == 1
                )
                assert (await session.get(Order, 1)).status == "processing"
            assert len(provider.captures) == 1

    asyncio.run(scenario())
