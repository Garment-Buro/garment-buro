"""Shared conversations; customer projections never contain internal inbox fields."""

from datetime import datetime, timezone

from sqlalchemy import select

from app.modules.identity.models import SecurityAuditEvent, User
from app.modules.orders.models import Order, OrderItem
from app.modules.production.inbox_models import AdminInboxItem, TicketMessage
from app.modules.production.inbox_service import (
    AdminInboxConflictError,
    AdminInboxNotFoundError,
    AdminInboxService,
)


class TicketService:
    async def item(self, session, ticket_id, *, customer_id=None, lock=False):
        query = select(AdminInboxItem).where(AdminInboxItem.id == ticket_id)
        if customer_id is not None:
            query = query.where(
                AdminInboxItem.kind == "support", AdminInboxItem.reporter_user_id == customer_id
            )
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        item = await session.scalar(query)
        if item is None:
            raise AdminInboxNotFoundError()
        return item

    @staticmethod
    def summary(item):
        return {
            key: getattr(item, key)
            for key in (
                "id",
                "subject",
                "status",
                "order_id",
                "created_at",
                "updated_at",
                "version",
            )
        }

    async def customer_list(self, session, customer_id, *, offset=0, limit=30):
        rows = list(
            await session.scalars(
                select(AdminInboxItem)
                .where(
                    AdminInboxItem.kind == "support", AdminInboxItem.reporter_user_id == customer_id
                )
                .order_by(AdminInboxItem.updated_at.desc(), AdminInboxItem.id.desc())
                .offset(offset)
                .limit(limit + 1)
            )
        )
        return {
            "items": [self.summary(x) for x in rows[:limit]],
            "next_offset": offset + limit if len(rows) > limit else None,
        }

    async def detail(self, session, item, *, admin=False, after=0):
        query = select(TicketMessage).where(
            TicketMessage.ticket_id == item.id, TicketMessage.id > after
        )
        if not admin:
            query = query.where(TicketMessage.visibility == "public")
        rows = list(await session.scalars(query.order_by(TicketMessage.id).limit(101)))
        result = self.summary(item) | {
            "message": item.message,
            "initial_author": "admin"
            if item.created_by_user_id and item.created_by_user_id != item.reporter_user_id
            else ("employee" if item.kind == "production_problem" else "customer"),
            "messages": [
                {
                    "id": x.id,
                    "body": x.body,
                    "author_role": x.author_role,
                    "visibility": x.visibility,
                    "created_at": x.created_at,
                }
                for x in rows[:100]
            ],
            "next_after": rows[99].id if len(rows) > 100 else None,
        }
        if admin:
            order = await session.get(Order, item.order_id) if item.order_id else None
            result["order"] = None
            if order:
                items = list(
                    await session.scalars(select(OrderItem).where(OrderItem.order_id == order.id))
                )
                result["order"] = {
                    "id": order.id,
                    "user_id": order.user_id,
                    "status": order.status,
                    "customer": " ".join(filter(None, [order.first_name, order.last_name])),
                    "email": order.email,
                    "phone": order.phone,
                    "items": [
                        {
                            "title": x.title_snapshot,
                            "size": x.size_snapshot,
                            "color": x.color_snapshot,
                            "quantity": x.quantity,
                        }
                        for x in items
                    ],
                }
            if item.kind == "production_problem":
                from app.modules.production.ticket_routing import routing_options

                result["routing_targets"] = await routing_options(session, item)
        return result

    async def reply(self, session, *, ticket_id, actor, payload, admin=False, employee=False):
        item = await self.item(
            session, ticket_id, customer_id=None if admin or employee else actor.id, lock=True
        )
        if item.version != payload.expected_version:
            raise AdminInboxConflictError("Тикет изменился. Обновите переписку перед отправкой")
        if not admin and payload.visibility != "public":
            raise AdminInboxConflictError("Клиенту недоступны внутренние комментарии")
        if item.kind == "support" and payload.visibility == "public":
            item.status = "in_progress" if admin else "new"
            item.resolved_at = None
        item.version += 1
        item.updated_at = datetime.now(timezone.utc)
        session.add(
            TicketMessage(
                ticket_id=item.id,
                author_user_id=actor.id,
                author_role="admin" if admin else "employee" if employee else "customer",
                visibility=payload.visibility,
                body=payload.message,
            )
        )
        session.add(
            SecurityAuditEvent(
                event_type="support.ticket_replied",
                actor_user_id=actor.id,
                subject_user_id=item.reporter_user_id,
                details={
                    "item_id": item.id,
                    "visibility": payload.visibility,
                    "version": item.version,
                },
            )
        )
        await session.flush()
        return self.summary(item)

    async def create_for_customer(self, session, *, actor, payload):
        customer_id = payload.customer_user_id
        if payload.order_id:
            order = await session.get(Order, payload.order_id)
            if order is None or order.is_demo or order.user_id is None:
                raise AdminInboxConflictError("Выберите заказ зарегистрированного клиента")
            if customer_id is not None and customer_id != order.user_id:
                raise AdminInboxConflictError("Заказ принадлежит другому клиенту")
            customer_id = order.user_id
        customer = await session.get(User, customer_id) if customer_id else None
        if customer is None or customer.status != "active":
            raise AdminInboxConflictError("Укажите действующего клиента или его заказ")
        item = await AdminInboxService().create_support_request(
            session,
            reporter=customer,
            subject=payload.subject,
            message=payload.message,
            order_id=payload.order_id,
        )
        item.created_by_user_id = actor.id
        item.updated_at = datetime.now(timezone.utc)
        item.status = "in_progress"
        item.assigned_to_user_id = actor.id
        session.add(
            SecurityAuditEvent(
                event_type="support.admin_ticket_created",
                actor_user_id=actor.id,
                subject_user_id=customer.id,
                details={"item_id": item.id, "order_id": item.order_id},
            )
        )
        await session.flush()
        return self.summary(item)
