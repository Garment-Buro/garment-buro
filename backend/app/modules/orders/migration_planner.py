from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.modules.identity.exceptions import InvalidEmailError
from app.modules.identity.security import normalize_email
from app.modules.orders.legacy import ORDER_COLUMNS
from app.modules.orders.migration_types import (
    LegacyOrderItemRecord,
    LegacyOrderRecord,
    OrderMigrationPlan,
)
from app.modules.orders.models import OrderPaymentStatus, OrderStatus

MONEY_QUANTUM = Decimal("0.01")
MAX_MONEY = Decimal("9999999999.99")
VALID_ORDER_STATUSES = {status.value for status in OrderStatus}
VALID_PAYMENT_STATUSES = {status.value for status in OrderPaymentStatus}


@dataclass(slots=True)
class _PlannerStats:
    synthetic_item_ids: int = 0
    total_mismatches: int = 0
    invalid_emails: int = 0
    missing_delivery_prices: int = 0
    defaulted_quantities: int = 0
    normalized_statuses: int = 0


class LegacyOrderPlanner:
    def build(self, database_path: Path) -> OrderMigrationPlan:
        database_path = database_path.expanduser().resolve()
        errors: list[str] = []
        records: list[LegacyOrderRecord] = []
        stats = _PlannerStats()
        source_orders_count = 0

        if not database_path.is_file():
            errors.append(f"Legacy database does not exist: {database_path}")
            return self._plan(database_path, 0, records, errors, stats)

        try:
            with self._connect_readonly(database_path) as connection:
                connection.execute("BEGIN")
                available = {
                    str(row["name"])
                    for row in connection.execute("PRAGMA table_info(orders)").fetchall()
                }
                missing = sorted(set(ORDER_COLUMNS) - available)
                if missing:
                    errors.append("Legacy table orders is missing columns: " + ", ".join(missing))
                else:
                    rows = connection.execute(
                        f"SELECT {', '.join(ORDER_COLUMNS)} FROM orders ORDER BY id"  # noqa: S608
                    ).fetchall()
                    source_orders_count = len(rows)
                    for row in rows:
                        record, row_errors = self._record(row, stats)
                        errors.extend(row_errors)
                        if record is not None:
                            records.append(record)
                connection.rollback()
        except sqlite3.Error as error:
            errors.append(f"Unable to read legacy SQLite database: {error}")

        return self._plan(
            database_path,
            source_orders_count,
            records,
            errors,
            stats,
        )

    @staticmethod
    def _connect_readonly(database_path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        return connection

    def _record(
        self,
        row: sqlite3.Row,
        stats: _PlannerStats,
    ) -> tuple[LegacyOrderRecord | None, list[str]]:
        errors: list[str] = []
        order_id = _positive_int(row["id"], "Order ID", errors)
        if order_id is None:
            return None, errors

        raw_cart_items = str(row["cart_items"] or "")
        items = self._items(raw_cart_items, order_id, errors, stats)
        total_price = _required_money(row["total_price"], order_id, "total price", errors)
        delivery_price = _optional_money(row["delivery_price"], order_id, "delivery price", errors)
        if delivery_price is None:
            delivery_price = Decimal("0.00")
            stats.missing_delivery_prices += 1

        items_subtotal: Decimal | None = None
        if total_price is not None:
            items_subtotal = (total_price - delivery_price).quantize(MONEY_QUANTUM)
            if items_subtotal < 0:
                errors.append(f"Order {order_id} has delivery price above total price")
            elif items is not None:
                line_sum = sum(
                    (item.line_total for item in items),
                    start=Decimal("0.00"),
                ).quantize(MONEY_QUANTUM)
                if line_sum != items_subtotal:
                    stats.total_mismatches += 1

        status = _status(
            row["status"],
            order_id,
            "status",
            OrderStatus.NEW.value,
            VALID_ORDER_STATUSES,
            errors,
            stats,
        )
        payment_status = _status(
            row["payment_status"],
            order_id,
            "payment status",
            OrderPaymentStatus.PENDING.value,
            VALID_PAYMENT_STATUSES,
            errors,
            stats,
        )
        created_at = _created_at(row["created_at"], order_id, errors)

        email = _optional_text(row["email"], 320, order_id, "email", errors)
        email_normalized: str | None = None
        if email is not None:
            try:
                email, email_normalized = normalize_email(email)
            except InvalidEmailError:
                stats.invalid_emails += 1

        phone = _optional_text(row["phone"], 64, order_id, "phone", errors)
        first_name = _optional_text(row["first_name"], 255, order_id, "first name", errors)
        last_name = _optional_text(row["last_name"], 255, order_id, "last name", errors)
        patronymic = _optional_text(row["patronymic"], 255, order_id, "patronymic", errors)
        delivery_city = _optional_text(row["delivery_city"], 255, order_id, "delivery city", errors)
        delivery_method = _optional_text(
            row["delivery_method"], 64, order_id, "delivery method", errors
        )
        delivery_address = _optional_text(
            row["delivery_address"], 4096, order_id, "delivery address", errors
        )
        cdek_point_code = _optional_text(
            row["cdek_point_code"], 64, order_id, "CDEK point code", errors
        )
        payment_method = _optional_text(
            row["payment_method"], 64, order_id, "payment method", errors
        )
        payment_provider_id = _optional_text(
            row["payment_id"], 255, order_id, "payment provider ID", errors
        )
        delivery_provider_uuid = _optional_text(
            row["cdek_uuid"], 255, order_id, "CDEK UUID", errors
        )
        delivery_provider_number = _optional_text(
            row["cdek_number"], 255, order_id, "CDEK number", errors
        )
        delivery_provider_status = _optional_text(
            row["cdek_status"], 255, order_id, "CDEK status", errors
        )

        source_row_sha256 = _source_row_sha256(row)
        if errors or items is None or total_price is None or items_subtotal is None:
            return None, errors

        return (
            LegacyOrderRecord(
                id=order_id,
                email=email,
                email_normalized=email_normalized,
                phone=phone,
                first_name=first_name,
                last_name=last_name,
                patronymic=patronymic,
                delivery_city=delivery_city,
                delivery_method=delivery_method,
                delivery_address=delivery_address,
                cdek_point_code=cdek_point_code,
                payment_method=payment_method,
                items=items,
                raw_cart_items=raw_cart_items,
                items_subtotal=items_subtotal,
                delivery_price=delivery_price,
                total_price=total_price,
                status=status,
                payment_status=payment_status,
                created_at=created_at,
                payment_provider_id=payment_provider_id,
                delivery_provider_uuid=delivery_provider_uuid,
                delivery_provider_number=delivery_provider_number,
                delivery_provider_status=delivery_provider_status,
                legacy_status=_raw_optional_text(row["status"]),
                legacy_payment_status=_raw_optional_text(row["payment_status"]),
                source_row_sha256=source_row_sha256,
            ),
            errors,
        )

    def _items(
        self,
        raw_cart_items: str,
        order_id: int,
        errors: list[str],
        stats: _PlannerStats,
    ) -> tuple[LegacyOrderItemRecord, ...] | None:
        try:
            raw_items = json.loads(raw_cart_items)
        except json.JSONDecodeError:
            errors.append(f"Order {order_id} has invalid cart JSON")
            return None
        if not isinstance(raw_items, list) or not raw_items:
            errors.append(f"Order {order_id} cart must be a non-empty array")
            return None

        records: list[LegacyOrderItemRecord] = []
        used_ids: set[str] = set()
        for index, raw_item in enumerate(raw_items):
            position = index + 1
            if not isinstance(raw_item, dict):
                errors.append(f"Order {order_id} item {position} must be an object")
                continue
            product_id = _positive_int(
                raw_item.get("product_id"),
                f"Order {order_id} item {position} product ID",
                errors,
            )
            variant_id = _optional_positive_int(
                raw_item.get("variant_id"),
                f"Order {order_id} item {position} variant ID",
                errors,
            )
            unit_price = _required_money(
                raw_item.get("price"),
                order_id,
                f"item {position} price",
                errors,
            )
            quantity = _quantity(raw_item.get("quantity"), order_id, position, errors)
            if raw_item.get("quantity") is None:
                stats.defaulted_quantities += 1
            customization = raw_item.get("customization")
            if customization is not None and not isinstance(customization, dict):
                errors.append(f"Order {order_id} item {position} customization must be an object")
                customization = None

            client_item_id = _client_item_id(
                raw_item.get("id"),
                order_id=order_id,
                position=position,
                used_ids=used_ids,
            )
            if client_item_id.synthetic:
                stats.synthetic_item_ids += 1

            title = _item_text(raw_item.get("title"), 255, order_id, position, "title", errors)
            image_url = _item_text(raw_item.get("image"), 4096, order_id, position, "image", errors)
            size = _item_text(raw_item.get("size"), 32, order_id, position, "size", errors)
            color = _item_text(raw_item.get("color"), 64, order_id, position, "color", errors)
            sku = _optional_item_text(raw_item.get("sku"), 100, order_id, position, "SKU", errors)
            if product_id is None or unit_price is None or quantity is None:
                continue
            records.append(
                LegacyOrderItemRecord(
                    client_item_id=client_item_id.value,
                    product_id=product_id,
                    variant_id=variant_id,
                    sku=sku,
                    title=title,
                    unit_price=unit_price,
                    quantity=quantity,
                    line_total=(unit_price * quantity).quantize(MONEY_QUANTUM),
                    image_url=image_url,
                    size=size,
                    color=color,
                    customization=customization,
                    sort_order=index,
                )
            )
        return tuple(records)

    @staticmethod
    def _plan(
        database_path: Path,
        source_orders_count: int,
        records: list[LegacyOrderRecord],
        errors: list[str],
        stats: _PlannerStats,
    ) -> OrderMigrationPlan:
        warnings: list[str] = []
        if stats.invalid_emails:
            warnings.append(
                f"{stats.invalid_emails} invalid legacy emails will not be eligible for ownership"
            )
        if stats.missing_delivery_prices:
            warnings.append(
                f"{stats.missing_delivery_prices} missing delivery prices will be imported as zero"
            )
        if stats.defaulted_quantities:
            warnings.append(
                f"{stats.defaulted_quantities} missing item quantities will be imported as one"
            )
        if stats.synthetic_item_ids:
            warnings.append(
                f"{stats.synthetic_item_ids} missing or duplicate item IDs will use stable synthetic IDs"
            )
        if stats.total_mismatches:
            warnings.append(
                f"{stats.total_mismatches} order totals differ from item snapshots; "
                "legacy order totals remain authoritative"
            )
        if stats.normalized_statuses:
            warnings.append(
                f"{stats.normalized_statuses} missing or case-variant statuses were normalized"
            )
        return OrderMigrationPlan(
            source_database=str(database_path),
            source_orders_count=source_orders_count,
            orders=tuple(records),
            errors=tuple(sorted(set(errors))),
            warnings=tuple(sorted(warnings)),
            synthetic_item_ids_count=stats.synthetic_item_ids,
            total_reconciliation_mismatches_count=stats.total_mismatches,
        )


@dataclass(frozen=True, slots=True)
class _ClientItemId:
    value: str
    synthetic: bool


def _client_item_id(
    value: object | None,
    *,
    order_id: int,
    position: int,
    used_ids: set[str],
) -> _ClientItemId:
    candidate = str(value).strip() if value is not None else ""
    synthetic = not candidate or len(candidate) > 255 or candidate in used_ids
    if synthetic:
        candidate = f"legacy-{order_id}-{position}"
        suffix = 1
        while candidate in used_ids:
            suffix += 1
            candidate = f"legacy-{order_id}-{position}-{suffix}"
    used_ids.add(candidate)
    return _ClientItemId(candidate, synthetic)


def _positive_int(
    value: object | None,
    label: str,
    errors: list[str],
) -> int | None:
    if isinstance(value, bool):
        errors.append(f"{label} is invalid")
        return None
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        errors.append(f"{label} is invalid")
        return None
    if parsed <= 0 or Decimal(str(value)) != parsed:
        errors.append(f"{label} must be a positive integer")
        return None
    return parsed


def _optional_positive_int(
    value: object | None,
    label: str,
    errors: list[str],
) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return _positive_int(value, label, errors)


def _quantity(
    value: object | None,
    order_id: int,
    position: int,
    errors: list[str],
) -> int | None:
    if value is None:
        return 1
    quantity = _positive_int(
        value,
        f"Order {order_id} item {position} quantity",
        errors,
    )
    if quantity is not None and quantity > 999:
        errors.append(f"Order {order_id} item {position} quantity exceeds 999")
        return None
    return quantity


def _required_money(
    value: object | None,
    order_id: int,
    label: str,
    errors: list[str],
) -> Decimal | None:
    if value is None or str(value).strip() == "":
        errors.append(f"Order {order_id} has no {label}")
        return None
    return _money(value, order_id, label, errors)


def _optional_money(
    value: object | None,
    order_id: int,
    label: str,
    errors: list[str],
) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    return _money(value, order_id, label, errors)


def _money(
    value: object,
    order_id: int,
    label: str,
    errors: list[str],
) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
        if not parsed.is_finite():
            raise InvalidOperation
        normalized = parsed.quantize(MONEY_QUANTUM)
    except (InvalidOperation, ValueError):
        errors.append(f"Order {order_id} has invalid {label}")
        return None
    if normalized < 0 or normalized > MAX_MONEY:
        errors.append(f"Order {order_id} has out-of-range {label}")
        return None
    if normalized != parsed:
        errors.append(f"Order {order_id} {label} has more than two decimal places")
        return None
    return normalized


def _status(
    value: object | None,
    order_id: int,
    label: str,
    default: str,
    allowed: set[str],
    errors: list[str],
    stats: _PlannerStats,
) -> str:
    raw = str(value).strip() if value is not None else ""
    normalized = raw.lower() or default
    if normalized not in allowed:
        errors.append(f"Order {order_id} has unsupported {label}")
        return default
    if normalized != raw:
        stats.normalized_statuses += 1
    return normalized


def _created_at(
    value: object | None,
    order_id: int,
    errors: list[str],
) -> datetime:
    if value is None or str(value).strip() == "":
        errors.append(f"Order {order_id} has no creation timestamp")
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        errors.append(f"Order {order_id} has an invalid creation timestamp")
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _optional_text(
    value: object | None,
    max_length: int,
    order_id: int,
    label: str,
    errors: list[str],
) -> str | None:
    normalized = _raw_optional_text(value)
    if normalized is not None and len(normalized) > max_length:
        errors.append(f"Order {order_id} {label} exceeds {max_length} characters")
        return None
    return normalized


def _item_text(
    value: object | None,
    max_length: int,
    order_id: int,
    position: int,
    label: str,
    errors: list[str],
) -> str:
    normalized = str(value) if value is not None else ""
    if len(normalized) > max_length:
        errors.append(f"Order {order_id} item {position} {label} exceeds {max_length} characters")
        return ""
    return normalized


def _optional_item_text(
    value: object | None,
    max_length: int,
    order_id: int,
    position: int,
    label: str,
    errors: list[str],
) -> str | None:
    normalized = _raw_optional_text(value)
    if normalized is not None and len(normalized) > max_length:
        errors.append(f"Order {order_id} item {position} {label} exceeds {max_length} characters")
        return None
    return normalized


def _raw_optional_text(value: object | None) -> str | None:
    normalized = str(value).strip() if value is not None else ""
    return normalized or None


def _source_row_sha256(row: sqlite3.Row) -> str:
    canonical = {column: row[column] for column in ORDER_COLUMNS}
    return hashlib.sha256(
        json.dumps(
            canonical,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
