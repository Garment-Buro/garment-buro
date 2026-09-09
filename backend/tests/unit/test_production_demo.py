import asyncio
import json

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from app.db.base import Base
from app.db.session import DatabaseManager
from app.integrations.minio import MinioStorage
from app.modules.crm.file_service import CrmFileService
from app.modules.crm.read_repository import CrmReadRepository
from app.modules.fulfillment.models import FulfillmentJob
from app.modules.fulfillment.service import FulfillmentOutboxService
from app.modules.identity.models import User
from app.modules.orders.models import Order
from app.modules.payments.models import Payment
from app.modules.payments.service import PaymentService, PaymentStateError
from app.modules.production.admin_reads import ProductionAdminReads
from app.modules.production.auth_service import PREFIXES
from app.modules.production.demo_access import require_demo_resource
from app.modules.production.models import ProductionDemoEmployee
from app.modules.production.read_service import ProductionReadService
from app.modules.production.schemas import ProductionCommand
from app.modules.production.security import ProductionDenied
from app.modules.production.service import ProductionService
from scripts.seed_production_demo import provision
from tests.fakes.minio import FakeMinioClient
from tests.unit.test_crm_private_files import _settings, _webp


def test_demo_seed_is_idempotent_private_and_has_each_workstation(tmp_path):
    async def scenario():
        settings = _settings(tmp_path / "demo.db").model_copy(
            update={
                "identity_otp_pepper": SecretStr("demo-test-pepper"),
                "fulfillment_outbox_enabled": True,
            }
        )
        db = DatabaseManager(settings)
        await db.startup()
        try:
            async with db.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            files = CrmFileService(MinioStorage(settings, client=FakeMinioClient()))
            secret = tmp_path / "private" / "demo.json"
            rows = await provision(db, files, secret, _webp())
            codes = json.loads(secret.read_text())
            assert len(rows) == len(codes) == 10
            assert secret.stat().st_mode & 0o777 == 0o600
            assert len({row["code"] for row in codes.values()}) == 10
            assert all(len(row["code"]) == 6 for row in codes.values())
            assert await provision(db, files, secret, _webp()) == rows
            assert json.loads(secret.read_text()) == codes
            async with db.session() as session:
                assert await session.scalar(select(func.count(Payment.id))) == 0
                assert await session.scalar(select(func.count(FulfillmentJob.id))) == 0
                assert await session.scalar(select(func.count(ProductionDemoEmployee.id))) == 10
                assert await session.scalar(select(func.count(User.id))) == 10
                assert (await ProductionAdminReads().stats(session))["orders_count"] == 0
                legacy_rows, _ = await CrmReadRepository().list_projects(
                    session, status=None, assigned_to_user_id=None, cursor=None, limit=30
                )
                assert legacy_rows == []
                queue = await ProductionReadService().queue(session, demo_only=True)
                assert len(queue["items"]) == 10
                by_id = {row["project_id"]: row for row in queue["items"]}
                for row in rows:
                    item = by_id[row["project_id"]]
                    assert item["is_demo"] and not item["blocked"]
                    detail = await ProductionReadService().detail(
                        session, project_id=row["project_id"], stations=["tech"]
                    )
                    assert not detail["units"][0]["blockers"]
                    if row["station"] in {"cut", "application", "sewing", "press", "qc", "packing"}:
                        assert item["stage_counts"][row["station"]] == 1
                    if row["station"] == "dtf":
                        assert item["state"] == "waiting_dtf" and item["dtf_pending"] == 1
                order = await session.get(Order, rows[0]["order_id"])
                with pytest.raises(PaymentStateError, match="Demo orders"):
                    PaymentService._validate_payable_order(order)
                assert (
                    await FulfillmentOutboxService(settings).schedule_paid_order(
                        session, order=order, payment_attempt_id=None
                    )
                    == []
                )
                with pytest.raises(ProductionDenied):
                    await require_demo_resource(
                        session, codes["tech"]["user_id"], {"project_id": 9999}
                    )
                shipping = next(row for row in rows if row["station"] == "shipping")
                detail = await ProductionReadService().detail(
                    session, project_id=shipping["project_id"], stations=["shipping"]
                )
                await ProductionService(settings).execute(
                    session,
                    project_id=shipping["project_id"],
                    actor_id=codes["shipping"]["user_id"],
                    key="demo-dispatch-test",
                    command=ProductionCommand(
                        expected_version=detail["version"],
                        action="dispatch",
                        tracking_number="DEMO-TEST",
                        note="Учебная передача",
                    ),
                )
            # Re-running does not reset a scenario already advanced by a worker.
            await provision(db, files, secret, _webp())
            async with db.session() as session:
                detail = await ProductionReadService().detail(
                    session, project_id=shipping["project_id"], stations=["shipping"]
                )
                assert detail["state"] == "dispatched"
                for station, row in codes.items():
                    assert row["code"].startswith(PREFIXES[station])
        finally:
            await db.shutdown()

    asyncio.run(scenario())


def test_demo_codes_cannot_read_files_or_mutate_real_orders(tmp_path):
    from app.modules.production.demo.employees import ensure_employees
    from tests.unit.test_production_terminal import setup

    async def scenario():
        async with setup(tmp_path) as (db, service, _spec):
            db.settings = db.settings.model_copy(
                update={"identity_otp_pepper": SecretStr("test-demo")}
            )
            people = await ensure_employees(db, tmp_path / "codes.json")
            tech = people["tech"]["user_id"]
            async with db.session() as session:
                for params in [
                    {"project_id": 1},
                    {"order_id": 1},
                    {"unit_id": 1},
                    {"attachment_id": 1},
                ]:
                    with pytest.raises(ProductionDenied):
                        await require_demo_resource(session, tech, params)
                with pytest.raises(ProductionDenied):
                    await service.execute(
                        session,
                        project_id=1,
                        actor_id=tech,
                        key="demo-no-real",
                        command=ProductionCommand(action="release", expected_version=0),
                    )
                queue = await ProductionReadService().queue(session, demo_only=True)
                assert queue["items"] == []

    asyncio.run(scenario())
