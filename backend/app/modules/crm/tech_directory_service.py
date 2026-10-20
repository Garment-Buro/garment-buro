from app.modules.crm.directory_service import continuation, position
from app.modules.crm.tech_directory_repository import TechDirectoryRepository
from app.modules.crm.tech_directory_schemas import (
    TechCardEditorSource,
    TechCardModelPage,
    TechCardPage,
)


class TechDirectoryService:
    repository = TechDirectoryRepository()

    async def page(self, session, kind, query):
        after_id, after_value = position(query, kind)
        read = self.repository.cards if kind == "tech-cards" else self.repository.models
        rows = await read(session, query, after_id=after_id, after_value=after_value)
        schema = TechCardPage if kind == "tech-cards" else TechCardModelPage
        return schema(items=rows[: query.limit], next_cursor=continuation(rows, query, kind))

    async def editor(self, session, card_id):
        row = await self.repository.editor(session, card_id)
        return TechCardEditorSource.model_validate(row) if row is not None else None
