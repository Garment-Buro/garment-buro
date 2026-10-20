from itertools import product

from sqlalchemy import (
    BigInteger,
    Integer,
    Numeric,
    and_,
    cast,
    column,
    func,
    or_,
    select,
    true,
    values,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.text import unicode_contains
from app.modules.crm.assortment_models import CrmGarmentPattern
from app.modules.crm.directory_repository import finish_page, ordered_text
from app.modules.crm.pattern_directory_schemas import PatternSize
from app.modules.crm.pattern_grid import GRID_STEP_CM
from app.modules.crm.reference_models import CrmGarmentModel, CrmGarmentSize

STEP_CENTS = int(GRID_STEP_CM * 100)


def cents(column):
    return cast(func.round(column * 100, 0), BigInteger)


def valid_grid_size(size):
    return and_(
        size.min_width_cm.is_not(None),
        size.max_width_cm.is_not(None),
        size.min_length_cm.is_not(None),
        size.max_length_cm.is_not(None),
        size.max_width_cm >= size.min_width_cm,
        size.max_length_cm >= size.min_length_cm,
    )


def required_slots(size):
    # Explicit integer division: PostgreSQL numeric->integer casts round rather than truncate.
    widths = (cents(size.max_width_cm) - cents(size.min_width_cm)).self_group().op("/")(
        STEP_CENTS
    ) + 1
    lengths = (cents(size.max_length_cm) - cents(size.min_length_cm)).self_group().op("/")(
        STEP_CENTS
    ) + 1
    return (
        widths
        * lengths
        * (cast(size.allow_standard_sleeve, Integer) + cast(size.allow_height_sleeve, Integer))
    )


def valid_slot(pattern, size):
    return and_(
        valid_grid_size(size),
        slot_in_geometry(
            pattern,
            min_width_cm=size.min_width_cm,
            max_width_cm=size.max_width_cm,
            min_length_cm=size.min_length_cm,
            max_length_cm=size.max_length_cm,
            allow_standard_sleeve=size.allow_standard_sleeve,
            allow_height_sleeve=size.allow_height_sleeve,
        ),
    )


def slot_in_geometry(
    pattern,
    *,
    min_width_cm,
    max_width_cm,
    min_length_cm,
    max_length_cm,
    allow_standard_sleeve,
    allow_height_sleeve,
):
    """Same exact grid predicate for SQL columns and an already-read size snapshot."""
    return and_(
        pattern.width_cm.between(min_width_cm, max_width_cm),
        pattern.length_cm.between(min_length_cm, max_length_cm),
        (cents(pattern.width_cm) - cents(min_width_cm)) % STEP_CENTS == 0,
        (cents(pattern.length_cm) - cents(min_length_cm)) % STEP_CENTS == 0,
        allowed_sleeve(pattern, allow_standard_sleeve, allow_height_sleeve),
    )


def allowed_sleeve(pattern, standard, height):
    return or_(
        and_(pattern.sleeve_variant == "standard", standard),
        and_(pattern.sleeve_variant == "height", height),
    )


class PatternDirectoryRepository:
    @staticmethod
    async def models(session: AsyncSession, query, *, after_id, after_value):
        model, size, pattern = CrmGarmentModel, CrmGarmentSize, CrmGarmentPattern
        total = (
            select(func.count())
            .where(pattern.garment_model_id == model.id)
            .correlate(model)
            .scalar_subquery()
        )
        required = (
            select(func.coalesce(func.sum(required_slots(size)), 0))
            .where(
                size.garment_model_id == model.id, size.is_active.is_(True), valid_grid_size(size)
            )
            .correlate(model)
            .scalar_subquery()
        )
        uploaded = (
            select(func.count())
            .select_from(pattern)
            .join(size, size.id == pattern.garment_size_id)
            .where(
                pattern.garment_model_id == model.id,
                size.is_active.is_(True),
                valid_slot(pattern, size),
            )
            .correlate(model)
            .scalar_subquery()
        )
        field, direction = query.sort.split(":")
        order = ordered_text(model.name if field == "model" else model.code)
        statement = select(
            model.id,
            model.name,
            model.code,
            model.is_active,
            model.version,
            total.label("pattern_count"),
            required.label("required_count"),
            uploaded.label("uploaded_count"),
            order.label("order_value"),
        )
        if query.model_id is not None:
            statement = statement.where(model.id == query.model_id)
        if query.active is not None:
            statement = statement.where(model.is_active.is_(query.active))
        if query.pattern_active is not None:
            statement = statement.where(
                select(pattern.id)
                .where(
                    pattern.garment_model_id == model.id,
                    pattern.is_active.is_(query.pattern_active),
                )
                .exists()
            )
        if query.query:
            statement = statement.where(
                or_(
                    unicode_contains(model.name, query.query),
                    unicode_contains(model.code, query.query),
                    select(pattern.id)
                    .where(
                        pattern.garment_model_id == model.id,
                        unicode_contains(pattern.code, query.query),
                    )
                    .exists(),
                )
            )
        rows = (
            (
                await session.execute(
                    finish_page(
                        statement,
                        id_column=model.id,
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
        return [{**row, "required_count": str(int(row["required_count"]))} for row in rows]

    @staticmethod
    async def files(session: AsyncSession, query, *, after_id, after_value):
        pattern, model, size = CrmGarmentPattern, CrmGarmentModel, CrmGarmentSize
        field, direction = query.sort.split(":")
        order = pattern.id if field == "id" else ordered_text(pattern.code)
        statement = (
            select(
                *pattern.__table__.c,
                model.name.label("garment_model_name"),
                size.code.label("size_code"),
                size.is_active.label("size_is_active"),
                order.label("order_value"),
            )
            .join(model, model.id == pattern.garment_model_id)
            .join(size, size.id == pattern.garment_size_id)
        )
        if query.model_id is not None:
            statement = statement.where(pattern.garment_model_id == query.model_id)
        if query.size_id is not None:
            statement = statement.where(pattern.garment_size_id == query.size_id)
        if query.active is not None:
            statement = statement.where(pattern.is_active.is_(query.active))
        if query.query:
            statement = statement.where(
                or_(
                    unicode_contains(pattern.code, query.query),
                    unicode_contains(pattern.name, query.query),
                    unicode_contains(model.name, query.query),
                    unicode_contains(size.code, query.query),
                )
            )
        return (
            (
                await session.execute(
                    finish_page(
                        statement,
                        id_column=pattern.id,
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

    @staticmethod
    async def sizes(session: AsyncSession, query, *, after_id, after_value):
        size = CrmGarmentSize
        field, direction = query.sort.split(":")
        order = size.sort_order if field == "position" else ordered_text(size.code)
        statement = select(
            size.id, size.code, size.code.label("name"), size.is_active, order.label("order_value")
        ).where(size.garment_model_id == query.model_id)
        if query.active is not None:
            statement = statement.where(size.is_active.is_(query.active))
        if query.query:
            statement = statement.where(unicode_contains(size.code, query.query))
        return (
            (
                await session.execute(
                    finish_page(
                        statement,
                        id_column=size.id,
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

    @staticmethod
    async def context(session: AsyncSession, model_id: int, size_id: int | None):
        model = (
            (
                await session.execute(
                    select(
                        CrmGarmentModel.id,
                        CrmGarmentModel.name,
                        CrmGarmentModel.code,
                        CrmGarmentModel.is_active,
                        CrmGarmentModel.version,
                    ).where(CrmGarmentModel.id == model_id)
                )
            )
            .mappings()
            .one_or_none()
        )
        if model is None:
            return None
        size = CrmGarmentSize
        statement = select(
            size.id,
            size.code,
            size.is_active,
            size.version,
            size.min_width_cm,
            size.max_width_cm,
            size.min_length_cm,
            size.max_length_cm,
            size.allow_standard_sleeve,
            size.allow_height_sleeve,
        ).where(size.garment_model_id == model_id)
        if size_id is not None:
            statement = statement.where(size.id == size_id)
        record = (
            (
                await session.execute(
                    statement.order_by(size.is_active.desc(), size.sort_order, size.id).limit(1)
                )
            )
            .mappings()
            .one_or_none()
        )
        if size_id is not None and record is None:
            return None
        return {"model": model, "size": record, "pattern": None}

    @staticmethod
    async def pattern(session: AsyncSession, pattern_id: int):
        return (
            (
                await session.execute(
                    select(*CrmGarmentPattern.__table__.c).where(CrmGarmentPattern.id == pattern_id)
                )
            )
            .mappings()
            .one_or_none()
        )

    @staticmethod
    async def window(
        session: AsyncSession, model_id: int, size_context: PatternSize, widths, lengths
    ):
        if not widths or not lengths:
            return [], 0
        pattern = CrmGarmentPattern
        # Use the context whose version was checked, rather than joining a potentially
        # newer size row again. Literal bounds also let the planner estimate hot sizes.
        target = and_(
            pattern.garment_model_id == model_id,
            pattern.garment_size_id == size_context.id,
        )
        condition = and_(
            target,
            slot_in_geometry(
                pattern,
                min_width_cm=size_context.min_width_cm,
                max_width_cm=size_context.max_width_cm,
                min_length_cm=size_context.min_length_cm,
                max_length_cm=size_context.max_length_cm,
                allow_standard_sleeve=size_context.allow_standard_sleeve,
                allow_height_sleeve=size_context.allow_height_sleeve,
            ),
        )
        count = await session.scalar(select(func.count()).select_from(pattern).where(condition))
        if session.get_bind().dialect.name == "postgresql":
            # A parameterized IN×IN query can choose a broad bitmap scan for a hot
            # size once PostgreSQL switches to a generic prepared plan. Each lateral
            # probe is an exact indexed point, bounded to two sleeves + one invalid
            # duplicate. LIMIT also prevents the planner flattening this boundary.
            points = values(
                column("width_cm", Numeric(10, 2)),
                column("length_cm", Numeric(10, 2)),
                name="window_points",
            ).data(list(product(widths, lengths)))
            point = (
                select(*pattern.__table__.c)
                .where(
                    target,
                    pattern.width_cm == points.c.width_cm,
                    pattern.length_cm == points.c.length_cm,
                    allowed_sleeve(
                        pattern,
                        size_context.allow_standard_sleeve,
                        size_context.allow_height_sleeve,
                    ),
                )
                .correlate(points)
                .limit(3)
                .lateral("point_files")
            )
            statement = (
                select(*point.c)
                .select_from(points.join(point, true()))
                .order_by(point.c.id)
                .limit(73)
            )
        else:
            # SQLite is the lightweight contract dialect and has no LATERAL support.
            statement = (
                select(*pattern.__table__.c)
                .where(
                    target,
                    pattern.width_cm.in_(widths),
                    pattern.length_cm.in_(lengths),
                    allowed_sleeve(
                        pattern,
                        size_context.allow_standard_sleeve,
                        size_context.allow_height_sleeve,
                    ),
                )
                .order_by(pattern.id)
                .limit(73)
            )
        rows = (await session.execute(statement)).mappings().all()
        if len(rows) > 72:
            raise ValueError("Pattern grid contains duplicate slots")
        return rows, count
