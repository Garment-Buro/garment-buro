"""Versioned evidence from stored rows, independent of the public catalog DTO."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.deletion_repository import CatalogDeletionRepository
from app.modules.catalog.mapper import PRODUCT_MULTI_MEDIA_ROLES
from app.modules.catalog.models import Product
from app.modules.media.models import MediaStatus, ProductMediaRole, ProductVariantMediaRole

DELETION_AUDIT_SCHEMA = "catalog.product-deleted.v2"
PRODUCT_MEDIA_ROLES = frozenset(role.value for role in ProductMediaRole)


def _json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=value.tzinfo or timezone.utc)
            .astimezone(timezone.utc)
            .isoformat(timespec="microseconds")
        )
    raise TypeError(f"Unsupported catalog audit value: {type(value).__name__}")


def _canonical_bytes(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default
    ).encode("utf-8")


@dataclass(frozen=True)
class CatalogDeletionAudit:
    checksum: str
    variants_count: int
    media_links_count: int
    media_references_count: int

    def details(self) -> dict[str, object]:
        return {
            "snapshot_schema": DELETION_AUDIT_SCHEMA,
            "variants_count": self.variants_count,
            "media_links_count": self.media_links_count,
            "media_references_count": self.media_references_count,
        }


async def catalog_deletion_audit(session: AsyncSession, product: Product) -> CatalogDeletionAudit:
    """Hash canonical JSON as cursor batches; retain only counters and one SKU's roles."""
    sections = CatalogDeletionRepository.sections(product.id)
    scalars = {
        "schema": DELETION_AUDIT_SCHEMA,
        "product": {
            attribute.columns[0].name: getattr(product, attribute.key)
            for attribute in inspect(product).mapper.column_attrs
        },
    }
    digest = hashlib.sha256()
    digest.update(b"{")
    variants_count = media_links_count = media_references_count = 0
    product_single_roles: set[str] = set()
    current_variant = None
    variant_preview_counted = False
    for index, name in enumerate(sorted([*sections, *scalars])):
        if index:
            digest.update(b",")
        digest.update(_canonical_bytes(name) + b":")
        if name in scalars:
            digest.update(_canonical_bytes(scalars[name]))
            continue
        digest.update(b"[")
        first = True
        async for row in CatalogDeletionRepository.rows(session, sections[name]):
            if not first:
                digest.update(b",")
            first = False
            digest.update(_canonical_bytes(row))
            if name == "variants":
                variants_count += 1
                continue
            media_links_count += 1
            if not row["media_is_public"] or row["media_status"] != MediaStatus.READY.value:
                continue
            role = row["role"]
            if name == "product_media":
                if role in PRODUCT_MULTI_MEDIA_ROLES:
                    media_references_count += 1
                elif role in PRODUCT_MEDIA_ROLES and role not in product_single_roles:
                    product_single_roles.add(role)
                    media_references_count += 1
            else:
                if current_variant != row["product_variant_id"]:
                    current_variant = row["product_variant_id"]
                    variant_preview_counted = False
                if role == ProductVariantMediaRole.IMAGES.value:
                    media_references_count += 1
                elif (
                    role == ProductVariantMediaRole.PREVIEW_IMAGE.value
                    and not variant_preview_counted
                ):
                    variant_preview_counted = True
                    media_references_count += 1
        digest.update(b"]")
    digest.update(b"}")
    return CatalogDeletionAudit(
        digest.hexdigest(), variants_count, media_links_count, media_references_count
    )
