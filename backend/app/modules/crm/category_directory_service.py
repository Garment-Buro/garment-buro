from app.modules.catalog.schemas import ProductCategoryResponse
from app.modules.crm.category_directory_repository import CategoryDirectoryRepository
from app.modules.crm.category_directory_schemas import CategoryCard, CategoryPage
from app.modules.crm.directory_service import continuation, position
from app.modules.crm.reference_schemas import CrmGarmentModelCategoryRead


class CategoryDirectoryService:
    repository = CategoryDirectoryRepository()

    async def page(self, session, kind, query):
        after_id, after_value = position(query, kind)
        rows = await self.repository.page(
            session, kind, query, after_id=after_id, after_value=after_value
        )
        return CategoryPage(
            items=[CategoryCard.model_validate(row) for row in rows[: query.limit]],
            next_cursor=continuation(rows, query, kind),
        )

    async def detail(self, session, kind, identity):
        row = await self.repository.detail(session, kind, identity)
        schema = (
            CrmGarmentModelCategoryRead if kind == "model-categories" else ProductCategoryResponse
        )
        return schema.model_validate(row) if row is not None else None
