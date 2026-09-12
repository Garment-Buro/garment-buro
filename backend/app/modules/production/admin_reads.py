"""Bounded administrative projections over existing source-of-truth tables."""

from datetime import datetime, timezone

from sqlalchemy import String, case, cast, func, or_, select
from sqlalchemy.orm import selectinload

from app.modules.bank_payouts.models import PartnerBankPayment
from app.modules.identity.models import Role, User, UserRole
from app.modules.orders.models import Order
from app.modules.orders.workflow_models import OrderWorkflow
from app.modules.partners.models import PartnerPayoutRequest, PartnerProfile
from app.modules.production.auth_models import ProductionCredential, ProductionEmployee


def money(value):
    return format(value or 0, ".2f")


def search(query, columns):
    if not query:
        return True
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return or_(*(cast(column, String).ilike(f"%{escaped}%", escape="\\") for column in columns))


def page(rows, limit, offset, serialize):
    return {
        "items": [serialize(row) for row in rows[:limit]],
        "next_offset": offset + limit if len(rows) > limit else None,
    }


def order_row(row):
    order, workflow_state = row
    return {
        "id": order.id,
        "is_demo": order.is_demo,
        "user_id": order.user_id,
        "name": " ".join(x for x in (order.first_name, order.last_name) if x),
        "email": order.email,
        "phone": order.phone,
        "created_at": order.created_at,
        "total": money(order.total_price),
        "status": order.status,
        "payment_status": order.payment_status,
        "workflow_state": workflow_state,
    }


class ProductionAdminReads:
    async def orders(self, session, *, q, status, limit, offset):
        state = func.coalesce(OrderWorkflow.state, Order.status)
        statement = select(Order, OrderWorkflow.state).outerjoin(
            OrderWorkflow, OrderWorkflow.order_id == Order.id
        )
        statement = statement.where(
            search(q, [Order.id, Order.email, Order.phone, Order.first_name, Order.last_name])
        )
        if status:
            statement = statement.where(state == status)
        rows = (
            await session.execute(
                statement.order_by(Order.id.desc()).offset(offset).limit(limit + 1)
            )
        ).all()
        return page(rows, limit, offset, order_row)

    async def order(self, session, order_id):
        row = (
            await session.execute(
                select(Order, OrderWorkflow.state)
                .outerjoin(OrderWorkflow, OrderWorkflow.order_id == Order.id)
                .where(Order.id == order_id)
                .options(selectinload(Order.items))
            )
        ).first()
        if row is None:
            return None
        order = row[0]
        flow = await session.scalar(select(OrderWorkflow).where(OrderWorkflow.order_id == order.id))
        return {
            **order_row(row),
            "moderation": {
                "version": flow.version,
                "state": flow.state,
                "hold_expires_at": flow.hold_expires_at,
                "decision": flow.decision,
                "attention": flow.attention_code,
            }
            if flow
            else None,
            "delivery_city": order.delivery_city,
            "delivery_address": order.delivery_address,
            "delivery_method": order.delivery_method,
            "pickup_point": order.cdek_point_code,
            "delivery_price": money(order.delivery_price),
            "items": [
                {
                    "id": x.id,
                    "title": x.title_snapshot,
                    "quantity": x.quantity,
                    "size": x.size_snapshot,
                    "color": x.color_snapshot,
                    "total": money(x.line_total),
                    "customization": x.customization_snapshot,
                }
                for x in order.items
            ],
        }

    async def employees(self, session, *, q, status, limit, offset):
        statement = (
            select(ProductionEmployee, User)
            .join(User, User.id == ProductionEmployee.user_id)
            .where(
                search(q, [User.id, User.email, User.phone, User.first_name, User.last_name]),
            )
        )
        if status:
            statement = statement.where(User.status == status)
        rows = (
            await session.execute(
                statement.order_by(User.id.desc()).offset(offset).limit(limit + 1)
            )
        ).all()
        roles = {}
        user_ids = [user.id for _, user in rows]
        if user_ids:
            for user_id, role in await session.execute(
                select(UserRole.user_id, Role.name)
                .join(Role, Role.id == UserRole.role_id)
                .where(
                    UserRole.user_id.in_(user_ids),
                    Role.name.like("production_%"),
                    Role.name != "production_admin",
                )
            ):
                roles.setdefault(user_id, []).append(role)
        active_codes = {
            user_id: updated_at
            for user_id, updated_at in await session.execute(
                select(ProductionCredential.user_id, ProductionCredential.updated_at).where(
                    ProductionCredential.user_id.in_(user_ids),
                    ProductionCredential.active.is_(True),
                )
            )
        }
        return page(
            rows,
            limit,
            offset,
            lambda row: {
                "id": row[1].id,
                "availability": row[0].availability,
                "first_name": row[1].first_name or "",
                "last_name": row[1].last_name or "",
                "name": " ".join(x for x in (row[1].first_name, row[1].last_name) if x),
                "email": row[1].email,
                "phone": row[1].phone,
                "status": row[1].status,
                "created_at": row[0].created_at,
                "stations": sorted(
                    role.removeprefix("production_") for role in roles.get(row[1].id, [])
                ),
                "primary_station": row[0].primary_station,
                "code_active": row[1].id in active_codes,
                "code_updated_at": active_codes.get(row[1].id),
            },
        )

    async def users(self, session, *, q, status, limit, offset):
        """Compatibility alias: terminal users are production employees."""
        return await self.employees(session, q=q, status=status, limit=limit, offset=offset)

    def clients_query(self):
        # Registered accounts never merge by contact. Unidentified guests stay distinct.
        key = case(
            (Order.user_id.is_not(None), "user:" + cast(Order.user_id, String)),
            (
                func.nullif(Order.email_normalized, "").is_not(None),
                "email:" + Order.email_normalized,
            ),
            (func.nullif(Order.phone, "").is_not(None), "phone:" + Order.phone),
            else_="order:" + cast(Order.id, String),
        )
        return (
            select(
                key.label("key"),
                func.max(Order.user_id).label("user_id"),
                func.max(Order.id).label("last_order_id"),
                func.max(Order.created_at).label("last_order_at"),
                func.count(Order.id).label("orders_count"),
                func.sum(Order.total_price).label("orders_total"),
                func.sum(case((Order.payment_status == "paid", Order.total_price), else_=0)).label(
                    "paid_orders_total"
                ),
            )
            .where(Order.is_demo.is_(False))
            .group_by(key)
            .subquery()
        )

    async def clients(self, session, *, q, limit, offset):
        clients = self.clients_query()
        rows = (
            (
                await session.execute(
                    select(clients, Order.first_name, Order.last_name, Order.email, Order.phone)
                    .join(Order, Order.id == clients.c.last_order_id)
                    .where(
                        search(
                            q,
                            [
                                clients.c.user_id,
                                Order.first_name,
                                Order.last_name,
                                Order.email,
                                Order.phone,
                            ],
                        )
                    )
                    .order_by(clients.c.last_order_id.desc())
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            .mappings()
            .all()
        )
        return page(
            rows,
            limit,
            offset,
            lambda r: {
                "key": r["key"],
                "user_id": r["user_id"],
                "last_order_id": r["last_order_id"],
                "name": " ".join(x for x in (r["first_name"], r["last_name"]) if x),
                "email": r["email"],
                "phone": r["phone"],
                "last_order_at": r["last_order_at"],
                "orders_count": r["orders_count"],
                "orders_total": money(r["orders_total"]),
                "paid_orders_total": money(r["paid_orders_total"]),
            },
        )

    async def payouts(self, session, *, q, status, limit, offset):
        statement = (
            select(PartnerPayoutRequest, PartnerProfile.display_name, PartnerBankPayment.state)
            .join(PartnerProfile, PartnerProfile.id == PartnerPayoutRequest.partner_id)
            .outerjoin(PartnerBankPayment, PartnerBankPayment.payout_id == PartnerPayoutRequest.id)
        )
        statement = statement.where(
            search(q, [PartnerPayoutRequest.id, PartnerProfile.display_name, PartnerProfile.code])
        )
        if status:
            statement = statement.where(PartnerPayoutRequest.status == status)
        rows = (
            await session.execute(
                statement.order_by(PartnerPayoutRequest.id.desc()).offset(offset).limit(limit + 1)
            )
        ).all()
        return page(
            rows,
            limit,
            offset,
            lambda r: {
                "id": r[0].id,
                "partner_id": r[0].partner_id,
                "partner": r[1],
                "amount": money(r[0].amount),
                "status": r[0].status,
                "bank_state": r[2],
                "note": r[0].note,
                "created_at": r[0].created_at,
                "reviewed_at": r[0].reviewed_at,
                "paid_at": r[0].paid_at,
            },
        )

    async def stats(self, session):
        count, total, paid = (
            await session.execute(
                select(
                    func.count(Order.id),
                    func.sum(Order.total_price),
                    func.sum(case((Order.payment_status == "paid", Order.total_price), else_=0)),
                ).where(Order.is_demo.is_(False))
            )
        ).one()
        payout_states = [
            {"status": status, "count": n, "amount": money(amount)}
            for status, n, amount in await session.execute(
                select(
                    PartnerPayoutRequest.status, func.count(), func.sum(PartnerPayoutRequest.amount)
                ).group_by(PartnerPayoutRequest.status)
            )
        ]
        state = func.coalesce(OrderWorkflow.state, Order.status)
        order_states = [
            {"status": status, "count": n}
            for status, n in await session.execute(
                select(state, func.count(Order.id))
                .outerjoin(OrderWorkflow, OrderWorkflow.order_id == Order.id)
                .where(Order.is_demo.is_(False))
                .group_by(state)
            )
        ]
        return {
            "as_of": datetime.now(timezone.utc),
            "orders_count": count,
            "orders_total": money(total),
            "paid_orders_total": money(paid),
            "employees_count": await session.scalar(select(func.count(ProductionEmployee.id))),
            "clients_count": await session.scalar(
                select(func.count()).select_from(self.clients_query())
            ),
            "order_states": order_states,
            "payout_states": payout_states,
        }
