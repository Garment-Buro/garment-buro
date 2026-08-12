from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class LegacyOrderItemRecord:
    client_item_id: str
    product_id: int
    variant_id: int | None
    sku: str | None
    title: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal
    image_url: str
    size: str
    color: str
    customization: dict[str, object] | None
    sort_order: int


@dataclass(frozen=True, slots=True)
class LegacyOrderRecord:
    id: int
    email: str | None
    email_normalized: str | None
    phone: str | None
    first_name: str | None
    last_name: str | None
    patronymic: str | None
    delivery_city: str | None
    delivery_method: str | None
    delivery_address: str | None
    cdek_point_code: str | None
    payment_method: str | None
    items: tuple[LegacyOrderItemRecord, ...]
    raw_cart_items: str
    items_subtotal: Decimal
    delivery_price: Decimal
    total_price: Decimal
    status: str
    payment_status: str
    created_at: datetime
    payment_provider_id: str | None
    delivery_provider_uuid: str | None
    delivery_provider_number: str | None
    delivery_provider_status: str | None
    legacy_status: str | None
    legacy_payment_status: str | None
    source_row_sha256: str


@dataclass(frozen=True, slots=True)
class OrderMigrationPlan:
    source_database: str
    source_orders_count: int
    orders: tuple[LegacyOrderRecord, ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    synthetic_item_ids_count: int
    total_reconciliation_mismatches_count: int

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def fingerprint(self) -> str:
        canonical = {
            "format": "garment-buro-legacy-orders-v1",
            "orders": [asdict(order) for order in self.orders],
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }
        return hashlib.sha256(
            json.dumps(
                canonical,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()

    @property
    def items_count(self) -> int:
        return sum(len(order.items) for order in self.orders)

    @property
    def payment_references_count(self) -> int:
        return sum(order.payment_provider_id is not None for order in self.orders)

    @property
    def delivery_references_count(self) -> int:
        return sum(
            order.delivery_provider_uuid is not None or order.delivery_provider_number is not None
            for order in self.orders
        )

    def report(self) -> dict[str, object]:
        return {
            "source_database": self.source_database,
            "valid": self.valid,
            "fingerprint_sha256": self.fingerprint,
            "counts": {
                "source_orders": self.source_orders_count,
                "planned_orders": len(self.orders),
                "items": self.items_count,
                "payment_references": self.payment_references_count,
                "delivery_references": self.delivery_references_count,
                "synthetic_item_ids": self.synthetic_item_ids_count,
                "total_reconciliation_mismatches": (self.total_reconciliation_mismatches_count),
            },
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class OrderMigrationResult:
    fingerprint_sha256: str
    orders: int
    items: int
    payment_references: int
    delivery_references: int


class InvalidOrderMigrationPlanError(RuntimeError):
    pass


class TargetOrderStoreNotEmptyError(RuntimeError):
    pass
