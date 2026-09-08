import hashlib
import json

from sqlalchemy import select

from app.modules.crm.file_models import CrmFileAttachment
from app.modules.crm.production_models import CrmProductionPlanRevision
from app.modules.media.models import MediaObject


class ProductionConflict(ValueError):
    pass


class ProductionNotFound(LookupError):
    pass


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


def order_evidence(item):
    return {
        "order_item_id": item.id,
        "product_id": item.product_id_snapshot,
        "variant_id": item.variant_id_snapshot,
        "title": item.title_snapshot,
        "size": item.size_snapshot,
        "color": item.color_snapshot,
        "sku": item.sku_snapshot,
        "quantity": item.quantity,
        "image": item.image_url_snapshot,
        "customization": item.customization_snapshot,
    }


async def validate_files(session, *, unit_id, card_id, pattern_ids, print_ids):
    ids = set(pattern_ids + print_ids)
    if set(pattern_ids) & set(print_ids):
        raise ProductionConflict("Лекала и печать должны быть отдельными файлами")
    files = list(
        (
            await session.execute(
                select(CrmFileAttachment, MediaObject)
                .join(MediaObject, MediaObject.id == CrmFileAttachment.media_object_id)
                .where(CrmFileAttachment.id.in_(ids))
            )
        ).all()
    )
    if len(files) != len(ids):
        raise ProductionConflict("Не все файлы сохранены в базе")
    for attachment, media in files:
        if (
            media.status != "ready"
            or media.is_public
            or not media.checksum_sha256
            or media.size_bytes <= 0
        ):
            raise ProductionConflict("Файл не готов в приватном хранилище")
        if attachment.production_unit_id != unit_id and not (
            attachment.id in pattern_ids
            and attachment.tech_card_revision_id == card_id
            and attachment.role == "pattern"
        ):
            raise ProductionConflict("Файл относится к другой вещи или техкарте")
    return [
        {
            "id": attachment.id,
            "filename": media.original_filename,
            "sha256": media.checksum_sha256,
            "size_bytes": media.size_bytes,
            "content_type": media.content_type,
            "storage_digest": digest(
                {
                    "media_id": media.id,
                    "bucket": media.bucket_name,
                    "key": media.object_key,
                    "version": media.version_id,
                }
            ),
        }
        for attachment, media in files
    ]


async def verify_specification(session, unit, spec, item):
    if spec.unit_id != unit.id or spec.order_digest != digest(order_evidence(item)):
        raise ProductionConflict("Данные заказа изменились относительно утверждённого снимка")
    if spec.specification_digest != digest(spec.specification):
        raise ProductionConflict("Нарушена целостность производственной спецификации")
    plan = await session.get(CrmProductionPlanRevision, spec.plan_id)
    if plan is None or plan.production_unit_id != unit.id or plan.status != "active":
        raise ProductionConflict("Закреплённый производственный план больше не активен")
    files = await validate_files(
        session,
        unit_id=unit.id,
        card_id=plan.tech_card_revision_id,
        pattern_ids=spec.specification["pattern_file_ids"],
        print_ids=spec.specification["print_file_ids"],
    )
    if sorted(files, key=lambda x: x["id"]) != sorted(
        spec.specification["files"], key=lambda x: x["id"]
    ):
        raise ProductionConflict("Файлы отличаются от утверждённых оригиналов")
