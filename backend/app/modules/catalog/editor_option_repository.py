from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.text import unicode_contains
from app.modules.catalog.editor_option_schemas import EditorOptionsQuery, EditorSizeQuery
from app.modules.crm.assortment_models import CrmGarmentFabricRequirement
from app.modules.crm.reference_models import CrmFabric, CrmGarmentModel, CrmGarmentSize


class EditorOptionRepository:
    @staticmethod
    def _model_columns():
        return CrmGarmentModel.id, CrmGarmentModel.name, CrmGarmentModel.is_active

    @staticmethod
    def _size_columns():
        return CrmGarmentSize.id, CrmGarmentSize.code, CrmGarmentSize.is_active

    @staticmethod
    def _fabric_columns():
        return (
            CrmFabric.id,
            CrmFabric.name,
            CrmFabric.is_active,
            CrmFabric.color_name,
            CrmFabric.color_hex,
        )

    @staticmethod
    async def models(session: AsyncSession, query: EditorOptionsQuery):
        model = CrmGarmentModel
        statement = select(*EditorOptionRepository._model_columns()).where(
            model.is_active.is_(True)
        )
        if query.query:
            statement = statement.where(
                unicode_contains(model.name, query.query)
                | unicode_contains(model.code, query.query)
            )
        # Seek the full index key, so sparse active rows do not walk the primary-key history.
        statement = statement.where(
            tuple_(model.is_active, model.id) > tuple_(True, query.cursor or 0)
        )
        return list(
            (await session.execute(statement.order_by(model.id).limit(query.limit + 1))).mappings()
        )

    @staticmethod
    async def model(session: AsyncSession, model_id: int):
        return (
            (
                await session.execute(
                    select(*EditorOptionRepository._model_columns()).where(
                        CrmGarmentModel.id == model_id
                    )
                )
            )
            .mappings()
            .one_or_none()
        )

    @staticmethod
    async def sizes(session: AsyncSession, query: EditorSizeQuery):
        size = CrmGarmentSize
        statement = select(*EditorOptionRepository._size_columns()).where(
            size.garment_model_id == query.model_id, size.is_active.is_(True)
        )
        if query.query:
            statement = statement.where(unicode_contains(size.code, query.query))
        statement = statement.where(
            tuple_(size.garment_model_id, size.is_active, size.id)
            > tuple_(query.model_id, True, query.cursor or 0)
        )
        return list(
            (await session.execute(statement.order_by(size.id).limit(query.limit + 1))).mappings()
        )

    @staticmethod
    async def selected_sizes(session: AsyncSession, model_id: int, ids: list[int]):
        if not ids:
            return []
        return list(
            (
                await session.execute(
                    select(*EditorOptionRepository._size_columns())
                    .where(
                        CrmGarmentSize.garment_model_id == model_id, CrmGarmentSize.id.in_(set(ids))
                    )
                    .order_by(CrmGarmentSize.id)
                )
            ).mappings()
        )

    @staticmethod
    async def fabrics(session: AsyncSession, query: EditorOptionsQuery):
        fabric = CrmFabric
        statement = select(*EditorOptionRepository._fabric_columns()).where(
            fabric.is_active.is_(True)
        )
        if query.model_id is not None:
            statement = statement.where(
                select(1)
                .where(
                    CrmGarmentFabricRequirement.fabric_id == fabric.id,
                    CrmGarmentFabricRequirement.garment_model_id == query.model_id,
                )
                .exists()
            )
        if query.query:
            statement = statement.where(
                unicode_contains(fabric.name, query.query)
                | unicode_contains(fabric.color_name, query.query)
                | unicode_contains(fabric.code, query.query)
            )
        statement = statement.where(
            tuple_(fabric.is_active, fabric.id) > tuple_(True, query.cursor or 0)
        )
        return list(
            (await session.execute(statement.order_by(fabric.id).limit(query.limit + 1))).mappings()
        )

    @staticmethod
    async def selected_fabrics(session: AsyncSession, ids: list[int]):
        return list(
            (
                await session.execute(
                    select(*EditorOptionRepository._fabric_columns())
                    .where(CrmFabric.id.in_(set(ids)))
                    .order_by(CrmFabric.id)
                )
            ).mappings()
        )
