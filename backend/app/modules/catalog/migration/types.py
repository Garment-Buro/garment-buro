from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True, slots=True)
class LegacyProductRecord:
    id: int
    title: str
    price: Decimal
    old_price: Decimal | None
    description: str | None
    composition: str | None
    model_info: str | None
    sizes: tuple[str, ...]
    colors: tuple[str, ...]
    is_active: bool
    product_type: str
    weight_kg: Decimal
    height_cm: Decimal
    width_cm: Decimal
    length_cm: Decimal
    stock_quantity: int


@dataclass(frozen=True, slots=True)
class LegacyVariantRecord:
    id: int
    product_id: int
    size: str | None
    color: str | None
    color_hex: str | None
    stock_quantity: int
    width_cm: Decimal | None
    height_cm: Decimal | None


@dataclass(frozen=True, slots=True)
class LegacyMediaReference:
    owner_type: Literal["product", "variant"]
    owner_id: int
    role: str
    sort_order: int
    source_url: str


@dataclass(frozen=True, slots=True)
class LegacyMediaAsset:
    source_url: str
    source_path: str
    target_key: str
    content_type: str
    size_bytes: int
    checksum_sha256: str


@dataclass(frozen=True, slots=True)
class CatalogMigrationPlan:
    source_database: str
    source_uploads: str
    products: tuple[LegacyProductRecord, ...]
    variants: tuple[LegacyVariantRecord, ...]
    references: tuple[LegacyMediaReference, ...]
    assets: tuple[LegacyMediaAsset, ...]
    unused_upload_files: tuple[str, ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(
            self._fingerprint_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def report(self) -> dict[str, object]:
        payload = self._report_payload()
        payload["fingerprint_sha256"] = self.fingerprint
        return payload

    def _report_payload(self) -> dict[str, object]:
        return {
            "source_database": self.source_database,
            "source_uploads": self.source_uploads,
            "valid": self.valid,
            "counts": {
                "products": len(self.products),
                "variants": len(self.variants),
                "media_references": len(self.references),
                "unique_media_assets": len(self.assets),
                "unused_upload_files": len(self.unused_upload_files),
            },
            "assets": [asdict(asset) for asset in self.assets],
            "unused_upload_files": list(self.unused_upload_files),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }

    def _fingerprint_payload(self) -> dict[str, object]:
        return {
            "source_database": self.source_database,
            "source_uploads": self.source_uploads,
            "products": [asdict(product) for product in self.products],
            "variants": [asdict(variant) for variant in self.variants],
            "references": [asdict(reference) for reference in self.references],
            "assets": [asdict(asset) for asset in self.assets],
            "unused_upload_files": list(self.unused_upload_files),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class CatalogMigrationResult:
    fingerprint_sha256: str
    products: int
    variants: int
    media_assets: int
    media_references: int


@dataclass(frozen=True, slots=True)
class CatalogContractComparison:
    list_products: int
    detail_products: int
    mismatches: tuple[str, ...]

    @property
    def matches(self) -> bool:
        return not self.mismatches

    def report(self) -> dict[str, object]:
        return {
            "matches": self.matches,
            "list_products": self.list_products,
            "detail_products": self.detail_products,
            "mismatches": list(self.mismatches),
        }


class InvalidMigrationPlanError(RuntimeError):
    pass


class TargetCatalogNotEmptyError(RuntimeError):
    pass
