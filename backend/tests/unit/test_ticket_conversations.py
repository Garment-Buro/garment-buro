import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.modules.identity.models import User
from app.modules.identity.router import get_current_identity_user
from app.modules.orders.models import Order
from app.modules.production.inbox_models import AdminInboxItem, TicketMessage
from app.modules.production.inbox_service import AdminInboxConflictError, AdminInboxService
from app.modules.production.models import ProductionBag, ProductionEvent, ProductionWorkItem
from app.modules.production.read_service import ProductionReadService
from app.modules.production.support_router import router as support_router
from app.modules.production.ticket_routing import route_ticket, routing_options
from app.modules.production.ticket_schemas import TicketRoute
from app.modules.production.ticket_service import TicketService
from tests.unit.test_production_admin import admin_app
from tests.unit.test_production_terminal import execute, setup
from tests.unit.test_production_unit_flow import workers


def test_customer_conversation_ownership_internal_notes_reopening_and_admin_initiation(tmp_path):
    async def scenario():
        async with admin_app(tmp_path) as (app, db, admin_code, cutter_code):
            app.include_router(support_router)
            async with db.session() as session:
                customer = await session.get(User, 3)
                other = await session.get(User, 2)
                order = await session.get(Order, 1)
                order.user_id = customer.id
                await session.commit()
                await session.refresh(customer)
                await session.refresh(other)
            app.dependency_overrides[get_current_identity_user] = lambda: customer
            async with AsyncClient(transport=ASGITransport(app), base_url="https://test") as client:
                await client.post("/api/production/auth/login", json={"code": admin_code})
                created = await client.post(
                    "/api/production/admin/tickets",
                    json={
                        "order_id": 1,
                        "subject": "Уточнение размеров",
                        "message": "Подтвердите длину рукава",
                    },
                )
                assert created.status_code == 201, created.text
                ticket_id = created.json()["id"]
                url = f"/api/support/{ticket_id}"
                admin_url = f"/api/production/admin/tickets/{ticket_id}"
                detail = (await client.get(url)).json()
                assert detail["initial_author"] == "admin"
                assert detail["message"] == "Подтвердите длину рукава"
                assert (await client.get(url)).headers["cache-control"] == "no-store"
                assert ticket_id in [
                    x["id"] for x in (await client.get("/api/support")).json()["items"]
                ]
                internal = await client.post(
                    admin_url + "/messages",
                    json={
                        "expected_version": 1,
                        "message": "Внутренние данные цеха",
                        "visibility": "internal",
                    },
                )
                assert internal.status_code == 200, internal.text
                detail = (await client.get(url)).json()
                assert detail["messages"] == []
                assert (
                    "order" not in detail
                    and "admin_note" not in detail
                    and "reporter_email" not in detail
                )
                assert len((await client.get(admin_url)).json()["messages"]) == 1
                assert (
                    await client.post(
                        url + "/messages",
                        json={
                            "expected_version": 2,
                            "message": "Скрыть ответ",
                            "visibility": "internal",
                        },
                    )
                ).status_code == 409
                answered = await client.post(
                    url + "/messages", json={"expected_version": 2, "message": "Рукав 65 см"}
                )
                assert answered.status_code == 200, answered.text
                assert answered.json()["status"] == "new"
                assert (
                    await client.post(
                        url + "/messages", json={"expected_version": 2, "message": "Дубль"}
                    )
                ).status_code == 409
                closed = await client.patch(
                    f"/api/production/admin/support/{ticket_id}",
                    json={
                        "expected_version": 3,
                        "status": "closed",
                        "priority": "normal",
                        "admin_note": "Служебная заметка",
                    },
                )
                assert closed.status_code == 200, closed.text
                reopened = await client.post(
                    url + "/messages", json={"expected_version": 4, "message": "Ещё один вопрос"}
                )
                assert reopened.status_code == 200
                assert reopened.json()["status"] == "new"
                assert "Служебная заметка" not in (await client.get(url)).text
                assert (
                    await client.post(
                        "/api/production/admin/tickets",
                        json={
                            "order_id": 1,
                            "customer_user_id": 2,
                            "message": "Чужой клиент",
                        },
                    )
                ).status_code == 409
                app.dependency_overrides[get_current_identity_user] = lambda: other
                assert (await client.get(url)).status_code == 404
                assert (
                    await client.post(
                        url + "/messages", json={"expected_version": 5, "message": "Чужой ответ"}
                    )
                ).status_code == 404
                assert (await client.get("/api/support/2")).status_code == 404  # production issue
                await client.post("/api/production/auth/login", json={"code": cutter_code})
                assert (await client.get(admin_url)).status_code == 403
                floor_url = "/api/production/projects/1/tickets/2"
                assert (await client.get(floor_url)).status_code == 404
                assert (await client.get("/api/production/projects/1/tickets/1")).status_code == 404
                assert (
                    await client.get("/api/production/projects/999/tickets/2")
                ).status_code == 404
                assert (
                    await client.post(
                        floor_url + "/messages",
                        json={
                            "expected_version": 1,
                            "message": "Материал найден на складе",
                        },
                    )
                ).status_code == 404
                assert (
                    await client.post(
                        admin_url + "/route",
                        json={"expected_version": 5, "target": "cut", "comment": "Обойти доступ"},
                    )
                ).status_code == 403

    asyncio.run(scenario())


def test_production_ticket_before_planning_and_atomic_routing(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, service, spec):
            people = await workers(db)
            await execute(db, service, "report_issue", unit_id=1, note="Нет размеров в заказе")
            async with db.session() as session:
                ticket = await session.scalar(select(AdminInboxItem))
                actor = await session.get(User, 1)
                assert [x["value"] for x in await routing_options(session, ticket)] == ["resume"]
                await route_ticket(
                    session,
                    ticket.id,
                    actor,
                    TicketRoute(expected_version=1, target="resume", comment="Размеры уточнены"),
                )
                await session.commit()
            await execute(db, service, "plan", unit_id=1, specification=spec)
            await execute(db, service, "confirm_documents", unit_id=1)
            await execute(db, service, "approve_order")
            await execute(db, service, "approve_order", actor=people["dtf"])
            await execute(db, service, "release")
            await execute(db, service, "issue_unit_label", actor=2, unit_id=1)
            await execute(
                db, service, "complete_stage", actor=2, unit_id=1, stage="cut", note="Готово"
            )
            await execute(
                db, service, "report_issue", actor=people["kit"], unit_id=1, note="Повреждён крой"
            )
            async with db.session() as session:
                ticket = await session.scalar(
                    select(AdminInboxItem).order_by(AdminInboxItem.id.desc())
                )
                ticket_id = ticket.id
                actor = await session.get(User, 1)
                bag = await session.scalar(select(ProductionBag))
                version = bag.version
                with pytest.raises(AdminInboxConflictError):
                    await route_ticket(
                        session,
                        ticket.id,
                        actor,
                        TicketRoute(expected_version=1, target="packing", comment="Пропустить цех"),
                    )
                await session.rollback()
            async with db.session() as session:
                actor = await session.get(User, 1)
                await route_ticket(
                    session,
                    ticket_id,
                    actor,
                    TicketRoute(
                        expected_version=1, target="cut", comment="Перекроить деталь спинки"
                    ),
                )
                await session.commit()
            async with db.session() as session:
                work = await session.scalar(select(ProductionWorkItem))
                bag = await session.scalar(select(ProductionBag))
                ticket = await session.get(AdminInboxItem, ticket_id)
                assert work.lane == "cut" and work.issue is None
                assert work.component_checks == {} and not work.dtf_inserted
                assert ticket.status == "resolved" and ticket.version == 2
                assert bag.version == version + 1
                event = await session.scalar(
                    select(ProductionEvent)
                    .where(ProductionEvent.action == "ticket_routed")
                    .order_by(ProductionEvent.id.desc())
                )
                assert event.evidence["command"]["note"] == "Перекроить деталь спинки"
                detail = await ProductionReadService().detail(
                    session, project_id=1, stations=["cut"]
                )
                assert "ticket_id" not in detail["units"][0]
                assert detail["events"] == []
                history = await ProductionReadService().detail(
                    session, project_id=1, stations=["tech"]
                )
                assert history["events"][0]["note"] == "Перекроить деталь спинки"
                with pytest.raises(AdminInboxConflictError):
                    await route_ticket(
                        session,
                        ticket_id,
                        await session.get(User, 1),
                        TicketRoute(expected_version=1, target="cut", comment="Повтор"),
                    )

    asyncio.run(scenario())


def test_messages_are_paginated_and_internal_notes_do_not_leak(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, _, _):
            async with db.session() as session:
                customer = await session.get(User, 3)
                ticket = await AdminInboxService().create_support_request(
                    session,
                    reporter=customer,
                    subject="Вопрос",
                    message="Первое сообщение",
                    order_id=None,
                )
                for i in range(105):
                    session.add(
                        TicketMessage(
                            ticket_id=ticket.id,
                            author_user_id=1,
                            author_role="admin",
                            visibility="public",
                            body=f"Ответ {i}",
                        )
                    )
                session.add(
                    TicketMessage(
                        ticket_id=ticket.id,
                        author_user_id=1,
                        author_role="admin",
                        visibility="internal",
                        body="Секретная заметка",
                    )
                )
                await session.flush()
                first = await TicketService().detail(session, ticket)
                assert len(first["messages"]) == 100
                second = await TicketService().detail(session, ticket, after=first["next_after"])
                assert len(second["messages"]) == 5 and second["next_after"] is None
                assert not {x["id"] for x in first["messages"]} & {
                    x["id"] for x in second["messages"]
                }

    asyncio.run(scenario())


def test_packing_rework_resets_quality_status_and_preserves_sibling(tmp_path):
    async def scenario():
        async with setup(tmp_path, quantity=2) as (db, service, spec):
            people = await workers(db)
            spec = spec | {
                "route": ["sewing", "qc", "packing"],
                "pattern_file_ids": [],
                "print_file_ids": [],
            }
            for unit_id in (1, 2):
                await execute(db, service, "plan", unit_id=unit_id, specification=spec)
                await execute(db, service, "confirm_documents", unit_id=unit_id)
            await execute(db, service, "approve_order")
            await execute(db, service, "approve_order", actor=people["dtf"])
            await execute(db, service, "release")
            for unit_id in (1, 2):
                await execute(db, service, "issue_unit_label", actor=2, unit_id=unit_id)
                await execute(
                    db,
                    service,
                    "complete_stage",
                    actor=2,
                    unit_id=unit_id,
                    stage="cut",
                    note="QR наклеен",
                )
            await execute(
                db,
                service,
                "check_component",
                actor=people["kit"],
                unit_id=1,
                component_key="fabric",
                checked=True,
            )
            await execute(db, service, "send_unit", actor=people["kit"], unit_id=1)
            await execute(
                db,
                service,
                "complete_workshop",
                actor=people["workshop"],
                unit_id=1,
                quality_confirmed=[0, 1],
            )
            await execute(
                db, service, "report_issue", actor=people["packing"], unit_id=1, note="Неровный шов"
            )
            async with db.session() as session:
                ticket = await session.scalar(select(AdminInboxItem))
                actor = await session.get(User, 1)
                await route_ticket(
                    session,
                    ticket.id,
                    actor,
                    TicketRoute(
                        expected_version=1,
                        target="workshop",
                        comment="Исправить шов и повторить ОТК",
                    ),
                )
                await session.commit()
            async with db.session() as session:
                detail = await ProductionReadService().detail(
                    session, project_id=1, stations=["tech"]
                )
                assert detail["units"][0]["lane"] == "workshop"
                assert detail["units"][0]["crm_status"] == "in_progress"
                assert detail["units"][1]["lane"] == "kit"
                assert detail["units"][1]["issue"] is None
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
            await execute(
                db,
                service,
                "report_issue",
                actor=people["packing"],
                unit_id=1,
                note="Повреждена упаковка",
            )
            async with db.session() as session:
                ticket = await session.scalar(
                    select(AdminInboxItem).order_by(AdminInboxItem.id.desc())
                )
                assert [x["value"] for x in await routing_options(session, ticket)] == ["resume"]

    asyncio.run(scenario())
