from decimal import Decimal

from sqlalchemy import func, literal, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.text import UnicodeLower, unicode_contains
from app.modules.catalog.models import Product, ProductCategory
from app.modules.crm.assortment_models import (
    CrmAccessory,
    CrmAccessoryCategory,
    CrmGarmentFabricRequirement,
    CrmPackagingBox,
)
from app.modules.crm.directory_schemas import FabricDirectoryQuery, ModelDirectoryQuery
from app.modules.crm.material_models import CrmMaterialBalance
from app.modules.crm.reference_models import (
    CrmFabric,
    CrmGarmentModel,
    CrmGarmentModelCategory,
    CrmGarmentSize,
    CrmTechCard,
    CrmTechCardRevision,
)
from app.modules.crm.reference_schemas import GARMENT_MODEL_SIZE_LIMIT


def ordered_text(column):
    # pg_c_utf8 already orders by code point, matching C byte order in UTF-8.
    # Keep the same collation on the expression and its seek index.
    return UnicodeLower(column)


def finish_page(statement, *, id_column, order_value, direction, limit, after_id, after_value):
    ascending = direction == "asc"
    if after_id is not None:
        # Both keys have the same direction and all directory order values are non-null.
        # A row comparison gives PostgreSQL one index range, including deep continuations.
        key, after = tuple_(order_value, id_column), tuple_(after_value, after_id)
        statement = statement.where(key > after if ascending else key < after)
    return statement.order_by(
        order_value.asc() if ascending else order_value.desc(),
        id_column.asc() if ascending else id_column.desc(),
    ).limit(limit + 1)


class ReferenceDirectoryRepository:
    @staticmethod
    async def models(
        session: AsyncSession,
        query: ModelDirectoryQuery,
        *,
        after_id: int | None,
        after_value: str | int | Decimal | None,
    ):
        model = CrmGarmentModel
        sizes = (
            select(func.count())
            .where(CrmGarmentSize.garment_model_id == model.id, CrmGarmentSize.is_active.is_(True))
            .correlate(model)
            .scalar_subquery()
        )
        products = (
            select(func.count())
            .where(Product.garment_model_id == model.id)
            .correlate(model)
            .scalar_subquery()
        )
        published = (
            select(CrmTechCardRevision)
            .join(CrmTechCard, CrmTechCard.id == CrmTechCardRevision.tech_card_id)
            .where(
                CrmTechCard.garment_model_id == model.id, CrmTechCardRevision.status == "published"
            )
            .order_by(CrmTechCardRevision.published_at.desc(), CrmTechCardRevision.id.desc())
            .limit(1)
            .correlate(model)
        )
        field, direction = query.sort.split(":")
        order_value = {
            "name": ordered_text(model.name),
            "code": ordered_text(model.code),
            "sizes": sizes,
            "products": products,
        }[field]
        statement = select(
            model.id,
            model.category_id,
            CrmGarmentModelCategory.name.label("category_name"),
            model.code,
            model.name,
            model.is_active,
            model.base_weight_g,
            sizes.label("size_count"),
            products.label("product_count"),
            published.with_only_columns(CrmTechCardRevision.name_snapshot)
            .scalar_subquery()
            .label("tech_card_name"),
            published.with_only_columns(CrmTechCardRevision.revision_number)
            .scalar_subquery()
            .label("tech_card_revision"),
            order_value.label("order_value"),
        ).outerjoin(CrmGarmentModelCategory, CrmGarmentModelCategory.id == model.category_id)
        if query.active is not None:
            statement = statement.where(model.is_active.is_(query.active))
        if query.category_id is not None:
            statement = statement.where(model.category_id == query.category_id)
        if query.query:
            statement = statement.where(
                or_(
                    unicode_contains(model.name, query.query),
                    unicode_contains(model.code, query.query),
                )
            )
        return list(
            (
                await session.execute(
                    finish_page(
                        statement,
                        id_column=model.id,
                        order_value=order_value,
                        direction=direction,
                        limit=query.limit,
                        after_id=after_id,
                        after_value=after_value,
                    )
                )
            ).mappings()
        )

    @staticmethod
    async def fabrics(
        session: AsyncSession,
        query: FabricDirectoryQuery,
        *,
        after_id: int | None,
        after_value: str | int | Decimal | None,
    ):
        fabric, balance = CrmFabric, CrmMaterialBalance
        available = func.coalesce(balance.on_hand_meters - balance.reserved_meters, 0)
        field, direction = query.sort.split(":")
        order_value = {
            "name": ordered_text(fabric.name),
            "code": ordered_text(fabric.code),
            "stock": available,
            "price": func.coalesce(fabric.cost_per_kg, 0),
        }[field]
        statement = select(
            *fabric.__table__.c,
            balance.fabric_id.label("balance_id"),
            balance.on_hand_meters,
            balance.reserved_meters,
            balance.version.label("balance_version"),
            balance.updated_at.label("balance_updated_at"),
            order_value.label("order_value"),
        ).outerjoin(balance, balance.fabric_id == fabric.id)
        if query.active is not None:
            statement = statement.where(fabric.is_active.is_(query.active))
        if query.stock != "all":
            statement = statement.where(
                available <= fabric.minimum_stock_meters
                if query.stock == "low"
                else available > fabric.minimum_stock_meters
            )
        if query.query:
            statement = statement.where(
                or_(
                    unicode_contains(fabric.name, query.query),
                    unicode_contains(fabric.code, query.query),
                    unicode_contains(fabric.color_name, query.query),
                )
            )
        return list(
            (
                await session.execute(
                    finish_page(
                        statement,
                        id_column=fabric.id,
                        order_value=order_value,
                        direction=direction,
                        limit=query.limit,
                        after_id=after_id,
                        after_value=after_value,
                    )
                )
            ).mappings()
        )

    @staticmethod
    async def model_detail(session: AsyncSession, model_id: int):
        model = (
            (
                await session.execute(
                    select(*CrmGarmentModel.__table__.c).where(CrmGarmentModel.id == model_id)
                )
            )
            .mappings()
            .one_or_none()
        )
        if model is None:
            return None
        sizes = list(
            (
                await session.execute(
                    select(*CrmGarmentSize.__table__.c)
                    .where(
                        CrmGarmentSize.garment_model_id == model_id,
                        CrmGarmentSize.is_active.is_(True),
                    )
                    .order_by(CrmGarmentSize.sort_order, CrmGarmentSize.id)
                    .limit(GARMENT_MODEL_SIZE_LIMIT + 1)
                )
            ).mappings()
        )
        return {**model, "sizes": sizes}

    @staticmethod
    async def selected(session: AsyncSession, kind: str, ids: list[int]):
        table = {
            "models": CrmGarmentModel,
            "model-categories": CrmGarmentModelCategory,
            "product-categories": ProductCategory,
            "tech-card-models": CrmGarmentModel,
            "pattern-sizes": CrmGarmentSize,
            "fabrics": CrmFabric,
            "accessories": CrmAccessory,
            "boxes": CrmPackagingBox,
            "accessory-categories": CrmAccessoryCategory,
        }[kind]
        return (
            (
                await session.execute(
                    select(
                        table.id,
                        (table.code if kind == "pattern-sizes" else table.name).label("name"),
                        (table.slug if kind == "product-categories" else table.code).label("code"),
                        table.is_active,
                        (table.max_items if kind == "boxes" else literal(None)).label("max_items"),
                    )
                    .where(table.id.in_(set(ids)))
                    .order_by(table.id)
                )
            )
            .mappings()
            .all()
        )

    @staticmethod
    async def fabric_requirements(session: AsyncSession, query, after_id: int | None):
        requirement = CrmGarmentFabricRequirement
        statement = (
            select(
                *requirement.__table__.c,
                CrmGarmentModel.name.label("garment_model_name"),
                CrmFabric.name.label("fabric_name"),
                requirement.id.label("order_value"),
            )
            .join(CrmGarmentModel, CrmGarmentModel.id == requirement.garment_model_id)
            .join(CrmFabric, CrmFabric.id == requirement.fabric_id)
        )
        if query.garment_model_id is not None:
            statement = statement.where(requirement.garment_model_id == query.garment_model_id)
        if after_id is not None:
            statement = statement.where(requirement.id > after_id)
        return (
            (await session.execute(statement.order_by(requirement.id).limit(query.limit + 1)))
            .mappings()
            .all()
        )
