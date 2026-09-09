from sqlalchemy import or_, select

from app.modules.crm.file_models import CrmFileAttachment
from app.modules.crm.models import CrmOrderProject
from app.modules.crm.production_repository import CrmProductionRepository
from app.modules.crm.reference_models import CrmTechCard, CrmTechCardRevision
from app.modules.media.models import MediaObject
from app.modules.orders.models import Order, OrderItem
from app.modules.production.evidence import (
    ProductionConflict,
    ProductionNotFound,
    order_evidence,
    verify_specification,
)
from app.modules.production.models import (
    ProductionBag,
    ProductionEvent,
    ProductionSpecification,
    ProductionWorkItem,
)
from app.modules.production.repository import ProductionRepository


def floor_evidence(item):
    data = order_evidence(item)
    if data["customization"]:
        custom = dict(data["customization"])
        custom.pop("totalPrice", None)
        if isinstance(custom.get("decorations"), list):
            custom["decorations"] = [
                {k: v for k, v in x.items() if k != "price"}
                for x in custom["decorations"]
                if isinstance(x, dict)
            ]
        data["customization"] = custom
    return data


class ProductionReadService:
    def __init__(self):
        self.repository = ProductionRepository()

    async def queue(self, session, *, cursor=None, limit=30, demo_only=False):
        query = (
            select(CrmOrderProject, Order, ProductionBag)
            .join(Order, Order.id == CrmOrderProject.order_id)
            .outerjoin(ProductionBag, ProductionBag.project_id == CrmOrderProject.id)
        )
        if demo_only:
            query = query.where(Order.is_demo.is_(True), CrmOrderProject.is_demo.is_(True))
        if cursor:
            query = query.where(CrmOrderProject.id < cursor)
        rows = list(
            (
                await session.execute(query.order_by(CrmOrderProject.id.desc()).limit(limit + 1))
            ).all()
        )
        # One bounded batch for the page, not one request per bag or station.
        stage_counts = {}
        dtf_counts = {}
        bag_ids = [bag.id for _, _, bag in rows[:limit] if bag]
        if bag_ids:
            work_rows = await session.execute(
                select(ProductionWorkItem, ProductionSpecification)
                .join(
                    ProductionSpecification,
                    ProductionSpecification.id == ProductionWorkItem.specification_id,
                )
                .where(ProductionWorkItem.bag_id.in_(bag_ids))
            )
            for work, spec in work_rows:
                route = spec.specification["route"]
                counts = stage_counts.setdefault(work.bag_id, {})
                if work.stage_index < len(route):
                    stage = route[work.stage_index]
                    counts[stage] = counts.get(stage, 0) + 1
                if spec.specification["print_file_ids"] and not work.dtf_ready:
                    dtf_counts[work.bag_id] = dtf_counts.get(work.bag_id, 0) + 1
        return {
            "items": [
                {
                    "project_id": project.id,
                    "order_id": order.id,
                    "is_demo": order.is_demo,
                    "customer": " ".join(filter(None, [order.first_name, order.last_name]))
                    or f"Заказ №{order.id}",
                    "units_count": project.units_count,
                    "state": bag.state if bag else "inbox",
                    "version": bag.version if bag else 0,
                    "stage_counts": stage_counts.get(bag.id, {}) if bag else {},
                    "dtf_pending": dtf_counts.get(bag.id, 0) if bag else 0,
                    "paid_at": project.payment_succeeded_at_snapshot,
                    "blocked": (not order.is_demo and order.payment_status != "paid")
                    or order.status == "cancelled"
                    or project.status in {"cancelled", "on_hold"},
                }
                for project, order, bag in rows[:limit]
            ],
            "next_cursor": rows[limit - 1][0].id if len(rows) > limit else None,
        }

    async def detail(self, session, *, project_id, stations):
        project = await self.repository.project(session, project_id)
        if project is None:
            raise ProductionNotFound("Заказ не найден")
        order = await session.get(Order, project.order_id)
        if order is None:
            raise ProductionConflict("Нет исходного заказа")
        bag = await self.repository.bag(session, project_id)
        work = await self.repository.work(session, bag.id) if bag else []
        specs = await self.repository.specifications(session, work)
        units = await self.repository.units(session, project_id)
        result = []
        plans = CrmProductionRepository()
        for unit in units:
            source = await session.get(OrderItem, unit.order_item_id)
            if source is None:
                raise ProductionConflict("Нет исходной позиции заказа")
            row = next((x for x in work if x.unit_id == unit.id), None)
            spec = specs.get(row.specification_id) if row else None
            blockers = []
            if spec:
                try:
                    await verify_specification(session, unit, spec, source)
                except ProductionConflict as error:
                    blockers.append(str(error))
            else:
                blockers.append("Технолог ещё не закрепил спецификацию и файлы")
            if row and row.issue:
                blockers.append(row.issue)
            link = await plans.get_catalog_model_link(
                session, catalog_product_id=unit.product_id_snapshot
            )
            sizes, cards = [], []
            if link:
                sizes = [
                    {"id": x.id, "code": x.code}
                    for x in await plans.list_active_sizes(
                        session, garment_model_id=link.garment_model_id
                    )
                ]
                cards = [
                    {"id": x.id, "name": x.name_snapshot, "revision": x.revision_number}
                    for x in await session.scalars(
                        select(CrmTechCardRevision)
                        .join(CrmTechCard, CrmTechCard.id == CrmTechCardRevision.tech_card_id)
                        .where(
                            CrmTechCard.garment_model_id == link.garment_model_id,
                            CrmTechCard.is_active.is_(True),
                            CrmTechCardRevision.status == "published",
                        )
                    )
                ]
            elif not spec:
                blockers.append("Модель каталога не связана с производственной моделью")
            files = list(
                (
                    await session.execute(
                        select(CrmFileAttachment, MediaObject)
                        .join(MediaObject, MediaObject.id == CrmFileAttachment.media_object_id)
                        .where(
                            or_(
                                CrmFileAttachment.production_unit_id == unit.id,
                                CrmFileAttachment.tech_card_revision_id.in_(
                                    [x["id"] for x in cards]
                                ),
                            ),
                            MediaObject.status == "ready",
                            MediaObject.is_public.is_(False),
                        )
                        .order_by(CrmFileAttachment.id)
                    )
                ).all()
            )
            result.append(
                {
                    "id": unit.id,
                    "number": unit.unit_number,
                    "crm_status": unit.status,
                    "source": floor_evidence(source),
                    "specification": spec.specification if spec else None,
                    "revision": spec.revision if spec else None,
                    "specification_id": spec.id if spec else None,
                    "stage_index": row.stage_index if row else 0,
                    "documents_confirmed": row.documents_confirmed if row else False,
                    "checks": row.component_checks if row else {},
                    "dtf_ready": row.dtf_ready if row else False,
                    "dtf_inserted": row.dtf_inserted if row else False,
                    "issue": row.issue if row else None,
                    "blockers": blockers,
                    "sizes": sizes,
                    "cards": cards,
                    "files": [
                        {
                            "id": a.id,
                            "name": m.original_filename,
                            "content_type": m.content_type,
                            "size_bytes": m.size_bytes,
                            "sha256": m.checksum_sha256,
                            "card_id": a.tech_card_revision_id,
                        }
                        for a, m in files
                    ],
                }
            )
        events = (
            list(
                await session.scalars(
                    select(ProductionEvent)
                    .where(ProductionEvent.bag_id == bag.id)
                    .order_by(ProductionEvent.version.desc())
                    .limit(100)
                )
            )
            if bag
            else []
        )
        delivery = None
        if set(stations) & {"tech", "shipping"}:
            delivery = {
                "recipient": " ".join(
                    filter(None, [order.last_name, order.first_name, order.patronymic])
                ),
                "phone": order.phone,
                "city": order.delivery_city,
                "address": order.delivery_address,
                "point_code": order.cdek_point_code,
                "method": order.delivery_method,
            }
        return {
            "project_id": project_id,
            "order_id": order.id,
            "is_demo": order.is_demo,
            "version": bag.version if bag else 0,
            "state": bag.state if bag else "inbox",
            "customer": " ".join(filter(None, [order.first_name, order.last_name]))
            or f"Заказ №{order.id}",
            "units_count": project.units_count,
            "paid_at": project.payment_succeeded_at_snapshot,
            "order_status": order.status,
            "payment_status": order.payment_status,
            "project_status": project.status,
            "delivery": delivery,
            "tracking_number": bag.tracking_number if bag else None,
            "units": result,
            "events": [
                {
                    "id": x.id,
                    "version": x.version,
                    "action": x.action,
                    "unit_id": x.unit_id,
                    "actor_id": x.actor_user_id,
                    "at": x.occurred_at,
                    "note": x.evidence.get("command", {}).get("note"),
                }
                for x in events
            ],
        }
