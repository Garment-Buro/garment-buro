from datetime import datetime, timezone

from sqlalchemy import select

from app.modules.crm.models import CrmOrderProject
from app.modules.identity.security import ensure_utc
from app.modules.orders.models import Order
from app.modules.production.evidence import (
    ProductionConflict,
    ProductionNotFound,
    order_evidence,
    verify_loaded_specification,
)
from app.modules.production.models import (
    ProductionBag,
    ProductionEvent,
    ProductionSpecification,
    ProductionWorkItem,
)
from app.modules.production.projections import bag_display_state, floor_customization, project_unit
from app.modules.production.read_repository import ProductionDetailRepository
from app.modules.production.repository import ProductionRepository


def _tech_card_view(card):
    return {
        "id": card.id,
        "name": card.name_snapshot,
        "revision": card.revision_number,
        "description": card.description_snapshot,
        "checkpoints": [
            {
                "position": point.position,
                "name": point.name,
                "description": point.description,
                "stage_code": point.stage_code,
                "standard_minutes": (
                    str(point.standard_minutes) if point.standard_minutes is not None else None
                ),
            }
            for point in card.checkpoints
        ],
    }


def floor_evidence(item):
    data = order_evidence(item)
    data["customization"] = floor_customization(data["customization"])
    return data


def _custom_measurement(source, key):
    customization = source.customization_snapshot or {}
    fit = customization.get("fit") or {}
    garment = customization.get("garment") or {}
    fallback = "heightCm" if key == "lengthCm" else key
    value = fit.get(key, garment.get(fallback))
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _custom_sleeve_variant(source):
    customization = source.customization_snapshot or {}
    fit = customization.get("fit") or {}
    return "height" if fit.get("sleeveMode") == "height" else "standard"


def cutting_details(data, *, source, spec, files):
    if spec is None:
        return None
    plan = data.plans.get(spec.plan_id)
    if plan is None:
        return None

    pattern_ids = set(spec.specification["pattern_file_ids"])
    pattern_media_ids = {
        attachment.media_object_id for attachment, _ in files if attachment.id in pattern_ids
    }
    patterns = data.patterns.get((plan.garment_model_id, plan.garment_size_id), [])
    sleeve_variant = _custom_sleeve_variant(source)
    pattern = next((row for row in patterns if row.media_object_id in pattern_media_ids), None)
    if pattern is None and len(patterns) == 1:
        pattern = patterns[0]
    if pattern is None:
        width = _custom_measurement(source, "widthCm")
        length = _custom_measurement(source, "lengthCm")
        if width is not None or length is not None:
            pattern = next(
                (
                    row
                    for row in patterns
                    if (width is None or float(row.width_cm) == width)
                    and (length is None or float(row.length_cm) == length)
                    and row.sleeve_variant == sleeve_variant
                ),
                None,
            )

    fabric = data.reserved_fabrics.get(plan.id)
    if fabric is None and source.variant_id_snapshot is not None:
        fabric = data.variant_fabrics.get(source.variant_id_snapshot)
    if fabric is None:
        fabric = data.default_fabrics.get(plan.garment_model_id)

    return {
        "pattern_code": pattern.code if pattern else None,
        "fabric": (
            {
                "code": fabric.code,
                "name": fabric.name,
                "color": fabric.color_name,
            }
            if fabric
            else None
        ),
        # Storage locations are not modelled yet. Keep this explicit in the API
        # and UI so the warehouse address cannot be silently forgotten.
        "fabric_location": "",
        "back_width_cm": float(pattern.width_cm) if pattern else None,
        "garment_length_cm": float(pattern.length_cm) if pattern else None,
        "sleeve_variant": pattern.sleeve_variant if pattern else sleeve_variant,
        "has_dtf": bool(spec.specification["print_file_ids"]),
    }


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
        else:
            # Managed employees use the same terminals for real work and training.
            # Keep mismatched flags out, but do not hide explicitly marked test orders.
            query = query.where(Order.is_demo == CrmOrderProject.is_demo)
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
        dtf_required_bags = set()
        purchase_counts = {}
        overdue_dtf_counts = {}
        now = datetime.now(timezone.utc)
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
                if spec.specification["print_file_ids"]:
                    dtf_required_bags.add(work.bag_id)
                route = spec.specification["route"]
                counts = stage_counts.setdefault(work.bag_id, {})
                if work.stage_index < len(route):
                    stage = work.lane or route[work.stage_index]
                    counts[stage] = counts.get(stage, 0) + 1
                if (
                    spec.specification["print_file_ids"]
                    and not work.dtf_ready
                    and (work.lane in {"kit", "waiting_dtf"} or work.lane is None)
                ):
                    dtf_counts[work.bag_id] = dtf_counts.get(work.bag_id, 0) + 1
                    if work.dtf_due_at and ensure_utc(work.dtf_due_at) < now:
                        overdue_dtf_counts[work.bag_id] = overdue_dtf_counts.get(work.bag_id, 0) + 1
                if work.lane in {"kit", "waiting_dtf"} and any(
                    not work.component_checks.get(component["key"])
                    for component in spec.specification["components"]
                ):
                    purchase_counts[work.bag_id] = purchase_counts.get(work.bag_id, 0) + 1
        return {
            "items": [
                {
                    "project_id": project.id,
                    "order_id": order.id,
                    "is_demo": order.is_demo,
                    "customer": f"Заказ №{order.id}",
                    "flow_version": bag.flow_version if bag else 2,
                    "units_count": project.units_count,
                    "state": bag.state if bag else "inbox",
                    "display_state": bag_display_state(
                        bag, stage_counts.get(bag.id, {}) if bag else []
                    ),
                    "version": bag.version if bag else 0,
                    "stage_counts": stage_counts.get(bag.id, {}) if bag else {},
                    "requires_dtf": bool(bag and bag.id in dtf_required_bags),
                    "dtf_pending": dtf_counts.get(bag.id, 0) if bag else 0,
                    "dtf_overdue": overdue_dtf_counts.get(bag.id, 0) if bag else 0,
                    "purchase_pending": purchase_counts.get(bag.id, 0) if bag else 0,
                    "tech_approved": bool(bag and bag.tech_approved_at),
                    "dtf_approved": bool(bag and bag.dtf_approved_at),
                    "qr_ready": bool(bag and bag.public_token),
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
        cutting = bool(set(stations) & {"tech", "cut"})
        data = await ProductionDetailRepository().load(
            session,
            units=units,
            specifications=specs,
            cutting=cutting,
            editing="tech" in stations,
        )
        work_by_unit = {row.unit_id: row for row in work}
        cards_by_model = {
            model_id: [_tech_card_view(card) for card in cards]
            for model_id, cards in data.cards.items()
        }
        result = []
        for unit in units:
            source = data.items.get(unit.order_item_id)
            if source is None:
                raise ProductionConflict("Нет исходной позиции заказа")
            row = work_by_unit.get(unit.id)
            spec = specs.get(row.specification_id) if row else None
            blockers = []
            if spec:
                try:
                    verify_loaded_specification(
                        unit,
                        spec,
                        source,
                        plan=data.plans.get(spec.plan_id),
                        files=data.specification_files(spec.specification),
                    )
                except ProductionConflict as error:
                    blockers.append(str(error))
            else:
                blockers.append("Технолог ещё не закрепил спецификацию и файлы")
            if row and row.issue:
                blockers.append(row.issue)
            garment_model_id = data.model_ids.get(unit.product_id_snapshot)
            sizes = data.sizes.get(garment_model_id, [])
            cards = cards_by_model.get(garment_model_id, [])
            if garment_model_id is None and not spec:
                blockers.append("Модель каталога не связана с производственной моделью")
            assigned_card = next(
                (
                    card
                    for card in cards
                    if spec and card["id"] == spec.specification["tech_card_revision_id"]
                ),
                None,
            )
            if spec and assigned_card is None:
                revision = data.revisions.get(spec.specification["tech_card_revision_id"])
                if revision:
                    assigned_card = _tech_card_view(revision)
            file_card_ids = {card["id"] for card in cards}
            if spec:
                file_card_ids.add(spec.specification["tech_card_revision_id"])
            files = data.visible_files(unit.id, file_card_ids)
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
                    "requires_dtf": bool(spec and spec.specification["print_file_ids"]),
                    "lane": row.lane if row else None,
                    "public_token": row.public_token if row else None,
                    "dtf_due_at": row.dtf_due_at if row else None,
                    "issue": row.issue if row else None,
                    "blockers": blockers,
                    "sizes": sizes,
                    "cards": cards,
                    "tech_card": assigned_card,
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
                    "cutting": (
                        cutting_details(
                            data,
                            source=source,
                            spec=spec,
                            files=files,
                        )
                        if cutting
                        else None
                    ),
                }
            )
        history_visible = bool(set(stations) & {"tech", "kit", "packing"})
        events = (
            list(
                await session.scalars(
                    select(ProductionEvent)
                    .where(ProductionEvent.bag_id == bag.id)
                    .order_by(ProductionEvent.version.desc())
                    .limit(100)
                )
            )
            if bag and history_visible
            else []
        )
        delivery = None
        if set(stations) & {"packing", "shipping"}:
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
            "flow_version": bag.flow_version if bag else 2,
            "display_state": bag_display_state(bag, [row.lane for row in work]),
            "public_token": bag.public_token if bag else None,
            "tech_approved": bool(bag and bag.tech_approved_at),
            "tech_approved_at": bag.tech_approved_at if bag else None,
            "dtf_approved": bool(bag and bag.dtf_approved_at),
            "dtf_approved_at": bag.dtf_approved_at if bag else None,
            "qr_ready": bool(bag and bag.public_token),
            "customer": f"Заказ №{order.id}",
            "units_count": project.units_count,
            "paid_at": project.payment_succeeded_at_snapshot,
            "order_status": order.status,
            "payment_status": order.payment_status,
            "project_status": project.status,
            "delivery": delivery,
            "tracking_number": bag.tracking_number if bag else None,
            "units": [project_unit(row, stations) for row in result],
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
            ]
            if history_visible
            else [],
        }
