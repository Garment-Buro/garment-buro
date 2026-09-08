import asyncio
import os
import uuid
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.crm.file_models import CrmFileAttachment
from app.modules.crm.models import CrmProductionUnit, CrmProductionUnitStatus
from app.modules.crm.production_service import CrmProductionConflictError, CrmProductionService
from app.modules.identity.models import PermissionCode, RoleName, User, UserRole
from app.modules.identity.repository import IdentityRepository
from app.modules.media.models import MediaObject
from app.modules.orders.models import Order, OrderItem
from app.modules.production.auth_router import get_production_user
from app.modules.production.evidence import ProductionConflict
from app.modules.production.models import ProductionBag, ProductionEvent, ProductionSpecification
from app.modules.production.read_service import ProductionReadService
from app.modules.production.router import router
from app.modules.production.schemas import ProductionCommand, SpecificationWrite
from app.modules.production.security import ProductionDenied
from app.modules.production.service import ProductionService
from tests.unit.test_crm_production_workflow import NOW, _seed_unit_and_reference_data, _settings


@asynccontextmanager
async def setup(tmp_path, postgres_url=None, quantity=1):
    settings = _settings(tmp_path / "production.db")
    if postgres_url:
        settings = settings.model_copy(update={"database_url": postgres_url})
    db = DatabaseManager(settings)
    await db.startup()
    schema = f"production_test_{uuid.uuid4().hex}" if postgres_url else None
    try:
        if schema:
            async with db.engine.begin() as conn:
                await conn.execute(CreateSchema(schema))
            db.engine.update_execution_options(schema_translate_map={None: schema})
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        unit, _, size, card = await _seed_unit_and_reference_data(db, quantity=quantity)
        async with db.session() as session:
            repo = IdentityRepository()
            await repo.ensure_system_authorization(session)
            tech = await repo.get_role(session, RoleName.PRODUCTION_TECH)
            session.add(UserRole(user_id=1, role_id=tech.id))
            cutter = User(email="cut@example.test", email_normalized="cut@example.test")
            customer = User(email="customer@example.test", email_normalized="customer@example.test")
            session.add_all([cutter, customer])
            await session.flush()
            for person, role_name in [
                (cutter, RoleName.PRODUCTION_CUT),
                (customer, RoleName.CUSTOMER),
            ]:
                role = await repo.get_role(session, role_name)
                session.add(UserRole(user_id=person.id, role_id=role.id))
            order = await session.get(Order, 1)
            order.first_name = "Test"
            order.phone = "+79990000000"
            order.delivery_city = "Test city"
            order.delivery_address = "Test address"
            for number in [1, 2]:
                media = MediaObject(
                    bucket_name=settings.minio_crm_bucket,
                    object_key=f"test/{number}.pdf",
                    original_filename=f"{number}.pdf",
                    content_type="application/pdf",
                    size_bytes=100,
                    checksum_sha256=str(number) * 64,
                    is_public=False,
                    status="ready",
                )
                session.add(media)
                await session.flush()
                session.add(
                    CrmFileAttachment(
                        media_object_id=media.id,
                        production_unit_id=unit,
                        role="production_evidence",
                        sort_order=number,
                        created_at=NOW,
                    )
                )
            await session.commit()
        spec = dict(
            tech_card_revision_id=card,
            garment_size_id=size,
            route=["cut", "application", "sewing", "press", "qc", "packing"],
            components=[dict(key="fabric", name="Fabric", quantity="2", unit="м", location="A-01")],
            pattern_file_ids=[1],
            print_file_ids=[2],
            instructions="Print file 2 on back, 20x30 cm. Check order measurements.",
            quality_checks=["Seams", "Print"],
        )
        yield db, ProductionService(settings), spec
    finally:
        if schema:
            async with db.engine.begin() as conn:
                await conn.execute(DropSchema(schema, cascade=True))
        await db.shutdown()


async def execute(db, service, action, *, actor=1, version=None, key=None, **payload):
    async with db.session() as session:
        if version is None:
            bag = await session.scalar(select(ProductionBag))
            version = bag.version if bag else 0
        return await service.execute(
            session,
            project_id=1,
            actor_id=actor,
            key=key or str(uuid.uuid4()),
            command=ProductionCommand(expected_version=version, action=action, **payload),
        )


def test_full_flow_persists_dtf_pocket_quality_and_order_shipment(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, service, spec):
            await execute(db, service, "plan", unit_id=1, specification=spec)
            with pytest.raises(ProductionConflict, match="Подтвердите"):
                await execute(db, service, "release")
            await execute(db, service, "confirm_documents", unit_id=1)
            await execute(db, service, "release")
            with pytest.raises(ProductionConflict, match="комплектующие"):
                await execute(db, service, "send_bag")
            await execute(
                db, service, "check_component", unit_id=1, component_key="fabric", checked=True
            )
            await execute(db, service, "send_bag")
            with pytest.raises(ProductionConflict, match="пропустить"):
                await execute(db, service, "complete_stage", unit_id=1, stage="sewing")
            await execute(
                db,
                service,
                "complete_stage",
                actor=2,
                unit_id=1,
                stage="cut",
                note="Wrapped with QR",
            )
            with pytest.raises(ProductionConflict, match="вложения"):
                await execute(db, service, "complete_stage", unit_id=1, stage="application")
            await execute(db, service, "return_to_dtf")
            with pytest.raises(ProductionConflict, match="DTF"):
                await execute(db, service, "send_bag")
            await execute(db, service, "dtf_ready", unit_id=1)
            async with db.session() as session:
                detail = await ProductionReadService().detail(
                    session, project_id=1, stations=["cut"]
                )
                assert detail["state"] == "waiting_dtf"
                assert detail["units"][0]["dtf_ready"] and not detail["units"][0]["dtf_inserted"]
                assert detail["delivery"] is None
            await execute(db, service, "insert_dtf", unit_id=1)
            await execute(db, service, "send_bag")
            for stage in ["application", "sewing", "press"]:
                await execute(db, service, "complete_stage", unit_id=1, stage=stage)
            with pytest.raises(ProductionConflict, match="ОТК"):
                await execute(
                    db, service, "complete_stage", unit_id=1, stage="qc", quality_confirmed=[0]
                )
            await execute(
                db, service, "complete_stage", unit_id=1, stage="qc", quality_confirmed=[0, 1]
            )
            with pytest.raises(ProductionConflict, match="упаковку"):
                await execute(db, service, "pack_bag")
            await execute(db, service, "complete_stage", unit_id=1, stage="packing")
            await execute(db, service, "pack_bag")
            receipt = await execute(
                db,
                service,
                "dispatch",
                key="dispatch-once",
                tracking_number="TEST-001",
                note="Carrier received",
            )
            replay = await execute(
                db,
                service,
                "dispatch",
                version=receipt.version - 1,
                key="dispatch-once",
                tracking_number="TEST-001",
                note="Carrier received",
            )
            assert replay == receipt
            async with db.session() as session:
                order = await session.get(Order, 1)
                assert order.status == "shipped"
                detail = await ProductionReadService().detail(
                    session, project_id=1, stations=["shipping"]
                )
                assert detail["state"] == "dispatched" and detail["tracking_number"] == "TEST-001"
                assert len(detail["events"]) == receipt.version
                assert detail["units"][0]["stage_index"] == 6

    asyncio.run(scenario())


def test_mixed_routes_share_one_bag_and_wait_for_dtf_together(tmp_path):
    async def scenario():
        async with setup(tmp_path, quantity=2) as (db, service, spec):
            await execute(db, service, "plan", unit_id=1, specification=spec)
            # Individual document preparation does not depend on other unfinished specs.
            await execute(db, service, "confirm_documents", unit_id=1)
            with pytest.raises(ProductionConflict, match="всех вещей"):
                await execute(db, service, "release")
            plain = spec | {
                "route": ["sewing", "qc", "packing"],
                "pattern_file_ids": [],
                "print_file_ids": [],
            }
            await execute(db, service, "plan", unit_id=2, specification=plain)
            await execute(db, service, "confirm_documents", unit_id=2)
            await execute(db, service, "release")
            for unit in [1, 2]:
                await execute(
                    db,
                    service,
                    "check_component",
                    unit_id=unit,
                    component_key="fabric",
                    checked=True,
                )
            await execute(db, service, "send_bag")
            await execute(db, service, "complete_stage", unit_id=1, stage="cut", note="Wrapped")
            with pytest.raises(ProductionConflict, match="пошив"):
                await execute(db, service, "return_to_dtf")
            await execute(db, service, "complete_stage", unit_id=2, stage="sewing")
            await execute(db, service, "return_to_dtf")
            with pytest.raises(ProductionConflict, match="состоянии мешка"):
                await execute(
                    db, service, "complete_stage", unit_id=2, stage="qc", quality_confirmed=[0, 1]
                )
            await execute(db, service, "dtf_ready", unit_id=1)
            await execute(db, service, "insert_dtf", unit_id=1)
            await execute(db, service, "send_bag")
            async with db.session() as session:
                detail = await ProductionReadService().detail(
                    session, project_id=1, stations=["kit"]
                )
                assert len(detail["units"]) == 2
                assert [unit["stage_index"] for unit in detail["units"]] == [1, 1]
                assert await session.scalar(select(func.count()).select_from(ProductionBag)) == 1

    asyncio.run(scenario())


def test_originals_and_order_quantity_cannot_be_silently_missing(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, service, spec):
            with pytest.raises(ProductionConflict, match="Не все файлы"):
                await execute(
                    db, service, "plan", unit_id=1, specification=spec | {"print_file_ids": [999]}
                )
            with pytest.raises(ProductionConflict, match="отдельными файлами"):
                await execute(
                    db, service, "plan", unit_id=1, specification=spec | {"print_file_ids": [1]}
                )
            async with db.session() as session:
                media = await session.get(MediaObject, 2)
                media.is_public = True
                await session.commit()
            with pytest.raises(ProductionConflict, match="приватном"):
                await execute(db, service, "plan", unit_id=1, specification=spec)
            async with db.session() as session:
                media = await session.get(MediaObject, 2)
                media.is_public = False
                await session.commit()
            await execute(db, service, "plan", unit_id=1, specification=spec)
            async with db.session() as session:
                source = await session.get(OrderItem, 1)
                source.quantity = 2
                source.line_total = source.unit_price * 2
                await session.commit()
            with pytest.raises(ProductionConflict, match="всех позиций"):
                await execute(db, service, "confirm_documents", unit_id=1)

    asyncio.run(scenario())


def test_versions_permissions_tamper_and_legacy_bypass_are_blocked(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, service, spec):
            with pytest.raises(ProductionDenied):
                await execute(db, service, "plan", actor=3, unit_id=1, specification=spec)
            with pytest.raises(ProductionDenied):
                await execute(db, service, "plan", actor=2, unit_id=1, specification=spec)
            first = await execute(
                db, service, "plan", key="plan-once", unit_id=1, specification=spec
            )
            assert (
                await execute(
                    db, service, "plan", version=0, key="plan-once", unit_id=1, specification=spec
                )
                == first
            )
            with pytest.raises(ProductionConflict, match="Ключ"):
                await execute(
                    db,
                    service,
                    "plan",
                    version=0,
                    key="plan-once",
                    unit_id=1,
                    specification=spec | {"instructions": "Changed"},
                )
            with pytest.raises(ProductionConflict, match="другим сотрудником"):
                await execute(db, service, "confirm_documents", version=0, unit_id=1)
            with pytest.raises(ProductionDenied):
                await execute(db, service, "confirm_documents", actor=2, unit_id=1)
            async with db.session() as session:
                unit = await session.get(CrmProductionUnit, 1)
                with pytest.raises(CrmProductionConflictError):
                    await CrmProductionService().transition_unit(
                        session,
                        production_unit_id=1,
                        expected_version=unit.version,
                        to_status=CrmProductionUnitStatus.IN_PROGRESS,
                        reason_code="bypass",
                        actor_user_id=1,
                    )
                assert not await IdentityRepository().user_has_permission(
                    session, user_id=2, permission=PermissionCode.CRM_ACCESS
                )
                media = await session.get(MediaObject, 2)
                media.checksum_sha256 = "f" * 64
                await session.commit()
            with pytest.raises(ProductionConflict, match="оригиналов"):
                await execute(db, service, "confirm_documents", unit_id=1)
            # Integrity failures must still be reportable and audited.
            await execute(db, service, "report_issue", unit_id=1, note="Wrong file checksum")
            async with db.session() as session:
                media = await session.get(MediaObject, 2)
                media.checksum_sha256 = "2" * 64
                item = await session.get(OrderItem, 1)
                item.size_snapshot = "S"
                await session.commit()
            with pytest.raises(ProductionConflict, match="снимка"):
                await execute(db, service, "confirm_documents", unit_id=1)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "change",
    [
        {"route": ["sewing", "cut", "qc", "packing"]},
        {"route": ["cut", "packing"]},
        {"pattern_file_ids": []},
        {"print_file_ids": []},
        {"components": []},
        {"quality_checks": [""]},
        {"instructions": ""},
    ],
)
def test_specification_requires_complete_evidence(tmp_path, change):
    async def scenario():
        async with setup(tmp_path) as (_, _, spec):
            with pytest.raises(ValidationError):
                SpecificationWrite(**(spec | change))

    asyncio.run(scenario())


def test_api_denies_customers_and_hides_delivery(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, service, spec):
            await execute(db, service, "plan", unit_id=1, specification=spec)
            app = FastAPI()
            app.include_router(router)
            app.state.database = db
            app.state.settings = service.settings.model_copy(
                update={"production_terminal_enabled": True}
            )
            async with db.session() as session:
                people = {x.id: x for x in await session.scalars(select(User))}
            current = people[3]

            async def identity():
                return current

            app.dependency_overrides[get_production_user] = identity
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="https://test"
            ) as client:
                assert (await client.get("/api/production/me")).status_code == 403
                current = people[2]
                response = await client.get("/api/production/projects/1")
                assert response.status_code == 200, response.text
                assert response.headers["cache-control"] == "no-store"
                assert response.json()["delivery"] is None
                response = await client.post(
                    "/api/production/projects/1/commands",
                    json={"action": "release", "expected_version": 1},
                    headers={"Idempotency-Key": "wrong-station-command"},
                )
                assert response.status_code == 403
                app.state.settings.production_terminal_enabled = False
                assert (await client.get("/api/production/me")).status_code == 503

    asyncio.run(scenario())


def test_bag_commands_cannot_record_an_unrelated_unit_or_specification():
    with pytest.raises(ValidationError, match="Параметры"):
        ProductionCommand(action="release", expected_version=1, unit_id=999)
    with pytest.raises(ValidationError, match="Параметры"):
        ProductionCommand(
            action="dtf_ready", expected_version=1, unit_id=1, tracking_number="fake-track"
        )


@pytest.mark.skipif(
    not os.getenv("PRODUCTION_TEST_POSTGRES_URL"), reason="Isolated PostgreSQL CI required"
)
def test_postgres_duplicate_commands_and_competing_versions(tmp_path):
    async def scenario():
        async with setup(tmp_path, os.environ["PRODUCTION_TEST_POSTGRES_URL"]) as (
            db,
            service,
            spec,
        ):
            rows = await asyncio.gather(
                *[
                    execute(
                        db,
                        service,
                        "plan",
                        version=0,
                        key="concurrent-plan",
                        unit_id=1,
                        specification=spec,
                    )
                    for _ in range(5)
                ]
            )
            assert all(row == rows[0] for row in rows)
            outcomes = await asyncio.gather(
                *[
                    execute(db, service, "confirm_documents", version=1, unit_id=1)
                    for _ in range(5)
                ],
                return_exceptions=True,
            )
            assert sum(isinstance(x, ProductionConflict) for x in outcomes) == 4
            async with db.session() as session:
                assert (
                    await session.scalar(select(func.count()).select_from(ProductionSpecification))
                    == 1
                )
                assert await session.scalar(select(func.count()).select_from(ProductionEvent)) == 2

    asyncio.run(scenario())
