from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.modules.identity.models import SecurityAuditEvent, User
from app.modules.orders.models import Order
from app.modules.production.inbox_models import (
    AdminInboxItem,
    AdminInboxKind,
    AdminInboxStatus,
    TicketMessage,
)
from app.modules.production.inbox_repository import AdminInboxRepository
from app.modules.production.inbox_schemas import AdminInboxPage, AdminInboxRead, AdminInboxUpdate
from app.modules.production.security import can_administer


class AdminInboxNotFoundError(LookupError):
    pass


class AdminInboxConflictError(ValueError):
    pass


class SupportOrderNotFoundError(LookupError):
    pass


class SupportRateLimitError(ValueError):
    pass


class AdminInboxService:
    def __init__(self, repository: AdminInboxRepository | None = None):
        self.repository = repository or AdminInboxRepository()

    async def list(self, session, **params) -> AdminInboxPage:
        rows = await self.repository.list(session, **params)
        limit = params["limit"]
        offset = params["offset"]
        return AdminInboxPage(
            items=[AdminInboxRead.model_validate(item) for item in rows[:limit]],
            next_offset=offset + limit if len(rows) > limit else None,
        )

    async def get(self, session, *, item_id: int, kind: str) -> AdminInboxRead:
        item = await self.repository.get(session, item_id=item_id, kind=kind)
        if item is None:
            raise AdminInboxNotFoundError()
        return AdminInboxRead.model_validate(item)

    async def create_production_problem(
        self,
        session,
        *,
        message: str,
        reporter_user_id: int,
        order_id: int,
        project_id: int,
        production_unit_id: int | None,
        station: str,
    ) -> AdminInboxItem:
        reporter = await session.get(User, reporter_user_id)
        reporter_name = (
            " ".join(part for part in (reporter.first_name, reporter.last_name) if part)
            if reporter
            else None
        )
        item = AdminInboxItem(
            kind=AdminInboxKind.PRODUCTION_PROBLEM.value,
            status=AdminInboxStatus.NEW.value,
            priority="normal",
            subject=(
                f"Проблема с изделием №{production_unit_id}"
                if production_unit_id is not None
                else f"Заказ №{order_id} отправлен на модерацию"
            ),
            message=message,
            reporter_user_id=reporter_user_id,
            reporter_name=reporter_name or None,
            reporter_email=reporter.email if reporter else None,
            reporter_phone=reporter.phone if reporter else None,
            order_id=order_id,
            project_id=project_id,
            production_unit_id=production_unit_id,
            station=station,
        )
        session.add(item)
        await session.flush()
        session.add(
            SecurityAuditEvent(
                event_type="production.admin_inbox_created",
                actor_user_id=reporter_user_id,
                subject_user_id=reporter_user_id,
                details={
                    "item_id": item.id,
                    "kind": item.kind,
                    "project_id": project_id,
                    "production_unit_id": production_unit_id,
                    "station": station,
                },
            )
        )
        return item

    async def create_support_request(
        self,
        session,
        *,
        reporter: User,
        subject: str,
        message: str,
        order_id: int | None,
    ) -> AdminInboxItem:
        if order_id is not None:
            owned_order = await session.scalar(
                select(Order.id).where(Order.id == order_id, Order.user_id == reporter.id)
            )
            if owned_order is None:
                raise SupportOrderNotFoundError()
        recent_count = await session.scalar(
            select(func.count(AdminInboxItem.id)).where(
                AdminInboxItem.kind == AdminInboxKind.SUPPORT.value,
                AdminInboxItem.reporter_user_id == reporter.id,
                AdminInboxItem.created_at >= datetime.now(timezone.utc) - timedelta(hours=1),
            )
        )
        if (recent_count or 0) >= 10:
            raise SupportRateLimitError("Слишком много обращений. Повторите позже")
        reporter_name = " ".join(part for part in (reporter.first_name, reporter.last_name) if part)
        item = AdminInboxItem(
            kind=AdminInboxKind.SUPPORT.value,
            status=AdminInboxStatus.NEW.value,
            priority="normal",
            subject=subject,
            message=message,
            reporter_user_id=reporter.id,
            reporter_name=reporter_name or None,
            reporter_email=reporter.email,
            reporter_phone=reporter.phone,
            order_id=order_id,
        )
        session.add(item)
        await session.flush()
        session.add(
            SecurityAuditEvent(
                event_type="support.request_created",
                actor_user_id=reporter.id,
                subject_user_id=reporter.id,
                details={"item_id": item.id, "order_id": order_id},
            )
        )
        return item

    async def resolve_production_problem(
        self,
        session,
        *,
        item_id: int | None,
        actor_user_id: int,
        note: str | None = None,
    ) -> None:
        if item_id is None:
            return
        item = await self.repository.get(
            session,
            item_id=item_id,
            kind=AdminInboxKind.PRODUCTION_PROBLEM.value,
            lock=True,
        )
        if item is None or item.status in {
            AdminInboxStatus.RESOLVED.value,
            AdminInboxStatus.CLOSED.value,
        }:
            return
        previous_status = item.status
        item.status = AdminInboxStatus.RESOLVED.value
        item.resolved_at = datetime.now(timezone.utc)
        item.version += 1
        session.add(
            TicketMessage(
                ticket_id=item.id,
                author_user_id=actor_user_id,
                author_role="system",
                visibility="public",
                body=f"Проблема устранена на производстве. {note or ''}".strip(),
            )
        )
        session.add(
            SecurityAuditEvent(
                event_type="production.admin_inbox_resolved_from_floor",
                actor_user_id=actor_user_id,
                subject_user_id=item.reporter_user_id,
                details={
                    "item_id": item.id,
                    "from_status": previous_status,
                    "to_status": item.status,
                    "version": item.version,
                },
            )
        )
        await session.flush()

    async def update(
        self,
        session,
        *,
        item_id: int,
        kind: str,
        payload: AdminInboxUpdate,
        actor_user_id: int,
    ) -> AdminInboxRead:
        item = await self.repository.get(session, item_id=item_id, kind=kind, lock=True)
        if item is None:
            raise AdminInboxNotFoundError()
        if item.version != payload.expected_version:
            raise AdminInboxConflictError("Запись уже изменена. Обновите карточку")
        if kind == "production_problem":
            from app.modules.production.models import ProductionWorkItem

            active_issue = await session.scalar(
                select(ProductionWorkItem.id).where(
                    ProductionWorkItem.problem_inbox_item_id == item.id,
                    ProductionWorkItem.issue.is_not(None),
                )
            )
            if active_issue and payload.status in {"resolved", "closed"}:
                raise AdminInboxConflictError("Выберите участок и сохраните решение по изделию")
            if (
                not active_issue
                and item.status in {"resolved", "closed"}
                and payload.status in {"new", "in_progress"}
            ):
                raise AdminInboxConflictError(
                    "Для новой остановки изделия сотрудник должен сообщить о новой проблеме"
                )
        if payload.assigned_to_user_id is not None:
            assignee = await session.scalar(
                select(User).where(
                    User.id == payload.assigned_to_user_id,
                    User.status == "active",
                )
            )
            if assignee is None or not await can_administer(session, assignee.id):
                raise AdminInboxConflictError("Ответственный администратор не найден")

        previous_status = item.status
        if item.admin_note != payload.admin_note and payload.admin_note:
            session.add(
                TicketMessage(
                    ticket_id=item.id,
                    author_user_id=actor_user_id,
                    author_role="admin",
                    visibility="internal",
                    body=payload.admin_note,
                )
            )
        if previous_status != payload.status:
            labels = {
                "new": "Новое",
                "in_progress": "В работе",
                "resolved": "Решено",
                "closed": "Закрыто",
            }
            session.add(
                TicketMessage(
                    ticket_id=item.id,
                    author_user_id=actor_user_id,
                    author_role="system",
                    visibility="public",
                    body=f"Статус: {labels[payload.status]}",
                )
            )
        item.status = payload.status
        item.priority = payload.priority
        item.assigned_to_user_id = payload.assigned_to_user_id
        item.admin_note = payload.admin_note
        item.version += 1
        if payload.status in {
            AdminInboxStatus.RESOLVED.value,
            AdminInboxStatus.CLOSED.value,
        }:
            item.resolved_at = item.resolved_at or datetime.now(timezone.utc)
        else:
            item.resolved_at = None
        session.add(
            SecurityAuditEvent(
                event_type="production.admin_inbox_updated",
                actor_user_id=actor_user_id,
                subject_user_id=item.reporter_user_id,
                details={
                    "item_id": item.id,
                    "kind": item.kind,
                    "from_status": previous_status,
                    "to_status": item.status,
                    "priority": item.priority,
                    "assigned_to_user_id": item.assigned_to_user_id,
                    "version": item.version,
                },
            )
        )
        await session.flush()
        await session.refresh(item)
        return AdminInboxRead.model_validate(item)
