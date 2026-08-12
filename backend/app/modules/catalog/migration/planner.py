from __future__ import annotations

import hashlib
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from app.modules.catalog.migration.types import (
    CatalogMigrationPlan,
    LegacyMediaAsset,
    LegacyMediaReference,
    LegacyProductRecord,
    LegacyVariantRecord,
)
from app.modules.media.models import (
    ProductMediaRole,
    ProductVariantMediaRole,
)
from app.modules.media.service import prepare_catalog_media

PRODUCT_COLUMNS = (
    "id",
    "title",
    "price",
    "old_price",
    "video_src",
    "image_left",
    "image_right",
    "description",
    "composition",
    "model_info",
    "sizes",
    "colors",
    "gallery_images",
    "is_active",
    "type",
    "weight",
    "height",
    "width",
    "length",
    "stock_quantity",
    "size_chart_img_1",
    "size_chart_img_2",
    "desktop_video",
    "desktop_video_poster",
    "desktop_card_images",
    "desktop_slider_images",
    "mobile_card_image",
    "mobile_video_poster",
    "mobile_slider_images",
    "mobile_product_slider_images",
    "mobile_size_chart_first",
)
VARIANT_COLUMNS = (
    "id",
    "product_id",
    "size",
    "color",
    "color_hex",
    "stock_quantity",
    "width_cm",
    "height_cm",
    "preview_image",
    "images",
)
PRODUCT_MEDIA_FIELDS = tuple(role.value for role in ProductMediaRole)
VARIANT_MEDIA_FIELDS = tuple(role.value for role in ProductVariantMediaRole)


class LegacyCatalogPlanner:
    def build(self, database_path: Path, uploads_path: Path) -> CatalogMigrationPlan:
        database_path = database_path.expanduser().resolve()
        uploads_path = uploads_path.expanduser().resolve()
        errors: list[str] = []
        warnings: list[str] = []

        if not database_path.is_file():
            errors.append(f"Legacy database does not exist: {database_path}")
        if not uploads_path.is_dir():
            errors.append(f"Legacy uploads directory does not exist: {uploads_path}")
        if errors:
            return self._empty_plan(
                database_path,
                uploads_path,
                errors=errors,
                warnings=warnings,
            )

        products: list[LegacyProductRecord] = []
        variants: list[LegacyVariantRecord] = []
        references: list[LegacyMediaReference] = []
        source_urls: set[str] = set()

        try:
            with self._connect_readonly(database_path) as connection:
                schema_errors = self._validate_schema(connection)
                if schema_errors:
                    errors.extend(schema_errors)
                else:
                    product_rows = connection.execute(
                        f"SELECT {', '.join(PRODUCT_COLUMNS)} FROM products ORDER BY id"
                    ).fetchall()
                    variant_rows = connection.execute(
                        f"SELECT {', '.join(VARIANT_COLUMNS)} "
                        "FROM product_variants ORDER BY product_id, id"
                    ).fetchall()
                    products = [self._product(row) for row in product_rows]
                    variants = [self._variant(row) for row in variant_rows]
                    references.extend(
                        self._media_references(
                            product_rows,
                            owner_type="product",
                            fields=PRODUCT_MEDIA_FIELDS,
                        )
                    )
                    references.extend(
                        self._media_references(
                            variant_rows,
                            owner_type="variant",
                            fields=VARIANT_MEDIA_FIELDS,
                        )
                    )
                    source_urls = {reference.source_url for reference in references}
                    errors.extend(self._validate_domain(products, variants))
                    errors.extend(self._validate_media_cardinality(references))
        except sqlite3.Error as error:
            errors.append(f"Unable to read legacy SQLite database: {error}")

        assets: list[LegacyMediaAsset] = []
        for source_url in sorted(source_urls):
            try:
                assets.append(self._inspect_asset(source_url, uploads_path))
            except (OSError, ValueError) as error:
                errors.append(f"{source_url}: {error}")

        referenced_filenames = {Path(asset.source_path).name for asset in assets}
        upload_files = {path.name for path in uploads_path.iterdir() if path.is_file()}
        unused_upload_files = tuple(sorted(upload_files - referenced_filenames))
        if unused_upload_files:
            warnings.append(
                f"{len(unused_upload_files)} upload files are not referenced by catalog rows"
            )

        return CatalogMigrationPlan(
            source_database=str(database_path),
            source_uploads=str(uploads_path),
            products=tuple(products),
            variants=tuple(variants),
            references=tuple(
                sorted(
                    references,
                    key=lambda item: (
                        item.owner_type,
                        item.owner_id,
                        item.role,
                        item.sort_order,
                    ),
                )
            ),
            assets=tuple(sorted(assets, key=lambda item: item.source_url)),
            unused_upload_files=unused_upload_files,
            errors=tuple(sorted(errors)),
            warnings=tuple(sorted(warnings)),
        )

    @staticmethod
    def _connect_readonly(database_path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(
            f"{database_path.as_uri()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _validate_schema(connection: sqlite3.Connection) -> list[str]:
        errors: list[str] = []
        for table, expected in (
            ("products", set(PRODUCT_COLUMNS)),
            ("product_variants", set(VARIANT_COLUMNS)),
        ):
            actual = {
                row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
            }
            missing = sorted(expected - actual)
            if missing:
                errors.append(f"Legacy table {table} is missing columns: {', '.join(missing)}")
        return errors

    @staticmethod
    def _product(row: sqlite3.Row) -> LegacyProductRecord:
        return LegacyProductRecord(
            id=int(row["id"]),
            title=str(row["title"] or ""),
            price=_decimal(row["price"]),
            old_price=_optional_decimal(row["old_price"]),
            description=row["description"],
            composition=row["composition"],
            model_info=row["model_info"],
            sizes=tuple(_split_csv(row["sizes"])),
            colors=tuple(_split_csv(row["colors"])),
            is_active=bool(row["is_active"]),
            product_type=str(row["type"] or "normal"),
            weight_kg=_decimal(row["weight"]),
            height_cm=_decimal(row["height"]),
            width_cm=_decimal(row["width"]),
            length_cm=_decimal(row["length"]),
            stock_quantity=int(row["stock_quantity"] or 0),
        )

    @staticmethod
    def _variant(row: sqlite3.Row) -> LegacyVariantRecord:
        return LegacyVariantRecord(
            id=int(row["id"]),
            product_id=int(row["product_id"]),
            size=row["size"],
            color=row["color"],
            color_hex=row["color_hex"],
            stock_quantity=int(row["stock_quantity"] or 0),
            width_cm=_optional_decimal(row["width_cm"]),
            height_cm=_optional_decimal(row["height_cm"]),
        )

    @staticmethod
    def _media_references(
        rows: list[sqlite3.Row],
        *,
        owner_type: Literal["product", "variant"],
        fields: tuple[str, ...],
    ) -> list[LegacyMediaReference]:
        references: list[LegacyMediaReference] = []
        for row in rows:
            for field in fields:
                for sort_order, source_url in enumerate(_split_csv(row[field])):
                    references.append(
                        LegacyMediaReference(
                            owner_type=owner_type,
                            owner_id=int(row["id"]),
                            role=field,
                            sort_order=sort_order,
                            source_url=source_url,
                        )
                    )
        return references

    @staticmethod
    def _validate_domain(
        products: list[LegacyProductRecord],
        variants: list[LegacyVariantRecord],
    ) -> list[str]:
        errors: list[str] = []
        product_ids = {product.id for product in products}
        variant_identities: set[tuple[int, str | None, str | None]] = set()
        for product in products:
            if not product.title.strip():
                errors.append(f"Product {product.id} has an empty title")
            if product.price < 0 or product.stock_quantity < 0:
                errors.append(f"Product {product.id} has negative price or stock")
            if any(
                value < 0
                for value in (
                    product.weight_kg,
                    product.height_cm,
                    product.width_cm,
                    product.length_cm,
                )
            ):
                errors.append(f"Product {product.id} has negative dimensions")
        for variant in variants:
            if variant.product_id not in product_ids:
                errors.append(
                    f"Variant {variant.id} references missing product {variant.product_id}"
                )
            identity = (variant.product_id, variant.size, variant.color)
            if identity in variant_identities:
                errors.append(
                    "Duplicate variant identity: "
                    f"product={variant.product_id}, size={variant.size}, color={variant.color}"
                )
            variant_identities.add(identity)
            if variant.stock_quantity < 0:
                errors.append(f"Variant {variant.id} has negative stock")
            if variant.width_cm is not None and variant.width_cm < 0:
                errors.append(f"Variant {variant.id} has negative width")
            if variant.height_cm is not None and variant.height_cm < 0:
                errors.append(f"Variant {variant.id} has negative height")
        return errors

    @staticmethod
    def _validate_media_cardinality(
        references: list[LegacyMediaReference],
    ) -> list[str]:
        multi_roles = {
            ProductMediaRole.GALLERY_IMAGES.value,
            ProductMediaRole.DESKTOP_CARD_IMAGES.value,
            ProductMediaRole.DESKTOP_SLIDER_IMAGES.value,
            ProductMediaRole.MOBILE_SLIDER_IMAGES.value,
            ProductMediaRole.MOBILE_PRODUCT_SLIDER_IMAGES.value,
            ProductVariantMediaRole.IMAGES.value,
        }
        counts: dict[tuple[str, int, str], int] = {}
        for reference in references:
            key = (reference.owner_type, reference.owner_id, reference.role)
            counts[key] = counts.get(key, 0) + 1
        return [
            f"Scalar media role has multiple values: {owner_type}={owner_id}, role={role}"
            for (owner_type, owner_id, role), count in sorted(counts.items())
            if role not in multi_roles and count > 1
        ]

    @staticmethod
    def _inspect_asset(source_url: str, uploads_path: Path) -> LegacyMediaAsset:
        parsed = urlsplit(source_url)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("external and parameterized media URLs require manual mapping")
        if not parsed.path.startswith("/uploads/"):
            raise ValueError("media URL is outside /uploads/")

        filename = parsed.path.removeprefix("/uploads/")
        if not filename or filename != Path(filename).name:
            raise ValueError("nested or unsafe upload path")

        upload_root = uploads_path.resolve()
        source_path = (upload_root / filename).resolve()
        if source_path.parent != upload_root:
            raise ValueError("upload resolves outside the source directory")
        if not source_path.is_file():
            raise ValueError("referenced upload file is missing")

        prepared = prepare_catalog_media(source_path.read_bytes())
        return LegacyMediaAsset(
            source_url=source_url,
            source_path=str(source_path),
            target_key=f"uploads/{filename}",
            content_type=prepared.content_type,
            size_bytes=len(prepared.data),
            checksum_sha256=hashlib.sha256(prepared.data).hexdigest(),
        )

    @staticmethod
    def _empty_plan(
        database_path: Path,
        uploads_path: Path,
        *,
        errors: list[str],
        warnings: list[str],
    ) -> CatalogMigrationPlan:
        return CatalogMigrationPlan(
            source_database=str(database_path),
            source_uploads=str(uploads_path),
            products=(),
            variants=(),
            references=(),
            assets=(),
            unused_upload_files=(),
            errors=tuple(errors),
            warnings=tuple(warnings),
        )


def _split_csv(value: object | None) -> list[str]:
    if value is None:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _decimal(value: object | None) -> Decimal:
    return Decimal(str(value if value is not None else 0))


def _optional_decimal(value: object | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None
