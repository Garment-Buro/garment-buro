from sqlalchemy import String, case, cast, func, or_, select

from app.modules.production.inbox_models import AdminInboxItem, TicketMessage


def _search(query: str):
    if not query:
        return True
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    return or_(
        cast(AdminInboxItem.id, String).ilike(pattern, escape="\\"),
        AdminInboxItem.subject.ilike(pattern, escape="\\"),
        AdminInboxItem.message.ilike(pattern, escape="\\"),
        AdminInboxItem.reporter_name.ilike(pattern, escape="\\"),
        AdminInboxItem.reporter_email.ilike(pattern, escape="\\"),
        AdminInboxItem.reporter_phone.ilike(pattern, escape="\\"),
        cast(AdminInboxItem.order_id, String).ilike(pattern, escape="\\"),
        cast(AdminInboxItem.project_id, String).ilike(pattern, escape="\\"),
        cast(AdminInboxItem.production_unit_id, String).ilike(pattern, escape="\\"),
        AdminInboxItem.station.ilike(pattern, escape="\\"),
        select(TicketMessage.id)
        .where(
            TicketMessage.ticket_id == AdminInboxItem.id,
            TicketMessage.body.ilike(pattern, escape="\\"),
        )
        .exists(),
    )


class AdminInboxRepository:
    async def list(
        self,
        session,
        *,
        kind: str,
        q: str,
        status: str,
        priority: str,
        sort: str,
        direction: str,
        limit: int,
        offset: int,
    ):
        statement = select(AdminInboxItem).where(
            AdminInboxItem.kind == kind,
            _search(q.strip()),
        )
        if status:
            statement = statement.where(AdminInboxItem.status == status)
        if priority:
            statement = statement.where(AdminInboxItem.priority == priority)
        fields = {
            "created_at": AdminInboxItem.created_at,
            "updated_at": AdminInboxItem.updated_at,
            "priority": case(
                (AdminInboxItem.priority == "critical", 4),
                (AdminInboxItem.priority == "high", 3),
                (AdminInboxItem.priority == "normal", 2),
                else_=1,
            ),
            "status": case(
                (AdminInboxItem.status == "new", 1),
                (AdminInboxItem.status == "in_progress", 2),
                (AdminInboxItem.status == "resolved", 3),
                else_=4,
            ),
            "reporter": func.lower(
                func.coalesce(
                    AdminInboxItem.reporter_name,
                    AdminInboxItem.reporter_email,
                    AdminInboxItem.reporter_phone,
                    "",
                )
            ),
        }
        ordered = fields[sort].asc() if direction == "asc" else fields[sort].desc()
        tie_breaker = AdminInboxItem.id.asc() if direction == "asc" else AdminInboxItem.id.desc()
        return list(
            await session.scalars(
                statement.order_by(ordered, tie_breaker).offset(offset).limit(limit + 1)
            )
        )

    async def get(self, session, *, item_id: int, kind: str, lock: bool = False):
        statement = select(AdminInboxItem).where(
            AdminInboxItem.id == item_id,
            AdminInboxItem.kind == kind,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)
