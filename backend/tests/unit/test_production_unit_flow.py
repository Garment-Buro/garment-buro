import asyncio
import json
import secrets

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.modules.identity.models import RoleName, User, UserRole
from app.modules.identity.repository import IdentityRepository
from app.modules.production.auth_models import ProductionEmployee
from app.modules.production.evidence import ProductionConflict
from app.modules.production.models import ProductionBag, ProductionEvent, ProductionWorkItem
from app.modules.production.read_service import ProductionReadService
from app.modules.production.router import router
from app.modules.production.security import ProductionDenied
from tests.unit.test_production_terminal import execute, setup


async def workers(db):
    result = {"tech": 1, "cut": 2}
    async with db.session() as session:
        repo = IdentityRepository()
        for station in ("kit", "dtf", "workshop", "packing"):
            person = User(internal_identity=f"employee:{station}", first_name=station)
            session.add(person)
            await session.flush()
            role = await repo.get_role(session, RoleName(f"production_{station}"))
            session.add(UserRole(user_id=person.id, role_id=role.id))
            session.add(ProductionEmployee(user_id=person.id, primary_station=station))
            result[station] = person.id
        await session.commit()
    return result


def test_independent_units_qr_dtf_workshop_and_packing(tmp_path):
    async def scenario():
        async with setup(tmp_path, quantity=2) as (db, service, spec):
            people = await workers(db)
            await execute(db, service, "plan", unit_id=1, specification=spec)
            await execute(
                db,
                service,
                "plan",
                unit_id=2,
                specification=spec
                | {
                    "route": ["sewing", "qc", "packing"],
                    "pattern_file_ids": [],
                    "print_file_ids": [],
                },
            )
            for unit in (1, 2):
                await execute(db, service, "confirm_documents", unit_id=unit)
            await execute(db, service, "release")
            with pytest.raises(ProductionDenied):
                await execute(
                    db, service, "issue_unit_label", unit_id=1
                )  # Technologist is not a cutter.
            with pytest.raises(ProductionConflict, match="QR"):
                await execute(
                    db, service, "complete_stage", actor=2, unit_id=1, stage="cut", note="Ready"
                )
            for unit in (1, 2):
                await execute(db, service, "issue_unit_label", actor=2, unit_id=unit)
                await execute(
                    db,
                    service,
                    "complete_stage",
                    actor=2,
                    unit_id=unit,
                    stage="cut",
                    note="QR attached",
                )
            async with db.session() as session:
                queue = await ProductionReadService().queue(session)
                assert queue["items"][0]["dtf_pending"] == 1
                assert queue["items"][0]["stage_counts"] == {"waiting_dtf": 1, "kit": 1}
            with pytest.raises(ProductionConflict, match="комплектующие"):
                await execute(db, service, "send_unit", actor=people["kit"], unit_id=2)
            for unit in (1, 2):
                await execute(
                    db,
                    service,
                    "check_component",
                    actor=people["kit"],
                    unit_id=unit,
                    component_key="fabric",
                    checked=True,
                )
            with pytest.raises(ProductionConflict, match="DTF"):
                await execute(db, service, "send_unit", actor=people["kit"], unit_id=1)
            await execute(db, service, "send_unit", actor=people["kit"], unit_id=2)
            with pytest.raises(ProductionConflict, match="качество"):
                await execute(db, service, "complete_workshop", actor=people["workshop"], unit_id=2)
            await execute(
                db,
                service,
                "complete_workshop",
                actor=people["workshop"],
                unit_id=2,
                quality_confirmed=[0, 1],
            )
            await execute(
                db, service, "complete_stage", actor=people["packing"], unit_id=2, stage="packing"
            )
            with pytest.raises(ProductionConflict):
                await execute(db, service, "pack_bag", actor=people["packing"])
            async with db.session() as session:
                data = await ProductionReadService().detail(session, project_id=1, stations=["kit"])
                assert data["units"][0]["lane"] == "waiting_dtf"
                assert data["units"][1]["lane"] == "done"
            await execute(db, service, "dtf_ready", actor=people["dtf"], unit_id=1)
            with pytest.raises(ProductionConflict, match="вложение"):
                await execute(db, service, "send_unit", actor=people["kit"], unit_id=1)
            await execute(db, service, "insert_dtf", actor=people["kit"], unit_id=1)
            receipt = await execute(
                db, service, "send_unit", actor=people["kit"], unit_id=1, key="handoff-retry"
            )
            assert (
                await execute(
                    db,
                    service,
                    "send_unit",
                    actor=people["kit"],
                    unit_id=1,
                    version=receipt.version - 1,
                    key="handoff-retry",
                )
                == receipt
            )
            await execute(
                db,
                service,
                "complete_workshop",
                actor=people["workshop"],
                unit_id=1,
                quality_confirmed=[0, 1],
            )
            await execute(
                db, service, "complete_stage", actor=people["packing"], unit_id=1, stage="packing"
            )
            await execute(db, service, "pack_bag", actor=people["packing"])
            async with db.session() as session:
                bag = await session.scalar(select(ProductionBag))
                assert bag.state == "packed" and len(bag.public_token) == 43
                unit = await session.scalar(
                    select(ProductionWorkItem).where(ProductionWorkItem.unit_id == 1)
                )
                token = unit.public_token
                assert token != bag.public_token
                events = list(
                    await session.scalars(select(ProductionEvent).order_by(ProductionEvent.version))
                )
                assert [e.version for e in events] == list(range(1, bag.version + 1))
            app = FastAPI()
            app.state.database = db
            app.state.settings = service.settings.model_copy(
                update={"production_terminal_enabled": True}
            )
            app.include_router(router)
            async with AsyncClient(transport=ASGITransport(app), base_url="https://test") as client:
                response = await client.get(f"/api/production/labels/{token}")
                assert response.status_code == 200, response.text
                assert response.headers["cache-control"] == "no-store"
                data = response.json()
                assert data["unit_id"] == 1 and len(data["units"]) == 1
                assert set(data["units"][0]) == {"id", "number", "title", "size", "color", "state"}
                for forbidden in (
                    "phone",
                    "price",
                    "delivery",
                    "recipient",
                    "customization",
                    "components",
                    "Test address",
                ):
                    assert forbidden not in response.text
                assert (
                    await client.get(f"/api/production/labels/{secrets.token_urlsafe(32)}")
                ).status_code == 404
                assert (await client.get("/api/production/labels/1")).status_code == 422

    asyncio.run(scenario())


def test_role_projection_and_employee_absence(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, service, spec):
            people = await workers(db)
            await execute(db, service, "plan", unit_id=1, specification=spec)
            async with db.session() as session:
                for role in ("tech", "cut", "dtf", "kit", "workshop", "packing"):
                    data = await ProductionReadService().detail(
                        session, project_id=1, stations=[role]
                    )
                    assert bool(data["delivery"]) == (role == "packing")
                    assert data["customer"] == "Заказ №1"
                    assert "storage_digest" not in json.dumps(data, default=str)
                    item = data["units"][0]
                    assert bool(item["specification"]["components"]) == (role in {"tech", "kit"})
                    if role == "dtf":
                        assert item["specification"]["pattern_file_ids"] == []
                        assert [x["id"] for x in item["files"]] == [2]
                employee = await session.scalar(
                    select(ProductionEmployee).where(ProductionEmployee.user_id == people["kit"])
                )
                employee.availability = "sick"
                await session.commit()
            with pytest.raises(ProductionDenied, match="отсутствует"):
                await execute(
                    db, service, "report_issue", actor=people["kit"], unit_id=1, note="Unavailable"
                )

    asyncio.run(scenario())


def test_nested_customization_never_exposes_prices_or_contacts():
    from app.modules.production.projections import floor_customization

    raw = {
        "totalPrice": 1000,
        "phone": "secret",
        "decorations": [
            {
                "price": 50,
                "side": "back",
                "position": {"x": 2, "y": 4, "cost": 5},
                "content": {"text": "ABC", "email": "secret"},
            }
        ],
    }
    assert floor_customization(raw) == {
        "decorations": [{"side": "back", "position": {"x": 2, "y": 4}, "content": {"text": "ABC"}}]
    }


def test_current_role_controls_contact_access_and_revocation(tmp_path):
    from sqlalchemy import delete

    from app.modules.production.auth_router import get_production_user

    async def scenario():
        async with setup(tmp_path) as (db, service, spec):
            await execute(db, service, "plan", unit_id=1, specification=spec)
            async with db.session() as session:
                packing = await IdentityRepository().get_role(session, RoleName.PRODUCTION_PACKING)
                packing_id = packing.id
                session.add(UserRole(user_id=1, role_id=packing_id))
                await session.commit()
                user = await session.get(User, 1)
            app = FastAPI()
            app.include_router(router)
            app.state.database = db
            app.state.settings = service.settings.model_copy(
                update={"production_terminal_enabled": True}
            )
            app.dependency_overrides[get_production_user] = lambda: user
            async with AsyncClient(transport=ASGITransport(app), base_url="https://test") as client:
                tech = await client.get("/api/production/projects/1?station=tech")
                pack = await client.get("/api/production/projects/1?station=packing")
                assert tech.json()["delivery"] is None
                assert pack.json()["delivery"]["phone"] == "+79990000000"
                assert (
                    await client.get("/api/production/projects/1?station=dtf")
                ).status_code == 403
                async with db.session() as session:
                    await session.execute(
                        delete(UserRole).where(
                            UserRole.user_id == 1, UserRole.role_id == packing_id
                        )
                    )
                    await session.commit()
                assert (
                    await client.get("/api/production/projects/1?station=packing")
                ).status_code == 403

    asyncio.run(scenario())
