from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.text import unicode_contains
from app.modules.crm.assortment_models import (
    CrmAccessory,
    CrmAccessoryCategory,
    CrmGarmentAccessoryRequirement,
    CrmGarmentPackagingRule,
    CrmPackagingBox,
)
from app.modules.crm.directory_repository import finish_page, ordered_text
from app.modules.crm.reference_models import CrmGarmentModel


class StockDirectoryRepository:
    @staticmethod
    async def stock(session: AsyncSession, kind, query, *, after_id, after_value):
        table = {
            "accessories": CrmAccessory,
            "boxes": CrmPackagingBox,
            "accessory-categories": CrmAccessoryCategory,
        }[kind]
        field, direction = query.sort.split(":")
        columns = [table.id, table.code, table.name, table.is_active, table.version]
        order = {
            "name": ordered_text(table.name),
            "code": ordered_text(table.code),
        }
        if kind == "accessory-categories":
            columns.append(table.description)
            statement = select(*columns, order[field].label("order_value"))
        else:
            columns += [
                table.unit_cost,
                table.currency,
                table.stock_quantity,
                table.minimum_stock_quantity,
                table.photo_media_object_id,
            ]
            order.update(stock=table.stock_quantity, price=table.unit_cost)
            if kind == "accessories":
                count = (
                    select(func.count())
                    .where(CrmGarmentAccessoryRequirement.accessory_id == table.id)
                    .correlate(table)
                    .scalar_subquery()
                )
                columns += [
                    table.category_id,
                    CrmAccessoryCategory.name.label("category_name"),
                    count.label("model_count"),
                ]
                statement = select(*columns, order[field].label("order_value")).join(
                    CrmAccessoryCategory, CrmAccessoryCategory.id == table.category_id
                )
                if query.category_id is not None:
                    statement = statement.where(table.category_id == query.category_id)
                if query.garment_model_id is not None:
                    statement = statement.where(
                        select(CrmGarmentAccessoryRequirement.id)
                        .where(
                            CrmGarmentAccessoryRequirement.accessory_id == table.id,
                            CrmGarmentAccessoryRequirement.garment_model_id
                            == query.garment_model_id,
                        )
                        .exists()
                    )
            else:
                order["capacity"] = table.max_items
                columns += [
                    table.inner_length_cm,
                    table.inner_width_cm,
                    table.inner_height_cm,
                    table.max_items,
                ]
                statement = select(*columns, order[field].label("order_value"))
            if query.stock != "all":
                statement = statement.where(
                    table.stock_quantity <= table.minimum_stock_quantity
                    if query.stock == "low"
                    else table.stock_quantity > table.minimum_stock_quantity
                )
        if query.active is not None:
            statement = statement.where(table.is_active.is_(query.active))
        if query.query:
            statement = statement.where(
                or_(
                    unicode_contains(table.name, query.query),
                    unicode_contains(table.code, query.query),
                )
            )
        return (
            (
                await session.execute(
                    finish_page(
                        statement,
                        id_column=table.id,
                        order_value=order[field],
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

    @staticmethod
    async def relations(session: AsyncSession, kind, query, *, after_id, after_value):
        packaging = kind == "packaging-rules"
        link = CrmGarmentPackagingRule if packaging else CrmGarmentAccessoryRequirement
        target = CrmPackagingBox if packaging else CrmAccessory
        target_id = link.box_id if packaging else link.accessory_id
        order_value = link.priority if packaging else link.id
        extras = (
            [target.name.label("box_name"), target.max_items.label("box_capacity")]
            if packaging
            else [target.name.label("accessory_name")]
        )
        statement = (
            select(
                *link.__table__.c,
                CrmGarmentModel.name.label("garment_model_name"),
                *extras,
                order_value.label("order_value"),
            )
            .join(CrmGarmentModel, CrmGarmentModel.id == link.garment_model_id)
            .join(target, target.id == target_id)
        )
        if query.garment_model_id is not None:
            statement = statement.where(link.garment_model_id == query.garment_model_id)
        if query.query:
            statement = statement.where(
                or_(
                    unicode_contains(CrmGarmentModel.name, query.query),
                    unicode_contains(CrmGarmentModel.code, query.query),
                    unicode_contains(target.name, query.query),
                    unicode_contains(target.code, query.query),
                )
            )
        return (
            (
                await session.execute(
                    finish_page(
                        statement,
                        id_column=link.id,
                        order_value=order_value,
                        direction="asc" if packaging else "desc",
                        limit=query.limit,
                        after_id=after_id,
                        after_value=after_value,
                    )
                )
            )
            .mappings()
            .all()
        )
