from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.assortment_schemas import CrmAccessoryCategoryRead, CrmPackagingBoxRead
from app.modules.crm.directory_service import continuation, position
from app.modules.crm.stock_directory_repository import StockDirectoryRepository
from app.modules.crm.stock_directory_schemas import (
    AccessoryCard,
    AccessoryCategoryPage,
    AccessoryDirectoryPage,
    AccessoryRequirementCard,
    AccessoryRequirementPage,
    BoxDirectoryPage,
    PackagingRuleCard,
    PackagingRulePage,
)


class StockDirectoryService:
    repository = StockDirectoryRepository()

    async def page(self, session: AsyncSession, kind, query):
        after_id, after_value = position(query, kind)
        if kind in {"accessory-requirements", "packaging-rules"}:
            rows = await self.repository.relations(
                session, kind, query, after_id=after_id, after_value=after_value
            )
        else:
            rows = await self.repository.stock(
                session, kind, query, after_id=after_id, after_value=after_value
            )
        row_type, page_type = {
            "accessories": (AccessoryCard, AccessoryDirectoryPage),
            "boxes": (CrmPackagingBoxRead, BoxDirectoryPage),
            "accessory-categories": (CrmAccessoryCategoryRead, AccessoryCategoryPage),
            "accessory-requirements": (AccessoryRequirementCard, AccessoryRequirementPage),
            "packaging-rules": (PackagingRuleCard, PackagingRulePage),
        }[kind]
        return page_type(
            items=[row_type.model_validate(row) for row in rows[: query.limit]],
            next_cursor=continuation(rows, query, kind),
        )
