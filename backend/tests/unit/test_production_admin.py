import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
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
from app.modules.payments.models import Payment
from app.modules.production.auth_models import ProductionCredential, ProductionEmployee
from app.modules.production.auth_service import issue_code
from app.modules.production.inbox_models import AdminInboxItem
from app.modules.production.models import ProductionDemoEmployee
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
            role = await repo.get_role(session, RoleName.ADMIN)
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
            order = await session.get(Order, 1)
            order.user_id = 3
            order.email = "customer@example.test"
            order.email_normalized = "customer@example.test"
            order.first_name = "Покупатель"
            session.add(PartnerPayoutRequest(partner_id=profile.id, amount=Decimal("1250.50")))
            session.add_all(
                [
                    AdminInboxItem(
                        kind="support",
                        subject="Не открывается заказ",
                        message="После оплаты страница заказа не загрузилась",
                        reporter_user_id=3,
                        reporter_name="Покупатель",
                        reporter_email="customer@example.test",
                        order_id=1,
                    ),
                    AdminInboxItem(
                        kind="production_problem",
                        subject="Нет материала на раскрое",
                        message="Для единицы производства не найден рулон ткани",
                        reporter_user_id=2,
                        reporter_name="Раскрой",
                        project_id=1,
                        production_unit_id=1,
                        station="cut",
                        priority="high",
                    ),
                ]
            )
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
                    "support",
                    "support/1",
                    "problems",
                    "problems/2",
                    "orders/1",
                    "assortment/models",
                    "assortment/fabrics",
                    "assortment/patterns",
                    "assortment/tech-cards",
                    "assortment/accessories",
                    "assortment/boxes",
                    "assortment/products",
                ):
                    response = await client.get(f"/api/production/admin/{name}")
                    assert response.status_code == 200, response.text
                    assert response.headers["cache-control"] == "no-store"
                    assert "code_digest" not in response.text and "ciphertext" not in response.text
                    assert "signing_url" not in response.text and "session" not in response.text
                stats = (await client.get("/api/production/admin/stats")).json()
                assert stats["employees_count"] == 1 and stats["orders_count"] == 1
                assert stats["support_open_count"] == 1
                assert stats["problems_open_count"] == 1
                assert set(stats["week_change"]) == {
                    "orders_count",
                    "orders_total",
                    "paid_orders_total",
                    "employees_count",
                    "clients_count",
                    "support_open_count",
                    "problems_open_count",
                }
                assert stats["week_change"]["support_open_count"] == 1
                assert stats["week_change"]["problems_open_count"] == 1
                assert stats["payout_states"] == [
                    {"status": "requested", "count": 1, "amount": "1250.50"}
                ]
                users = (await client.get("/api/production/admin/employees?limit=1")).json()
                assert len(users["items"]) == 1 and users["next_offset"] is None
                assert (
                    await client.get("/api/production/admin/employees?sort=name&direction=asc")
                ).status_code == 200
                clients = (
                    await client.get(
                        "/api/production/admin/clients",
                        params={
                            "kind": "registered",
                            "sort": "orders_total",
                            "direction": "desc",
                        },
                    )
                ).json()
                detail = await client.get(
                    "/api/production/admin/clients/detail",
                    params={"key": clients["items"][0]["key"]},
                )
                assert detail.status_code == 200, detail.text
                assert detail.json()["account"]["id"] == 3
                assert [order["id"] for order in detail.json()["orders"]] == [1]
                assert [ticket["id"] for ticket in detail.json()["tickets"]] == [1]
                assert detail.json()["recipient"]["city"] == "Test city"
                assert (
                    await client.get("/api/production/admin/employees?q=customer%40example.test")
                ).json()["items"] == []
                assert (await client.get("/api/production/admin/orders/999")).status_code == 404
                assert (
                    await client.get("/api/production/admin/employees?limit=10000")
                ).status_code == 422
                assert (
                    await client.get("/api/production/admin/clients?sort=unknown")
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


def test_statistics_reports_change_since_last_week(tmp_path):
    async def scenario():
        async with admin_app(tmp_path) as (app, db, code, _):
            now = datetime.now(timezone.utc)
            async with db.session() as session:
                order = await session.get(Order, 1)
                employee = await session.get(ProductionEmployee, 1)
                support = await session.get(AdminInboxItem, 1)
                order.created_at = now - timedelta(days=8)
                employee.created_at = now - timedelta(days=8)
                support.created_at = now - timedelta(days=8)
                support.status = "resolved"
                support.resolved_at = now - timedelta(days=1)
                payment = await session.scalar(select(Payment).where(Payment.order_id == order.id))
                payment.status = "succeeded"
                payment.amount = Decimal("321.45")
                payment.succeeded_at = now - timedelta(days=1)
                await session.commit()
            async with AsyncClient(transport=ASGITransport(app), base_url="https://test") as client:
                await client.post("/api/production/auth/login", json={"code": code})
                stats = (await client.get("/api/production/admin/stats")).json()
                assert stats["week_change"]["orders_count"] == 0
                assert stats["week_change"]["employees_count"] == 0
                assert stats["week_change"]["clients_count"] == 0
                assert stats["week_change"]["paid_orders_total"] == "321.45"
                assert stats["week_change"]["support_open_count"] == -1
                assert stats["week_change"]["problems_open_count"] == 1

    asyncio.run(scenario())


def test_orders_and_payouts_support_allowlisted_sorting(tmp_path):
    async def scenario():
        async with admin_app(tmp_path) as (app, db, code, _):
            async with db.session() as session:
                session.add(
                    Order(
                        email="large-order@example.test",
                        email_normalized="large-order@example.test",
                        first_name="Большой",
                        items_subtotal=Decimal("999999.00"),
                        delivery_price=Decimal("0.00"),
                        total_price=Decimal("999999.00"),
                        request_fingerprint_sha256="f" * 64,
                    )
                )
                session.add(
                    PartnerPayoutRequest(
                        partner_id=1,
                        amount=Decimal("250.00"),
                    )
                )
                await session.commit()
            async with AsyncClient(transport=ASGITransport(app), base_url="https://test") as client:
                await client.post("/api/production/auth/login", json={"code": code})
                orders = (
                    await client.get("/api/production/admin/orders?sort=total&direction=desc")
                ).json()
                assert orders["items"][0]["total"] == "999999.00"
                payouts = (
                    await client.get("/api/production/admin/payouts?sort=amount&direction=asc")
                ).json()
                assert [row["amount"] for row in payouts["items"]] == [
                    "250.00",
                    "1250.50",
                ]
                assert (
                    await client.get("/api/production/admin/orders?sort=created_at;drop")
                ).status_code == 422
                assert (
                    await client.get("/api/production/admin/payouts?direction=sideways")
                ).status_code == 422

    asyncio.run(scenario())


def test_admin_filters_and_updates_support_and_production_problems(tmp_path):
    async def scenario():
        async with admin_app(tmp_path) as (app, db, admin_code, cutter_code):
            async with AsyncClient(transport=ASGITransport(app), base_url="https://test") as client:
                await client.post("/api/production/auth/login", json={"code": admin_code})

                support = await client.get("/api/production/admin/support?q=оплаты&priority=normal")
                assert support.status_code == 200, support.text
                assert [item["subject"] for item in support.json()["items"]] == [
                    "Не открывается заказ"
                ]
                assert (
                    await client.get("/api/production/admin/support?sort=updated_at&direction=asc")
                ).status_code == 200
                assert (
                    await client.get("/api/production/admin/support?status=unknown")
                ).status_code == 422
                assert (await client.get("/api/production/admin/support/999")).status_code == 404
                assert (await client.get("/api/production/admin/problems/1")).status_code == 404

                updated = await client.patch(
                    "/api/production/admin/support/1",
                    json={
                        "expected_version": 1,
                        "status": "in_progress",
                        "priority": "high",
                        "assigned_to_user_id": 4,
                        "admin_note": "Проверяем статус оплаты",
                    },
                )
                assert updated.status_code == 200, updated.text
                assert updated.json()["version"] == 2
                assert updated.json()["status"] == "in_progress"
                assert updated.json()["assigned_to_user_id"] == 4

                stale = await client.patch(
                    "/api/production/admin/support/1",
                    json={
                        "expected_version": 1,
                        "status": "closed",
                        "priority": "high",
                    },
                )
                assert stale.status_code == 409

                resolved = await client.patch(
                    "/api/production/admin/support/1",
                    json={
                        "expected_version": 2,
                        "status": "resolved",
                        "priority": "high",
                        "assigned_to_user_id": 4,
                        "admin_note": "Доступ к заказу восстановлен",
                    },
                )
                assert resolved.status_code == 200
                assert resolved.json()["resolved_at"] is not None
                assert (await client.get("/api/production/admin/stats")).json()[
                    "support_open_count"
                ] == 0

            async with AsyncClient(transport=ASGITransport(app), base_url="https://test") as floor:
                await floor.post("/api/production/auth/login", json={"code": cutter_code})
                assert (await floor.get("/api/production/admin/problems")).status_code == 403

            async with db.session() as session:
                events = list(
                    await session.scalars(
                        select(SecurityAuditEvent).where(
                            SecurityAuditEvent.event_type == "production.admin_inbox_updated"
                        )
                    )
                )
                assert len(events) == 2
                assert all(event.actor_user_id == 4 for event in events)

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
                    await client.get("/api/production/admin/assortment/models")
                ).status_code == 403
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


def test_production_administrator_only_sees_orders_and_problems(tmp_path):
    async def scenario():
        async with admin_app(tmp_path) as (app, db, code, _):
            async with db.session() as session:
                admin = await session.scalar(select(User).where(User.email == "admin@example.test"))
                await session.execute(
                    UserRole.__table__.delete().where(UserRole.user_id == admin.id)
                )
                role = await IdentityRepository().get_role(session, RoleName.PRODUCTION_SUPERVISOR)
                session.add(UserRole(user_id=admin.id, role_id=role.id))
                await session.commit()

            async with AsyncClient(transport=ASGITransport(app), base_url="https://test") as client:
                assert (
                    await client.post("/api/production/auth/login", json={"code": code})
                ).status_code == 200
                me = (await client.get("/api/production/me")).json()
                assert me["can_administer"] is True
                assert me["admin_scope"] == "production"
                for path in ("orders", "orders/1", "problems", "problems/2", "tickets/2"):
                    assert (await client.get(f"/api/production/admin/{path}")).status_code == 200
                for path in (
                    "stats",
                    "employees",
                    "clients",
                    "payouts",
                    "support",
                    "support/1",
                    "tickets/1",
                    "assortment/models",
                ):
                    assert (await client.get(f"/api/production/admin/{path}")).status_code == 403

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
                    "last_name": "",
                    "email": None,
                    "phone": None,
                    "status": "active",
                    "stations": ["cut", "workshop"],
                    "primary_station": "cut",
                }
                created = await client.post("/api/production/admin/employees", json=payload)
                assert created.status_code == 200, created.text
                result = created.json()
                employee_id = result["employee"]["id"]
                first_code = result["code"]
                assert len(first_code) == 6 and first_code.startswith("2")
                assert result["employee"]["stations"] == ["cut", "workshop"]
                assert result["employee"]["last_name"] == ""
                assert result["employee"]["phone"] is None

                # The raw code is shown once and never appears in a later read.
                listed = await client.get(f"/api/production/admin/employees?q={employee_id}")
                assert listed.status_code == 200
                assert listed.json()["items"][0]["code_active"] is True
                assert first_code not in listed.text and "code_digest" not in listed.text
                found_by_code = await client.get(f"/api/production/admin/employees?q={first_code}")
                assert [item["id"] for item in found_by_code.json()["items"]] == [employee_id]

                async with AsyncClient(
                    transport=ASGITransport(app), base_url="https://test"
                ) as worker:
                    assert (
                        await worker.post("/api/production/auth/login", json={"code": first_code})
                    ).status_code == 200
                    me = (await worker.get("/api/production/me")).json()
                    assert me["stations"] == ["cut", "workshop"]

                changed = await client.put(
                    f"/api/production/admin/employees/{employee_id}",
                    json=payload
                    | {
                        "stations": ["workshop", "packing"],
                        "primary_station": "workshop",
                    },
                )
                assert changed.status_code == 200, changed.text
                second_code = changed.json()["code"]
                assert len(second_code) == 6 and second_code.startswith("4")
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
                        "workshop",
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
                removed_role = await client.post(
                    "/api/production/admin/employees",
                    json=payload | {"primary_station": "sewing", "stations": ["sewing"]},
                )
                assert removed_role.status_code == 422
                assert (
                    await client.post(
                        "/api/production/admin/employees",
                        json=payload | {"primary_station": "cut", "stations": ["workshop"]},
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


def test_admin_lists_and_finds_isolated_demo_access_by_code(tmp_path):
    async def scenario():
        async with admin_app(tmp_path) as (app, db, admin_code, _):
            async with db.session() as session:
                repo = IdentityRepository()
                demo = User(
                    email="production-demo-qc@garment-buro.invalid",
                    email_normalized="production-demo-qc@garment-buro.invalid",
                    first_name="Демо · ОТК",
                )
                session.add(demo)
                await session.flush()
                session.add(ProductionDemoEmployee(user_id=demo.id, station="qc"))
                role = await repo.get_role(session, RoleName.PRODUCTION_QC)
                session.add(UserRole(user_id=demo.id, role_id=role.id))
                await session.flush()
                demo_code = await issue_code(session, user_id=demo.id, station="qc", pepper=PEPPER)
                await session.commit()

            async with AsyncClient(transport=ASGITransport(app), base_url="https://test") as client:
                await client.post("/api/production/auth/login", json={"code": admin_code})
                response = await client.get(f"/api/production/admin/employees?q={demo_code}")
                assert response.status_code == 200, response.text
                assert response.json()["items"] == [
                    {
                        "id": demo.id,
                        "is_demo": False,
                        "availability": "available",
                        "is_production_admin": False,
                        "first_name": "Демо · ОТК",
                        "last_name": "",
                        "name": "Демо · ОТК",
                        "email": "production-demo-qc@garment-buro.invalid",
                        "phone": None,
                        "status": "active",
                        "created_at": response.json()["items"][0]["created_at"],
                        "stations": ["qc"],
                        "primary_station": "qc",
                        "code_active": True,
                        "code_updated_at": response.json()["items"][0]["code_updated_at"],
                    }
                ]
                assert demo_code not in response.text
                adopted = await client.put(
                    f"/api/production/admin/employees/{demo.id}",
                    json={
                        "first_name": "Контроль качества",
                        "last_name": "Сотрудник",
                        "email": None,
                        "phone": None,
                        "status": "active",
                        "availability": "available",
                        "is_production_admin": False,
                        "stations": ["workshop"],
                        "primary_station": "workshop",
                    },
                )
                assert adopted.status_code == 200, adopted.text
                assert adopted.json()["employee"]["is_demo"] is False
            async with db.session() as session:
                assert (
                    await session.scalar(
                        select(ProductionDemoEmployee.id).where(
                            ProductionDemoEmployee.user_id == demo.id
                        )
                    )
                    is None
                )
                assert (
                    await session.scalar(
                        select(ProductionEmployee.id).where(ProductionEmployee.user_id == demo.id)
                    )
                    is not None
                )

    asyncio.run(scenario())


def test_system_admin_can_assign_manager_access_with_regular_employee_code(tmp_path):
    async def scenario():
        async with admin_app(tmp_path) as (app, _, admin_code, _):
            payload = {
                "first_name": "Начальник производства",
                "last_name": "",
                "email": None,
                "phone": None,
                "status": "active",
                "availability": "available",
                "is_production_admin": True,
                "stations": ["tech"],
                "primary_station": "tech",
            }
            async with AsyncClient(transport=ASGITransport(app), base_url="https://test") as system:
                await system.post("/api/production/auth/login", json={"code": admin_code})
                created = await system.post("/api/production/admin/employees", json=payload)
                assert created.status_code == 200, created.text
                employee_id = created.json()["employee"]["id"]
                code = created.json()["code"]
                assert len(code) == 6 and code.startswith("0")
                assert created.json()["employee"]["is_production_admin"] is True

                listed = await system.get(f"/api/production/admin/employees?q={employee_id}")
                assert listed.json()["items"][0]["is_production_admin"] is True
                filtered = await system.get("/api/production/admin/employees?station=manager")
                assert [item["id"] for item in filtered.json()["items"]] == [employee_id]

            async with AsyncClient(
                transport=ASGITransport(app), base_url="https://test"
            ) as production:
                assert (
                    await production.post("/api/production/auth/login", json={"code": code})
                ).status_code == 200
                me = (await production.get("/api/production/me")).json()
                assert me["admin_scope"] == "production"
                assert me["stations"] == ["tech"]
                assert (await production.get("/api/production/admin/orders")).status_code == 200
                assert (await production.get("/api/production/admin/problems")).status_code == 200
                assert (await production.get("/api/production/admin/employees")).status_code == 403

    asyncio.run(scenario())


def test_admin_filters_employees_by_availability_and_station(tmp_path):
    async def scenario():
        async with admin_app(tmp_path) as (app, db, admin_code, _):
            async with db.session() as session:
                employee = await session.scalar(
                    select(ProductionEmployee).where(ProductionEmployee.user_id == 2)
                )
                employee.availability = "sick"
                await session.commit()
            async with AsyncClient(transport=ASGITransport(app), base_url="https://test") as client:
                await client.post("/api/production/auth/login", json={"code": admin_code})
                sick = await client.get(
                    "/api/production/admin/employees?availability=sick&station=cut"
                )
                assert sick.status_code == 200, sick.text
                assert [item["id"] for item in sick.json()["items"]] == [2]
                assert (
                    await client.get("/api/production/admin/employees?availability=unknown")
                ).status_code == 422
                assert (
                    await client.get("/api/production/admin/employees?station=unknown")
                ).status_code == 422

    asyncio.run(scenario())
