import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.bank_payouts.contracts import BankDraft, BankPaymentStatus, BankProviderError
from app.modules.bank_payouts.models import PartnerBankPayment, PartnerBankPaymentEvent
from app.modules.bank_payouts.router import router
from app.modules.bank_payouts.schemas import BankPayoutCreate
from app.modules.bank_payouts.service import BankPayoutConflict, PartnerBankPayoutService
from app.modules.identity.factory import build_identity_service
from app.modules.identity.models import RoleName, User, UserRole
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.router import get_current_identity_user
from app.modules.orders.models import Order
from app.modules.partners.models import PartnerCommission, PartnerPayoutRequest
from app.modules.partners.requisites_crypto import EncryptedPartnerRequisites
from app.modules.partners.schemas import (
    PartnerCreateRequest,
    PartnerLandingCreateRequest,
    PartnerRequisitesRequest,
)
from app.modules.partners.service import PartnerPayoutStateError, PartnerProgramService

COMMAND = BankPayoutCreate(payment_purpose="Вознаграждение по договору 1. Без НДС.")
NOW = datetime.now(timezone.utc)


def runtime_settings(tmp_path, **overrides):
    values = dict(
        _env_file=None,
        app_env="test",
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'bank.db'}",
        identity_api_enabled=True,
        identity_migration_fingerprint="1" * 64,
        jwt_secret="test-identity-jwt-secret-long-enough",
        identity_otp_pepper="test-identity-otp-pepper-long-enough",
        notification_encryption_key="bm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm4=",
        partner_program_enabled=True,
        partner_attribution_secret="test-partner-attribution-long-enough",
        partner_commission_hold_days=0,
        tochka_payouts_enabled=True,
    )
    return Settings(**(values | overrides))


class Bank:
    def __init__(self):
        self.calls = 0
        self.status_calls = 0
        self.status = "WaitingForCreate"
        self.error = None
        self.status_error = None
        self.before_send = None
        self.request_id = "openapi-test-123"

    async def create_draft(self, body):
        self.calls += 1
        self.body = json.loads(body)
        if self.before_send:
            await self.before_send()
        if self.error:
            raise self.error
        return BankDraft(
            self.request_id, f"https://i.tochka.com/bank/m/payment-preview/{self.request_id}"
        )

    async def get_status(self, request_id):
        self.status_calls += 1
        if self.status_error:
            raise self.status_error
        return BankPaymentStatus(self.request_id, self.status)


@asynccontextmanager
async def setup(tmp_path, postgres_url=None):
    settings = runtime_settings(
        tmp_path, **({"database_url": postgres_url} if postgres_url else {})
    )
    db = DatabaseManager(settings)
    await db.startup()
    schema = f"tochka_test_{uuid.uuid4().hex}" if postgres_url else None
    try:
        if schema:
            async with db.engine.begin() as conn:
                await conn.execute(CreateSchema(schema))
            db.engine.update_execution_options(schema_translate_map={None: schema})
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        partners = PartnerProgramService(settings)
        async with db.session() as session:
            repo = IdentityRepository()
            await repo.ensure_system_authorization(session)
            admin = User(email="admin@example.test", email_normalized="admin@example.test")
            session.add(admin)
            await session.flush()
            role = await repo.get_role(session, RoleName.ADMIN)
            session.add(UserRole(user_id=admin.id, role_id=role.id))
            profile = await partners.create_partner(
                session,
                actor_user_id=admin.id,
                payload=PartnerCreateRequest(
                    email="partner@example.test",
                    code="test_partner",
                    display_name="Тестовый партнёр",
                    commission_bps=1500,
                    status="active",
                ),
            )
            landing = await partners.create_landing(
                session,
                partner_id=profile.id,
                payload=PartnerLandingCreateRequest(
                    slug="test-partner",
                    title="Test",
                    headline="Test",
                    description="Test landing",
                    cta_label="Open",
                    cta_href="/",
                    product_ids=[],
                    status="published",
                ),
            )
            token, _ = await partners.register_visit(
                session, slug=landing.slug, visitor_value="test", now=NOW
            )
            order = Order(
                user_id=None,
                email="buyer@example.test",
                email_normalized="buyer@example.test",
                phone="+79990000000",
                first_name="Тест",
                delivery_city="Москва",
                delivery_method="courier",
                delivery_address="Тестовый адрес",
                payment_method="card",
                items_subtotal=Decimal("1000.00"),
                delivery_price=Decimal("0"),
                total_price=Decimal("1000.00"),
                currency="RUB",
                request_fingerprint_sha256="b" * 64,
            )
            session.add(order)
            await session.flush()
            await partners.attribute_order(session, order_id=order.id, token=token, now=NOW)
            await partners.accrue_commission(session, order_id=order.id, now=NOW)
            await partners.save_requisites(
                session,
                user_id=profile.user_id,
                payload=PartnerRequisitesRequest(
                    entity_type="sole_proprietor",
                    recipient_name="ИП Тестовый Получатель",
                    tax_id="123456789012",
                    bank_name="Тестовый банк",
                    bic="044525225",
                    correspondent_account="30101810400000000225",
                    settlement_account="40802810900000000001",
                ),
            )
            payout = await partners.request_payout(
                session, user_id=profile.user_id, amount=Decimal("100.33"), now=NOW
            )
            await partners.review_payout(
                session,
                payout_id=payout.id,
                status="approved",
                note=None,
                actor_user_id=admin.id,
                now=NOW,
            )
            await session.commit()
        bank = Bank()
        service = PartnerBankPayoutService(settings, bank, partners)
        yield db, service, bank, payout, profile, admin
    finally:
        if schema:
            async with db.engine.begin() as conn:
                await conn.execute(DropSchema(schema, cascade=True))
        await db.shutdown()


async def create(db, service, payout, admin):
    async with db.session() as session:
        return await service.create(
            session, payout_id=payout.id, actor_user_id=admin.id, command=COMMAND
        )


def test_durable_submission_idempotence_and_encrypted_snapshot(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, service, bank, payout, profile, admin):

            async def check_durable():
                async with db.session() as session:
                    row = await service.repository.get(session, payout.id)
                    assert row.state == "submitting"
                    assert (await session.get(PartnerPayoutRequest, payout.id)).status == "approved"

            bank.before_send = check_durable
            payment = await create(db, service, payout, admin)
            again = await create(db, service, payout, admin)
            assert again.id == payment.id and bank.calls == 1
            assert payment.state == "awaiting_signature"
            assert "123456789012" not in payment.ciphertext
            snapshot = service.partners.requisites_codec.decrypt(
                EncryptedPartnerRequisites(
                    ciphertext=payment.ciphertext,
                    nonce=payment.nonce,
                    tag=payment.tag,
                    key_version=payment.key_version,
                    schema_version=payment.schema_version,
                ),
                partner_id=profile.id,
            )
            assert snapshot["request"] == bank.body
            async with db.session() as session:
                with pytest.raises(BankPayoutConflict, match="different parameters"):
                    await service.create(
                        session,
                        payout_id=payout.id,
                        actor_user_id=admin.id,
                        command=BankPayoutCreate(payment_purpose="Another payment purpose"),
                    )
                assert (
                    await session.scalar(select(func.count()).select_from(PartnerBankPayment)) == 1
                )

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "bank_status,expected", [("Paid", "paid"), ("Canceled", "canceled"), ("Rejected", "rejected")]
)
def test_only_terminal_bank_evidence_changes_ledger(tmp_path, bank_status, expected):
    async def scenario():
        async with setup(tmp_path) as (db, service, bank, payout, profile, admin):
            await create(db, service, payout, admin)
            async with db.session() as session:
                bank.status = "Created"
                assert (await service.reconcile(session, payout_id=payout.id)).state == "processing"
                stored = await session.get(PartnerPayoutRequest, payout.id)
                assert stored.status == "approved" and stored.paid_at is None
                bank.status = "WaitingForCreate"
                assert (await service.reconcile(session, payout_id=payout.id)).state == "processing"
                bank.status = bank_status
                assert (await service.reconcile(session, payout_id=payout.id)).state == expected
                assert stored.status == expected
                assert (stored.paid_at is not None) == (expected == "paid")
                count = bank.status_calls
                await service.reconcile(session, payout_id=payout.id)
                assert bank.status_calls == count
                dashboard = await service.partners.dashboard(session, user_id=profile.user_id)
                assert dashboard.available == (
                    Decimal("49.67") if expected == "paid" else Decimal("150.00")
                )
                assert dashboard.paid == (Decimal("100.33") if expected == "paid" else Decimal("0"))
                states = list(
                    await session.scalars(
                        select(PartnerBankPaymentEvent.state).order_by(PartnerBankPaymentEvent.id)
                    )
                )
                assert states == ["submitting", "awaiting_signature", "processing", expected]

    asyncio.run(scenario())


@pytest.mark.parametrize("unknown", [True, False])
def test_creation_failure_reservations_and_no_resend(tmp_path, unknown):
    async def scenario():
        async with setup(tmp_path) as (db, service, bank, payout, profile, admin):
            bank.error = BankProviderError(
                "http_500" if unknown else "http_400", outcome_unknown=unknown
            )
            payment = await create(db, service, payout, admin)
            assert payment.state == ("unknown" if unknown else "rejected")
            await create(db, service, payout, admin)
            assert bank.calls == 1
            async with db.session() as session:
                dashboard = await service.partners.dashboard(session, user_id=profile.user_id)
                assert dashboard.available == (Decimal("49.67") if unknown else Decimal("150.00"))
                service.partners.settings.tochka_payouts_enabled = False
                with pytest.raises(PartnerPayoutStateError, match="bank reconciliation"):
                    await service.partners.review_payout(
                        session,
                        payout_id=payout.id,
                        status="canceled",
                        note=None,
                        actor_user_id=admin.id,
                    )

    asyncio.run(scenario())


def test_process_crash_does_not_resend_or_release_balance(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, service, bank, payout, profile, admin):
            bank.error = asyncio.CancelledError()
            with pytest.raises(asyncio.CancelledError):
                await create(db, service, payout, admin)
            bank.error = None
            assert (await create(db, service, payout, admin)).state == "submitting"
            async with db.session() as session:
                row = await service.reconcile(
                    session, payout_id=payout.id, now=NOW + timedelta(minutes=5)
                )
                assert row.state == "unknown" and row.last_error == "bank_receipt_missing"
                assert (await session.get(PartnerPayoutRequest, payout.id)).status == "approved"
                assert bank.calls == 1 and bank.status_calls == 0

    asyncio.run(scenario())


@pytest.mark.parametrize("case", ["requested", "insufficient", "suspended", "missing_requisites"])
def test_preflight_refuses_unsafe_submission(tmp_path, case):
    async def scenario():
        async with setup(tmp_path) as (db, service, bank, payout, profile, admin):
            async with db.session() as session:
                if case == "requested":
                    (await session.get(PartnerPayoutRequest, payout.id)).status = "requested"
                elif case == "insufficient":
                    (await session.scalar(select(PartnerCommission))).status = "canceled"
                elif case == "suspended":
                    (
                        await service.partners.repository.get_profile(
                            session, partner_id=profile.id
                        )
                    ).status = "suspended"
                else:
                    row = await service.partners.repository.get_partner_requisites(
                        session, partner_id=profile.id
                    )
                    await session.delete(row)
                await session.commit()
                with pytest.raises(BankPayoutConflict):
                    await service.create(
                        session, payout_id=payout.id, actor_user_id=admin.id, command=COMMAND
                    )
                assert bank.calls == 0

    asyncio.run(scenario())


def test_failed_status_evidence_and_environment_switch_never_mark_paid(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, service, bank, payout, profile, admin):
            await create(db, service, payout, admin)
            async with db.session() as session:
                bank.status, bank.request_id = "Paid", "wrong-id"
                row = await service.reconcile(session, payout_id=payout.id)
                assert (
                    row.state == "awaiting_signature"
                    and row.last_error == "invalid_status_evidence"
                )
                bank.status_error = BankProviderError("network_error")
                row = await service.reconcile(session, payout_id=payout.id)
                assert row.last_error == "network_error"
                assert (await session.get(PartnerPayoutRequest, payout.id)).status == "approved"
                service.settings.tochka_environment = "production"
                with pytest.raises(BankPayoutConflict, match="another bank environment"):
                    await service.reconcile(session, payout_id=payout.id)

    asyncio.run(scenario())


def test_admin_cannot_manually_mark_paid_with_bank_enabled(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, service, bank, payout, profile, admin):
            async with db.session() as session:
                with pytest.raises(PartnerPayoutStateError, match="confirmed bank payment"):
                    await service.partners.review_payout(
                        session,
                        payout_id=payout.id,
                        status="paid",
                        note=None,
                        actor_user_id=admin.id,
                    )

    asyncio.run(scenario())


def test_http_permissions_ownership_redaction_and_disabled_create(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, service, bank, payout, profile, admin):
            app = FastAPI()
            app.include_router(router)
            app.state.database = db
            app.state.partner_program_service = service.partners
            app.state.partner_bank_payout_service = service
            app.state.identity_service = build_identity_service(service.settings)
            current = admin

            async def identity():
                return current

            app.dependency_overrides[get_current_identity_user] = identity
            path = f"/api/admin/partners/payouts/{payout.id}/bank-payment"
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="https://test"
            ) as client:
                response = await client.post(path, json=COMMAND.model_dump())
                assert response.status_code == 200, response.text
                assert (
                    response.json()["signing_url"]
                    and response.headers["cache-control"] == "no-store"
                )
                async with db.session() as session:
                    current = await session.get(User, profile.user_id)
                assert (await client.post(path, json=COMMAND.model_dump())).status_code == 403
                own_path = f"/api/partner/payouts/{payout.id}/bank-payment"
                response = await client.get(own_path)
                assert response.status_code == 200
                assert (
                    not {"signing_url", "ciphertext", "request_id", "last_error"}
                    & response.json().keys()
                )
                current = admin
                assert (await client.get(own_path)).status_code == 404
                app.dependency_overrides.clear()
                assert (await client.post(path, json=COMMAND.model_dump())).status_code == 401
                app.dependency_overrides[get_current_identity_user] = identity
                app.state.partner_bank_payout_service = None
                assert (await client.post(path, json=COMMAND.model_dump())).status_code == 503
                assert (await client.get(path)).status_code == 200
                assert bank.calls == 1

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "override,match",
    [
        ({"tochka_environment": "production"}, "only allowed in production"),
        ({"app_env": "production"}, "Sandbox bank statuses"),
        ({"app_env": "production", "tochka_environment": "production"}, "TOCHKA_API_TOKEN"),
        ({"tochka_poll_seconds": 1}, "poll interval"),
        ({"notification_encryption_key": None}, "requisites encryption"),
    ],
)
def test_configuration_fails_closed(tmp_path, override, match):
    with pytest.raises(ValidationError, match=match):
        runtime_settings(tmp_path, **override)


def test_tochka_disabled_by_default():
    assert Settings(_env_file=None).tochka_payouts_enabled is False


@pytest.mark.skipif(
    not os.getenv("TOCHKA_TEST_POSTGRES_URL"), reason="Isolated PostgreSQL CI service required"
)
def test_postgres_concurrent_submission_and_polling(tmp_path):
    async def scenario():
        async with setup(tmp_path, os.environ["TOCHKA_TEST_POSTGRES_URL"]) as (
            db,
            service,
            bank,
            payout,
            profile,
            admin,
        ):
            entered, release = asyncio.Event(), asyncio.Event()

            async def hold_bank_response():
                entered.set()
                await release.wait()

            bank.before_send = hold_bank_response
            first = asyncio.create_task(create(db, service, payout, admin))
            await asyncio.wait_for(entered.wait(), timeout=10)
            try:
                duplicates = await asyncio.wait_for(
                    asyncio.gather(*[create(db, service, payout, admin) for _ in range(4)]),
                    timeout=10,
                )
                assert all(row.state == "submitting" for row in duplicates)
                assert bank.calls == 1
                async with db.session() as session:
                    with pytest.raises(PartnerPayoutStateError):
                        await service.partners.review_payout(
                            session,
                            payout_id=payout.id,
                            status="canceled",
                            note=None,
                            actor_user_id=admin.id,
                        )
            finally:
                release.set()
                await first
            bank.status = "Paid"

            async def poll():
                async with db.session() as session:
                    return await service.reconcile(session, payout_id=payout.id)

            rows = await asyncio.wait_for(asyncio.gather(*[poll() for _ in range(4)]), timeout=10)
            assert all(row.state == "paid" for row in rows)
            assert bank.status_calls == 1
            async with db.session() as session:
                count = await session.scalar(
                    select(func.count())
                    .select_from(PartnerBankPaymentEvent)
                    .where(PartnerBankPaymentEvent.state == "paid")
                )
                assert count == 1

    asyncio.run(scenario())
