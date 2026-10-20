from __future__ import annotations

from copy import deepcopy

from app.db.session import DatabaseManager
from app.modules.media.models import MediaObject, ProductMedia


def project_payload(product_id: int, media_id: int, *, key: str = "first-draft") -> dict:
    return {
        "client_key": key,
        "product_id": product_id,
        "kind": "draft",
        "title": "Мой проект",
        "snapshot": {
            "schemaVersion": 1,
            "activeView": "back",
            "canvasPixelSize": {"width": 390, "height": 700},
            "modelBounds": {"x": 45, "y": 80, "width": 300, "height": 500},
            "customization": {
                "kind": "constructor",
                "selectedSize": "M",
                "modelImages": {"front": {"mediaId": media_id}, "back": {"mediaId": media_id}},
                "canvas": {"widthCm": 80, "heightCm": 100},
                "garment": {"widthCm": 60, "heightCm": 75},
                "decorations": [],
                "totalPrice": 1234,
                "comment": "Сохранить расположение",
            },
        },
    }


def project_edit(created: dict, *, title: str = "Изменённое имя") -> dict:
    return {
        "expected_version": created["version"],
        "kind": created["kind"],
        "title": title,
        "snapshot": deepcopy(created["snapshot"]),
    }


async def seed_project_media(settings, products, users):
    database = DatabaseManager(settings)
    await database.startup()
    try:
        async with database.session() as session:
            records = [
                MediaObject(
                    bucket_name=bucket,
                    object_key=key,
                    content_type="image/png",
                    size_bytes=100,
                    checksum_sha256="a" * 64,
                    status="ready",
                    is_public=public,
                    uploaded_by_user_id=owner,
                )
                for bucket, key, public, owner in (
                    (settings.minio_media_bucket, f"catalog/{products[0]}.png", True, None),
                    (settings.minio_media_bucket, f"catalog/{products[1]}.png", True, None),
                    (
                        "garment-buro-test-projects",
                        f"projects/{users[0]}/one.png",
                        False,
                        users[0],
                    ),
                    (
                        "garment-buro-test-projects",
                        f"projects/{users[1]}/two.png",
                        False,
                        users[1],
                    ),
                    (
                        settings.minio_crm_bucket,
                        f"crm/projects-test/{users[0]}.png",
                        False,
                        users[0],
                    ),
                )
            ]
            session.add_all(records)
            await session.flush()
            for index in (0, 1):
                session.add(
                    ProductMedia(
                        product_id=products[index],
                        media_object_id=records[index].id,
                        role="image_left",
                        sort_order=0,
                    )
                )
            await session.commit()
            return [record.id for record in records]
    finally:
        await database.shutdown()
