"""Scalar client projections; history pages never hydrate order or ticket bodies."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, case, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import User
from app.modules.orders.models import Order
from app.modules.orders.workflow_models import OrderWorkflow
from app.modules.production.inbox_models import AdminInboxItem


@dataclass(frozen=True)
class ClientScope:
    kind: str
    value: str | int

    @classmethod
    def parse(cls, key: str):
        kind, separator, value = key.partition(":")
        if not separator or not value or "\x00" in value:
            raise ValueError("Некорректный идентификатор клиента")
        if kind in {"user", "order"}:
            if not value.isascii() or not value.isdigit() or len(value) > 10:
                raise ValueError("Некорректный идентификатор клиента")
            value = int(value)
            if not 1 <= value <= 2_147_483_647:
                raise ValueError("Некорректный идентификатор клиента")
        elif kind not in {"email", "phone"}:
            raise ValueError("Некорректный идентификатор клиента")
        return cls(kind, value)

    def orders(self):
        if self.kind == "user":
            identity = Order.user_id == self.value
        elif self.kind == "email":
            identity = and_(Order.user_id.is_(None), Order.email_normalized == self.value)
        elif self.kind == "phone":
            identity = and_(
                Order.user_id.is_(None),
                func.nullif(Order.email_normalized, "").is_(None),
                func.coalesce(Order.buyer_phone, Order.phone) == self.value,
            )
        else:
            identity = Order.id == self.value
        return and_(Order.is_demo.is_(False), identity)

    def tickets(self):
        if self.kind == "user":
            direct = AdminInboxItem.reporter_user_id == self.value
        elif self.kind == "email":
            direct = and_(
                AdminInboxItem.reporter_user_id.is_(None),
                func.lower(AdminInboxItem.reporter_email) == str(self.value).lower(),
            )
        elif self.kind == "phone":
            direct = and_(
                AdminInboxItem.reporter_user_id.is_(None),
                AdminInboxItem.reporter_email.is_(None),
                AdminInboxItem.reporter_phone == self.value,
            )
        else:
            direct = AdminInboxItem.order_id == self.value
        # All matching orders participate, not just those on the visible history page.
        orders = select(Order.id).where(self.orders()).correlate(None)
        return and_(
            AdminInboxItem.kind == "support", or_(direct, AdminInboxItem.order_id.in_(orders))
        )


class ProductionClientRepository:
    @staticmethod
    async def latest(session: AsyncSession, scope: ClientScope):
        return (
            (
                await session.execute(
                    select(
                        Order.id,
                        Order.buyer_name,
                        Order.first_name,
                        Order.last_name,
                        Order.email,
                        Order.buyer_phone,
                        Order.phone,
                        Order.patronymic,
                        Order.recipient_email,
                        Order.delivery_city,
                        Order.delivery_address,
                        Order.delivery_method,
                        Order.cdek_point_code,
                    )
                    .where(scope.orders())
                    .order_by(Order.created_at.desc(), Order.id.desc())
                    .limit(1)
                )
            )
            .mappings()
            .first()
        )

    @staticmethod
    async def account(session: AsyncSession, user_id: int):
        return (
            (
                await session.execute(
                    select(
                        User.id,
                        User.email,
                        User.phone,
                        User.username,
                        User.created_at.label("registered_at"),
                        User.email_verified_at,
                        User.gender,
                        User.birth_date,
                        User.height_cm,
                        User.weight_kg,
                    ).where(User.id == user_id)
                )
            )
            .mappings()
            .first()
        )

    @staticmethod
    async def totals(session: AsyncSession, scope: ClientScope):
        tickets_count = (
            select(func.count(AdminInboxItem.id)).where(scope.tickets()).scalar_subquery()
        )
        return (
            (
                await session.execute(
                    select(
                        func.count(Order.id).label("orders_count"),
                        func.coalesce(func.sum(Order.total_price), 0).label("orders_total"),
                        func.coalesce(
                            func.sum(
                                case((Order.payment_status == "paid", Order.total_price), else_=0)
                            ),
                            0,
                        ).label("paid_orders_total"),
                        tickets_count.label("tickets_count"),
                    ).where(scope.orders())
                )
            )
            .mappings()
            .one()
        )

    @staticmethod
    async def orders(
        session: AsyncSession, scope: ClientScope, *, limit: int, after: tuple[datetime, int] | None
    ):
        statement = (
            select(
                Order.id,
                Order.created_at,
                Order.total_price,
                Order.status,
                Order.payment_status,
                OrderWorkflow.state.label("workflow_state"),
                Order.delivery_city,
                Order.delivery_method,
                Order.payment_method,
            )
            .outerjoin(OrderWorkflow, OrderWorkflow.order_id == Order.id)
            .where(scope.orders())
        )
        if after is not None:
            statement = statement.where(tuple_(Order.created_at, Order.id) < after)
        return list(
            (
                await session.execute(
                    statement.order_by(Order.created_at.desc(), Order.id.desc()).limit(limit)
                )
            ).mappings()
        )

    @staticmethod
    async def tickets(
        session: AsyncSession, scope: ClientScope, *, limit: int, after: tuple[datetime, int] | None
    ):
        statement = select(
            AdminInboxItem.id,
            AdminInboxItem.subject,
            AdminInboxItem.status,
            AdminInboxItem.priority,
            AdminInboxItem.order_id,
            AdminInboxItem.created_at,
            AdminInboxItem.updated_at,
        ).where(scope.tickets())
        if after is not None:
            statement = statement.where(
                tuple_(AdminInboxItem.updated_at, AdminInboxItem.id) < after
            )
        return list(
            (
                await session.execute(
                    statement.order_by(
                        AdminInboxItem.updated_at.desc(), AdminInboxItem.id.desc()
                    ).limit(limit)
                )
            ).mappings()
        )
