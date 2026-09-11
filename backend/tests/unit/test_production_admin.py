import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import select

from app.modules.identity.models import RoleName, SecurityAuditEvent, User, UserRole
from app.modules.identity.repository import IdentityRepository
from app.modules.orders.models import Order
from app.modules.partners.models import PartnerPayoutRequest, PartnerProfile
from app.modules.partners.service import PartnerProgramService
from app.modules.production.auth_models import ProductionCredential, ProductionEmployee
from app.modules.production.auth_service import issue_code
from app.modules.production.router import router
from tests.unit.test_production_auth import PEPPER
from tests.unit.test_production_terminal import setup


@asynccontextmanager
async def admin_app(tmp_path):
    async with setup(tmp_path) as (db, service, _):
        settings = service.settings.model_copy(
            update={
                "production_terminal_enabled": True,
                "identity_otp_pepper": SecretStr(PEPPER),
                "partner_program_enabled": True,
                "partner_attribution_secret": SecretStr(
                    "test-only-partner-attribution-secret-not-for-deployment"
                ),
                "public_base_url": "https://test",
                "cors_origins": "https://test",
            }
        )
        app = FastAPI()
        app.include_router(router)
        app.state.database = db
        app.state.settings = settings
        app.state.partner_program_service = PartnerProgramService(settings)
        async with db.session() as session:
            repo = IdentityRepository()
            person = User(
                email="admin@example.test",
                email_normalized="admin@example.test",
                first_name="Администратор",
            )
            session.add(person)
            await session.flush()
            role = await repo.get_role(session, RoleName.PRODUCTION_ADMIN)
            session.add(UserRole(user_id=person.id, role_id=role.id))
            profile = PartnerProfile(
                user_id=3,
                code="test-partner",
                display_name="Тестовый партнёр",
                commission_bps=1000,
                status="active",
            )
            session.add(profile)
            await session.flush()
            session.add(PartnerPayoutRequest(partner_id=profile.id, amount=Decimal("1250.50")))
            await session.commit()
            admin_code = await issue_code(
                session, user_id=person.id, station="admin", pepper=PEPPER
            )
            session.add(ProductionEmployee(user_id=2, primary_station="cut"))
            cutter_code = await issue_code(session, user_id=2, station="cut", pepper=PEPPER)
            await session.commit()
        yield app, db, admin_code, cutter_code


def test_administrator_reads_all_sections_without_exposing_secrets(tmp_path):
    async def scenario():
        async with admin_app(tmp_path) as (app, db, code, _):
            assert len(code) == 8 and code.startswith("99")
            async with AsyncClient(transport=ASGITransport(app), base_url="https://test") as client:
                result = await client.post("/api/production/auth/login", json={"code": code})
                assert result.status_code == 200, result.text
                assert (await client.get("/api/production/me")).json()["can_administer"]
                for name in (
                    "stats",
                    "orders",
                    "employees",
                    "users",
                    "clients",
                    "payouts",
                    "orders/1",
                ):
                    response = await client.get(f"/api/production/admin/{name}")
                    assert response.status_code == 200, response.text
                    assert response.headers["cache-control"] == "no-store"
                    assert "code_digest" not in response.text and "ciphertext" not in response.text
                    assert "signing_url" not in response.text and "session" not in response.text
                stats = (await client.get("/api/production/admin/stats")).json()
                assert stats["employees_count"] == 1 and stats["orders_count"] == 1
                assert stats["payout_states"] == [
                    {"status": "requested", "count": 1, "amount": "1250.50"}
                ]
                users = (await client.get("/api/production/admin/employees?limit=1")).json()
                assert len(users["items"]) == 1 and users["next_offset"] is None
                assert (
                    await client.get("/api/production/admin/employees?q=customer%40example.test")
                ).json()["items"] == []
                assert (await client.get("/api/production/admin/orders/999")).status_code == 404
                assert (
                    await client.get("/api/production/admin/employees?limit=10000")
                ).status_code == 422
            async with db.session() as session:
                # Unpaid orders must not be counted as captured/paid turnover.
                order = await session.get(Order, 1)
                order.payment_status = "pending"
                await session.commit()
            async with AsyncClient(transport=ASGITransport(app), base_url="https://test") as client:
                await client.post("/api/production/auth/login", json={"code": code})
                assert (await client.get("/api/production/admin/stats")).json()[
                    "paid_orders_total"
                ] == "0.00"

    asyncio.run(scenario())


def test_floor_code_cannot_be_used_as_admin_even_after_role_grant(tmp_path):
    async def scenario():
        async with admin_app(tmp_path) as (app, db, _, cutter):
            async with AsyncClient(transport=ASGITransport(app), base_url="https://test") as client:
                assert (await client.get("/api/production/admin/employees")).status_code == 401
                await client.post("/api/production/auth/login", json={"code": cutter})
                for path in ("stats", "orders", "orders/1", "users", "clients", "payouts"):
                    assert (await client.get(f"/api/production/admin/{path}")).status_code == 403
                async with db.session() as session:
                    role = await IdentityRepository().get_role(session, RoleName.PRODUCTION_ADMIN)
                    session.add(UserRole(user_id=2, role_id=role.id))
                    await session.commit()
                assert not (await client.get("/api/production/me")).json()["can_administer"]
                assert (await client.get("/api/production/admin/employees")).status_code == 403
                assert (
                    await client.post(
                        "/api/production/admin/payouts/1/review",
                        json={
                            "status": "approved",
                            "expected_status": "requested",
                            "note": "Checked",
                        },
                    )
                ).status_code == 403

    asyncio.run(scenario())


def test_payout_decision_is_guarded_audited_and_never_marks_paid(tmp_path):
    async def scenario():
        async with admin_app(tmp_path) as (app, db, code, _):
            async with AsyncClient(transport=ASGITransport(app), base_url="https://test") as client:
                await client.post("/api/production/auth/login", json={"code": code})
                payload = {
                    "expected_status": "requested",
                    "status": "approved",
                    "note": "Реквизиты и договор проверены",
                }
                url = "/api/production/admin/payouts/1/review"
                assert (
                    await client.post(url, json=payload, headers={"Origin": "https://evil.test"})
                ).status_code == 403
                assert (
                    await client.post(url, json=payload | {"status": "paid"})
                ).status_code == 422
                assert (await client.post(url, json=payload | {"note": "   "})).status_code == 422
                result = await client.post(url, json=payload)
                assert result.status_code == 200, result.text
                assert result.json()["status"] == "approved"
                assert (await client.post(url, json=payload)).status_code == 409
                assert (
                    await client.post(
                        url, json={**payload, "expected_status": "approved", "status": "rejected"}
                    )
                ).status_code == 200
            async with db.session() as session:
                payout = await session.get(PartnerPayoutRequest, 1)
                assert payout.paid_at is None and payout.status == "rejected"
                events = list(
                    await session.scalars(
                        select(SecurityAuditEvent).where(
                            SecurityAuditEvent.event_type == "production.payout_review"
                        )
                    )
                )
                assert len(events) == 2 and all(e.actor_user_id == 4 for e in events)

    asyncio.run(scenario())


def test_admin_code_is_not_available_to_ordinary_worker(tmp_path):
    async def scenario():
        async with admin_app(tmp_path) as (_, db, _, _):
            async with db.session() as session:
                with pytest.raises(ValueError):
                    await issue_code(session, user_id=2, station="admin", pepper=PEPPER)

    asyncio.run(scenario())


def test_admin_manages_employee_roles_status_and_one_time_codes(tmp_path):
    async def scenario():
        async with admin_app(tmp_path) as (app, db, admin_code, _):
            async with AsyncClient(transport=ASGITransport(app), base_url="https://test") as client:
                await client.post("/api/production/auth/login", json={"code": admin_code})
                payload = {
                    "first_name": "Мария",
                    "last_name": "Орлова",
                    "email": None,
                    "phone": "+375291112233",
                    "status": "active",
                    "stations": ["cut", "sewing"],
                    "primary_station": "cut",
                }
                created = await client.post("/api/production/admin/employees", json=payload)
                assert created.status_code == 200, created.text
                result = created.json()
                employee_id = result["employee"]["id"]
                first_code = result["code"]
                assert len(first_code) == 6 and first_code.startswith("2")
                assert result["employee"]["stations"] == ["cut", "sewing"]

                # The raw code is shown once and never appears in a later read.
                listed = await client.get(f"/api/production/admin/employees?q={employee_id}")
                assert listed.status_code == 200
                assert listed.json()["items"][0]["code_active"] is True
                assert first_code not in listed.text and "code_digest" not in listed.text

                async with AsyncClient(
                    transport=ASGITransport(app), base_url="https://test"
                ) as worker:
                    assert (
                        await worker.post("/api/production/auth/login", json={"code": first_code})
                    ).status_code == 200
                    me = (await worker.get("/api/production/me")).json()
                    assert me["stations"] == ["cut", "sewing"]

                changed = await client.put(
                    f"/api/production/admin/employees/{employee_id}",
                    json=payload
                    | {
                        "stations": ["sewing", "packing"],
                        "primary_station": "sewing",
                    },
                )
                assert changed.status_code == 200, changed.text
                second_code = changed.json()["code"]
                assert len(second_code) == 6 and second_code.startswith("5")
                assert second_code != first_code

                async with AsyncClient(
                    transport=ASGITransport(app), base_url="https://test"
                ) as worker:
                    assert (
                        await worker.post("/api/production/auth/login", json={"code": first_code})
                    ).status_code == 401
                    assert (
                        await worker.post("/api/production/auth/login", json={"code": second_code})
                    ).status_code == 200
                    assert (await worker.get("/api/production/me")).json()["stations"] == [
                        "sewing",
                        "packing",
                    ]

                blocked = await client.put(
                    f"/api/production/admin/employees/{employee_id}",
                    json=payload | {"status": "blocked"},
                )
                assert blocked.status_code == 200 and blocked.json()["code"] is None
                assert blocked.json()["employee"]["code_active"] is False
                assert (
                    await client.post(f"/api/production/admin/employees/{employee_id}/code")
                ).status_code == 409

                activated = await client.put(
                    f"/api/production/admin/employees/{employee_id}", json=payload
                )
                third_code = activated.json()["code"]
                assert activated.status_code == 200 and third_code.startswith("2")
                rotated = await client.post(f"/api/production/admin/employees/{employee_id}/code")
                assert rotated.status_code == 200
                fourth_code = rotated.json()["code"]
                assert fourth_code != third_code and fourth_code.startswith("2")

                invalid = await client.post(
                    "/api/production/admin/employees",
                    json=payload | {"primary_station": "admin", "stations": ["admin"]},
                )
                assert invalid.status_code == 422
                assert (
                    await client.post(
                        "/api/production/admin/employees",
                        json=payload | {"primary_station": "cut", "stations": ["sewing"]},
                    )
                ).status_code == 422
                assert (
                    await client.post(
                        "/api/production/admin/employees",
                        json=payload,
                        headers={"Origin": "https://evil.test"},
                    )
                ).status_code == 403

            async with db.session() as session:
                employee = await session.scalar(
                    select(ProductionEmployee).where(ProductionEmployee.user_id == employee_id)
                )
                user = await session.get(User, employee_id)
                credentials = list(
                    await session.scalars(
                        select(ProductionCredential).where(
                            ProductionCredential.user_id == employee_id
                        )
                    )
                )
                events = list(
                    await session.scalars(
                        select(SecurityAuditEvent).where(
                            SecurityAuditEvent.subject_user_id == employee_id
                        )
                    )
                )
                assert employee is not None and user.internal_identity.startswith("employee:")
                assert user.email is None and len(credentials) == 4
                assert sum(item.active for item in credentials) == 1
                assert all(len(item.code_digest) == 64 for item in credentials)
                assert {item.event_type for item in events} >= {
                    "production.employee_created",
                    "production.employee_updated",
                    "production.employee_code_rotated",
                }

    asyncio.run(scenario())
