from __future__ import annotations

from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.migration.types import (
    CatalogContractComparison,
    CatalogMigrationPlan,
    LegacyMediaReference,
)
from app.modules.catalog.service import CatalogService
from app.modules.media.models import ProductMediaRole, ProductVariantMediaRole


class CatalogContractComparator:
    def __init__(self, service: CatalogService) -> None:
        self.service = service

    async def compare(
        self,
        session: AsyncSession,
        plan: CatalogMigrationPlan,
    ) -> CatalogContractComparison:
        expected_list, expected_details = expected_legacy_contract(plan)
        actual_list = [
            product.model_dump() for product in await self.service.list_products(session)
        ]
        actual_details: dict[int, dict[str, object]] = {}
        for product_id in sorted(expected_details):
            detail = await self.service.get_product(session, product_id)
            if detail is not None:
                actual_details[product_id] = detail.model_dump()

        mismatches: list[str] = []
        _compare_values(expected_list, actual_list, path="list", mismatches=mismatches)
        _compare_values(
            expected_details,
            actual_details,
            path="details",
            mismatches=mismatches,
        )
        return CatalogContractComparison(
            list_products=len(actual_list),
            detail_products=len(actual_details),
            mismatches=tuple(mismatches),
        )


def expected_legacy_contract(
    plan: CatalogMigrationPlan,
) -> tuple[list[dict[str, object]], dict[int, dict[str, object]]]:
    product_media = _reference_values(plan.references, owner_type="product")
    variant_media = _reference_values(plan.references, owner_type="variant")
    variants_by_product: dict[int, list[dict[str, object]]] = {}
    for variant in plan.variants:
        media = variant_media.get(variant.id, {})
        variants_by_product.setdefault(variant.product_id, []).append(
            {
                "id": variant.id,
                "product_id": variant.product_id,
                "size": variant.size,
                "color": variant.color,
                "color_hex": variant.color_hex,
                "stock_quantity": variant.stock_quantity,
                "width_cm": _optional_float(variant.width_cm),
                "height_cm": _optional_float(variant.height_cm),
                "preview_image": _joined_or_none(
                    media.get(ProductVariantMediaRole.PREVIEW_IMAGE.value)
                ),
                "images": _joined_or_none(media.get(ProductVariantMediaRole.IMAGES.value)),
            }
        )

    list_payload: list[dict[str, object]] = []
    detail_payload: dict[int, dict[str, object]] = {}
    for product in sorted(plan.products, key=lambda item: item.id, reverse=True):
        media = product_media.get(product.id, {})
        payload: dict[str, object] = {
            "id": product.id,
            "title": product.title,
            "price": float(product.price),
            "old_price": _optional_float(product.old_price),
            "description": product.description,
            "composition": product.composition,
            "model_info": product.model_info,
            "sizes": ",".join(product.sizes),
            "colors": ",".join(product.colors),
            "is_active": product.is_active,
            "type": product.product_type,
            "weight": float(product.weight_kg),
            "height": float(product.height_cm),
            "width": float(product.width_cm),
            "length": float(product.length_cm),
            "stock_quantity": product.stock_quantity,
        }
        payload.update(
            {role.value: _joined_or_none(media.get(role.value)) for role in ProductMediaRole}
        )
        list_payload.append(payload)
        detail_payload[product.id] = {
            **payload,
            "variants": sorted(
                variants_by_product.get(product.id, []),
                key=lambda item: int(item["id"]),
            ),
        }
    return list_payload, detail_payload


def _reference_values(
    references: tuple[LegacyMediaReference, ...],
    *,
    owner_type: Literal["product", "variant"],
) -> dict[int, dict[str, list[str]]]:
    grouped: dict[int, dict[str, list[tuple[int, str]]]] = {}
    for reference in references:
        if reference.owner_type != owner_type:
            continue
        grouped.setdefault(reference.owner_id, {}).setdefault(reference.role, []).append(
            (reference.sort_order, reference.source_url)
        )
    return {
        owner_id: {role: [url for _, url in sorted(values)] for role, values in roles.items()}
        for owner_id, roles in grouped.items()
    }


def _joined_or_none(values: list[str] | None) -> str | None:
    return ",".join(values) if values else None


def _optional_float(value: object | None) -> float | None:
    return float(value) if value is not None else None


def _compare_values(
    expected: object,
    actual: object,
    *,
    path: str,
    mismatches: list[str],
) -> None:
    if isinstance(expected, dict) and isinstance(actual, dict):
        expected_keys = set(expected)
        actual_keys = set(actual)
        for key in sorted(expected_keys - actual_keys, key=str):
            mismatches.append(f"{path}.{key}: missing from actual")
        for key in sorted(actual_keys - expected_keys, key=str):
            mismatches.append(f"{path}.{key}: unexpected in actual")
        for key in sorted(expected_keys & actual_keys, key=str):
            _compare_values(
                expected[key],
                actual[key],
                path=f"{path}.{key}",
                mismatches=mismatches,
            )
        return
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            mismatches.append(f"{path}: list length expected {len(expected)}, actual {len(actual)}")
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual, strict=False)):
            _compare_values(
                expected_item,
                actual_item,
                path=f"{path}[{index}]",
                mismatches=mismatches,
            )
        return
    if expected != actual:
        mismatches.append(f"{path}: expected {expected!r}, actual {actual!r}")
