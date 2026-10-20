from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.text import unicode_contains
from app.modules.crm.directory_repository import finish_page, ordered_text
from app.modules.crm.reference_models import (
    CrmGarmentModel,
    CrmTechCard,
    CrmTechCardCheckpoint,
    CrmTechCardRevision,
)


def draft_number():
    return (
        select(CrmTechCardRevision.revision_number)
        .where(
            CrmTechCardRevision.tech_card_id == CrmTechCard.id,
            CrmTechCardRevision.status == "draft",
        )
        .correlate(CrmTechCard)
        .scalar_subquery()
    )


class TechDirectoryRepository:
    @staticmethod
    async def cards(session: AsyncSession, query, *, after_id, after_value):
        card, model = CrmTechCard, CrmGarmentModel
        latest = aliased(CrmTechCardRevision)
        count = (
            select(func.count())
            .where(CrmTechCardCheckpoint.tech_card_revision_id == latest.id)
            .correlate(latest)
            .scalar_subquery()
        )
        field, direction = query.sort.split(":")
        order = {
            "model": ordered_text(model.name),
            "code": ordered_text(card.code),
            "revision": card.latest_revision_number,
        }[field]
        statement = (
            select(
                card.id,
                card.garment_model_id,
                model.name.label("garment_model_name"),
                card.code,
                card.is_active,
                card.latest_revision_number,
                latest.status.label("latest_revision_status"),
                latest.name_snapshot.label("latest_revision_name"),
                count.label("checkpoint_count"),
                draft_number().label("draft_revision_number"),
                order.label("order_value"),
            )
            .join(model, model.id == card.garment_model_id)
            .outerjoin(
                latest,
                (latest.tech_card_id == card.id)
                & (latest.revision_number == card.latest_revision_number),
            )
        )
        if query.active is not None:
            statement = statement.where(card.is_active.is_(query.active))
        if query.revision_status is not None:
            statement = statement.where(latest.status == query.revision_status)
        if query.query:
            statement = statement.where(
                or_(
                    unicode_contains(card.code, query.query),
                    unicode_contains(model.name, query.query),
                    unicode_contains(latest.name_snapshot, query.query),
                )
            )
        return (
            (
                await session.execute(
                    finish_page(
                        statement,
                        id_column=card.id,
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
    async def models(session: AsyncSession, query, *, after_id, after_value):
        model = CrmGarmentModel
        field, direction = query.sort.split(":")
        order = ordered_text(model.name if field == "name" else model.code)
        statement = select(
            model.id, model.name, model.code, model.is_active, order.label("order_value")
        ).where(~select(CrmTechCard.id).where(CrmTechCard.garment_model_id == model.id).exists())
        if query.active is not None:
            statement = statement.where(model.is_active.is_(query.active))
        if query.query:
            statement = statement.where(
                or_(
                    unicode_contains(model.name, query.query),
                    unicode_contains(model.code, query.query),
                )
            )
        return (
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

    @staticmethod
    async def editor(session: AsyncSession, card_id: int):
        card, revision = CrmTechCard, CrmTechCardRevision
        source_id = (
            select(revision.id)
            .where(revision.tech_card_id == card.id, revision.status != "discarded")
            .order_by(revision.revision_number.desc())
            .limit(1)
            .correlate(card)
            .scalar_subquery()
        )
        row = (
            (
                await session.execute(
                    select(
                        card.id,
                        card.code,
                        card.garment_model_id,
                        CrmGarmentModel.name.label("garment_model_name"),
                        card.latest_revision_number,
                        draft_number().label("draft_revision_number"),
                        revision.id.label("source_id"),
                        revision.revision_number,
                        revision.name_snapshot,
                        revision.description_snapshot,
                    )
                    .join(CrmGarmentModel, CrmGarmentModel.id == card.garment_model_id)
                    .outerjoin(revision, revision.id == source_id)
                    .where(card.id == card_id)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        source = None
        if row["source_id"] is not None:
            checkpoints = (
                (
                    await session.execute(
                        select(*CrmTechCardCheckpoint.__table__.c)
                        .where(CrmTechCardCheckpoint.tech_card_revision_id == row["source_id"])
                        .order_by(CrmTechCardCheckpoint.position)
                        .limit(201)
                    )
                )
                .mappings()
                .all()
            )
            if len(checkpoints) > 200:
                raise ValueError("Tech-card revision exceeds the supported operation limit")
            source = dict(
                id=row["source_id"],
                revision_number=row["revision_number"],
                name_snapshot=row["name_snapshot"],
                description_snapshot=row["description_snapshot"],
                checkpoints=checkpoints,
            )
        return {**row, "source": source}
