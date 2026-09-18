import asyncio

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.modules.identity.models import SecurityAuditEvent, User
from app.modules.identity.router import get_current_identity_user
from app.modules.orders.models import Order
from app.modules.production.inbox_models import AdminInboxItem
from app.modules.production.support_router import router
from tests.unit.test_production_terminal import setup


def test_authenticated_user_can_create_support_request_for_owned_order(tmp_path):
    async def scenario():
        async with setup(tmp_path) as (db, _, _):
            async with db.session() as session:
                user = await session.get(User, 3)
                user.first_name = "Покупатель"
                user.phone = "+79990000001"
                order = await session.get(Order, 1)
                order.user_id = user.id
                await session.commit()
                await session.refresh(user)

            app = FastAPI()
            app.state.database = db
            app.include_router(router)
            app.dependency_overrides[get_current_identity_user] = lambda: user
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="https://test"
            ) as client:
                response = await client.post(
                    "/api/support",
                    json={"message": "Не отображается статус заказа", "order_id": 1},
                )
                assert response.status_code == 201, response.text
                assert response.json()["status"] == "new"
                hidden_order = await client.post(
                    "/api/support",
                    json={"message": "Чужой заказ", "order_id": 999},
                )
                assert hidden_order.status_code == 404

            async with db.session() as session:
                item = await session.scalar(select(AdminInboxItem))
                assert item.kind == "support"
                assert item.subject == "Обращение пользователя"
                assert item.reporter_user_id == user.id
                assert item.reporter_name == "Покупатель"
                assert item.reporter_phone == "+79990000001"
                assert item.order_id == 1
                audit = await session.scalar(
                    select(SecurityAuditEvent).where(
                        SecurityAuditEvent.event_type == "support.request_created"
                    )
                )
                assert audit.details["item_id"] == item.id

    asyncio.run(scenario())
