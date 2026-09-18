from sqlalchemy import String, cast, or_, select

from app.modules.production.inbox_models import AdminInboxItem


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
        return list(
            await session.scalars(
                statement.order_by(AdminInboxItem.id.desc()).offset(offset).limit(limit + 1)
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
