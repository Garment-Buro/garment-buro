"""Request-local loading for a complete production order, without per-unit SQL."""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, raiseload, selectinload

from app.modules.catalog.models import Product, ProductVariant
from app.modules.crm.assortment_models import CrmGarmentFabricRequirement, CrmGarmentPattern
from app.modules.crm.file_models import CrmFileAttachment
from app.modules.crm.material_models import CrmMaterialReservation
from app.modules.crm.models import CrmProductionUnit
from app.modules.crm.production_models import CrmProductionPlanRevision
from app.modules.crm.reference_models import (
    CrmFabric,
    CrmGarmentModel,
    CrmGarmentSize,
    CrmTechCard,
    CrmTechCardRevision,
)
from app.modules.media.models import MediaObject
from app.modules.orders.models import OrderItem
from app.modules.production.models import ProductionSpecification


def batches(values):
    ordered = sorted(set(values))
    for start in range(0, len(ordered), 256):
        yield ordered[start : start + 256]


@dataclass
class ProductionDetailData:
    items: dict[int, OrderItem] = field(default_factory=dict)
    model_ids: dict[int, int | None] = field(default_factory=dict)
    sizes: dict[int, list[dict[str, int | str]]] = field(default_factory=lambda: defaultdict(list))
    cards: dict[int, list[CrmTechCardRevision]] = field(default_factory=lambda: defaultdict(list))
    revisions: dict[int, CrmTechCardRevision] = field(default_factory=dict)
    plans: dict[int, CrmProductionPlanRevision] = field(default_factory=dict)
    files: dict[int, tuple[CrmFileAttachment, MediaObject]] = field(default_factory=dict)
    unit_files: dict[int, list[tuple[CrmFileAttachment, MediaObject]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    card_files: dict[int, list[tuple[CrmFileAttachment, MediaObject]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    patterns: dict[tuple[int, int], list[CrmGarmentPattern]] = field(
        default_factory=lambda: defaultdict(list)
    )
    reserved_fabrics: dict[int, CrmFabric] = field(default_factory=dict)
    variant_fabrics: dict[int, CrmFabric] = field(default_factory=dict)
    default_fabrics: dict[int, CrmFabric] = field(default_factory=dict)

    def visible_files(self, unit_id, card_ids):
        # Never expose another unit's files merely because they shared a batch.
        rows = {row[0].id: row for row in self.unit_files.get(unit_id, [])}
        for card_id in card_ids:
            rows.update({row[0].id: row for row in self.card_files.get(card_id, [])})
        return [
            rows[key]
            for key in sorted(rows)
            if rows[key][1].status == "ready" and not rows[key][1].is_public
        ]

    def specification_files(self, specification):
        ids = set(specification["pattern_file_ids"] + specification["print_file_ids"])
        # Include non-ready/public/foreign rows for the shared validator to reject;
        # absence is different from an existing but unusable attachment.
        return [self.files[key] for key in sorted(ids) if key in self.files]


class ProductionDetailRepository:
    async def load(
        self,
        session: AsyncSession,
        *,
        units: Sequence[CrmProductionUnit],
        specifications: Mapping[int, ProductionSpecification],
        cutting: bool,
        editing: bool,
    ) -> ProductionDetailData:
        data = ProductionDetailData()
        for ids in batches(unit.order_item_id for unit in units):
            for item in await session.scalars(
                select(OrderItem)
                .where(OrderItem.id.in_(ids))
                .execution_options(populate_existing=True)
            ):
                data.items[item.id] = item
        for ids in batches(unit.product_id_snapshot for unit in units):
            for product_id, model_id in await session.execute(
                select(Product.id, Product.garment_model_id).where(Product.id.in_(ids))
            ):
                data.model_ids[product_id] = model_id
        model_ids = {value for value in data.model_ids.values() if value is not None}
        for ids in batches(model_ids if editing else set()):
            for model_id, size_id, code in await session.execute(
                select(CrmGarmentSize.garment_model_id, CrmGarmentSize.id, CrmGarmentSize.code)
                .where(CrmGarmentSize.garment_model_id.in_(ids), CrmGarmentSize.is_active.is_(True))
                .order_by(CrmGarmentSize.sort_order, CrmGarmentSize.id)
            ):
                data.sizes[model_id].append({"id": size_id, "code": code})
            for model_id, revision in await session.execute(
                select(CrmTechCard.garment_model_id, CrmTechCardRevision)
                .join(CrmTechCardRevision, CrmTechCardRevision.tech_card_id == CrmTechCard.id)
                .options(selectinload(CrmTechCardRevision.checkpoints))
                .where(
                    CrmTechCard.garment_model_id.in_(ids),
                    CrmTechCard.is_active.is_(True),
                    CrmTechCardRevision.status == "published",
                )
                .order_by(CrmTechCardRevision.id)
                .execution_options(populate_existing=True)
            ):
                data.cards[model_id].append(revision)
                data.revisions[revision.id] = revision
        pinned_ids = {
            spec.specification["tech_card_revision_id"] for spec in specifications.values()
        }
        for ids in batches(pinned_ids - data.revisions.keys()):
            for revision in await session.scalars(
                select(CrmTechCardRevision)
                .options(selectinload(CrmTechCardRevision.checkpoints))
                .where(CrmTechCardRevision.id.in_(ids))
                .execution_options(populate_existing=True)
            ):
                data.revisions[revision.id] = revision
        for ids in batches(spec.plan_id for spec in specifications.values()):
            for plan in await session.scalars(
                select(CrmProductionPlanRevision)
                .where(CrmProductionPlanRevision.id.in_(ids))
                .execution_options(populate_existing=True)
            ):
                data.plans[plan.id] = plan

        attachment_ids = {
            file_id
            for spec in specifications.values()
            for file_id in spec.specification["pattern_file_ids"]
            + spec.specification["print_file_ids"]
        }
        scopes = [(CrmFileAttachment.id, attachment_ids)]
        if editing:
            scopes.extend(
                [
                    (CrmFileAttachment.production_unit_id, {unit.id for unit in units}),
                    (CrmFileAttachment.tech_card_revision_id, data.revisions.keys()),
                ]
            )
        for column, scope in scopes:
            for ids in batches(scope):
                for attachment, media in await session.execute(
                    select(CrmFileAttachment, MediaObject)
                    .join(MediaObject, MediaObject.id == CrmFileAttachment.media_object_id)
                    .options(
                        raiseload("*"),
                        load_only(
                            CrmFileAttachment.id,
                            CrmFileAttachment.media_object_id,
                            CrmFileAttachment.production_unit_id,
                            CrmFileAttachment.tech_card_revision_id,
                            CrmFileAttachment.role,
                            raiseload=True,
                        ),
                        load_only(
                            MediaObject.id,
                            MediaObject.bucket_name,
                            MediaObject.object_key,
                            MediaObject.version_id,
                            MediaObject.original_filename,
                            MediaObject.content_type,
                            MediaObject.size_bytes,
                            MediaObject.checksum_sha256,
                            MediaObject.status,
                            MediaObject.is_public,
                            raiseload=True,
                        ),
                    )
                    .where(column.in_(ids))
                    .execution_options(populate_existing=True)
                ):
                    data.files[attachment.id] = (attachment, media)
        for attachment, media in data.files.values():
            if attachment.production_unit_id is not None:
                data.unit_files[attachment.production_unit_id].append((attachment, media))
            if attachment.tech_card_revision_id is not None:
                data.card_files[attachment.tech_card_revision_id].append((attachment, media))
        if cutting:
            await self._cutting(session, data)
        return data

    async def _cutting(self, session, data):
        slots = {
            (plan.garment_model_id, plan.garment_size_id)
            for plan in data.plans.values()
            if plan.garment_size_id is not None
        }
        for ids in batches(slots):
            for pattern in await session.scalars(
                select(CrmGarmentPattern)
                .where(
                    tuple_(
                        CrmGarmentPattern.garment_model_id, CrmGarmentPattern.garment_size_id
                    ).in_(ids),
                    CrmGarmentPattern.is_active.is_(True),
                )
                .order_by(CrmGarmentPattern.code, CrmGarmentPattern.id)
                .execution_options(populate_existing=True)
            ):
                data.patterns[(pattern.garment_model_id, pattern.garment_size_id)].append(pattern)
        # A correlated equality + ORDER BY id can walk the global PK when the
        # planner assumes a common plan ID. Seek the composite prefix first;
        # checking its owner outside LIMIT also handles a plan with no reserves.
        first_reservation = (
            select(
                CrmMaterialReservation.production_plan_revision_id.label("plan_id"),
                CrmMaterialReservation.fabric_id,
            )
            .where(
                CrmMaterialReservation.production_plan_revision_id >= CrmProductionPlanRevision.id
            )
            .order_by(
                CrmMaterialReservation.production_plan_revision_id,
                CrmMaterialReservation.id,
            )
            .limit(1)
            .correlate(CrmProductionPlanRevision)
            .subquery()
        )
        reserved = (
            select(first_reservation.c.fabric_id)
            .where(first_reservation.c.plan_id == CrmProductionPlanRevision.id)
            .correlate(CrmProductionPlanRevision)
            .scalar_subquery()
        )
        for ids in batches(data.plans):
            for plan_id, fabric in await session.execute(
                select(CrmProductionPlanRevision.id, CrmFabric)
                .join(CrmFabric, CrmFabric.id == reserved)
                .where(CrmProductionPlanRevision.id.in_(ids))
                .execution_options(populate_existing=True)
            ):
                data.reserved_fabrics[plan_id] = fabric
        for ids in batches(
            item.variant_id_snapshot
            for item in data.items.values()
            if item.variant_id_snapshot is not None
        ):
            for variant_id, fabric in await session.execute(
                select(ProductVariant.id, CrmFabric)
                .join(CrmFabric, CrmFabric.id == ProductVariant.fabric_id)
                .where(ProductVariant.id.in_(ids))
                .execution_options(populate_existing=True)
            ):
                data.variant_fabrics[variant_id] = fabric
        # Test activity by the referenced fabric's PK instead of allowing a hash
        # join over the entire fabric registry for every requested model.
        active_fabric = (
            select(CrmFabric.is_active)
            .where(CrmFabric.id == CrmGarmentFabricRequirement.fabric_id)
            .limit(1)
            .correlate(CrmGarmentFabricRequirement)
            .scalar_subquery()
        )
        default = (
            select(CrmGarmentFabricRequirement.fabric_id)
            .where(
                CrmGarmentFabricRequirement.garment_model_id == CrmGarmentModel.id,
                active_fabric.is_(True),
            )
            .order_by(CrmGarmentFabricRequirement.is_primary.desc(), CrmGarmentFabricRequirement.id)
            .limit(1)
            .correlate(CrmGarmentModel)
            .scalar_subquery()
        )
        for ids in batches(plan.garment_model_id for plan in data.plans.values()):
            selected = (
                select(CrmGarmentModel.id.label("model_id"), default.label("fabric_id"))
                .where(CrmGarmentModel.id.in_(ids))
                .cte("production_default_fabric_ids")
                .prefix_with("MATERIALIZED", dialect="postgresql")
            )
            for model_id, fabric in await session.execute(
                select(selected.c.model_id, CrmFabric)
                .join(CrmFabric, CrmFabric.id == selected.c.fabric_id)
                .execution_options(populate_existing=True)
            ):
                data.default_fabrics[model_id] = fabric
