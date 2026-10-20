from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.text import unicode_contains
from app.modules.catalog.models import Product, ProductCategory
from app.modules.crm.directory_repository import finish_page, ordered_text
from app.modules.crm.reference_models import CrmGarmentModel, CrmGarmentModelCategory


class CategoryDirectoryRepository:
    @staticmethod
    def source(kind):
        if kind == "model-categories":
            return CrmGarmentModelCategory, CrmGarmentModel, CrmGarmentModelCategory.code
        if kind == "product-categories":
            return ProductCategory, Product, ProductCategory.slug
        raise ValueError("Unknown category directory")

    async def page(self, session: AsyncSession, kind, query, *, after_id, after_value):
        category, item, code = self.source(kind)
        count = (
            select(func.count())
            .where(item.category_id == category.id)
            .correlate(category)
            .scalar_subquery()
        )
        field, direction = query.sort.split(":")
        order = (
            category.id
            if field == "id"
            else ordered_text(category.name if field == "name" else code)
        )
        statement = select(
            category.id,
            code.label("code"),
            category.name,
            category.is_active,
            category.version,
            count.label("item_count"),
            order.label("order_value"),
        )
        if query.active is not None:
            statement = statement.where(category.is_active.is_(query.active))
        if query.query:
            statement = statement.where(
                or_(
                    unicode_contains(category.name, query.query),
                    unicode_contains(code, query.query),
                )
            )
        return (
            (
                await session.execute(
                    finish_page(
                        statement,
                        id_column=category.id,
                        order_value=order,
                        direction=direction,
                        limit=query.limit,
                        after_id=after_id,
                        after_value=after_value,
                    )
                )
            )
            .mappings()
            .all()
        )

    async def detail(self, session: AsyncSession, kind, identity):
        table, _, _ = self.source(kind)
        columns = [table.id, table.name, table.is_active, table.version]
        columns += [table.code] if kind == "model-categories" else [table.slug, table.description]
        return (
            (await session.execute(select(*columns).where(table.id == identity)))
            .mappings()
            .one_or_none()
        )
