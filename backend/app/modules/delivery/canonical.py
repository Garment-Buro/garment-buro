from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal

from app.core.config import Settings
from app.modules.delivery.constants import (
    CDEK_DELIVERY_METHODS,
    CDEK_DOOR_DELIVERY_METHOD,
    CDEK_PICKUP_DELIVERY_METHOD,
)
from app.modules.delivery.logistics import (
    CdekLogisticsValidationError,
    centimeters_to_integer,
    kilograms_to_grams,
)
from app.modules.delivery.validation import normalize_cdek_phone
from app.modules.orders.models import Order, OrderItem

CDEK_REQUEST_SCHEMA_VERSION = 1


class CdekRequestValidationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class CanonicalCdekRequest:
    body: bytes
    sha256: str
    client_order_number: str
    schema_version: int = CDEK_REQUEST_SCHEMA_VERSION

    def as_dict(self) -> dict[str, object]:
        payload = json.loads(self.body)
        if not isinstance(payload, dict):
            raise RuntimeError("Canonical CDEK request must decode to an object")
        return payload


class CdekCanonicalRequestBuilder:
    """Build one immutable CDEK v2 request from trusted order snapshots."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build(self, order: Order) -> CanonicalCdekRequest:
        if order.id is None or order.id <= 0:
            raise CdekRequestValidationError("cdek_order_not_persisted")
        if order.delivery_method not in CDEK_DELIVERY_METHODS:
            raise CdekRequestValidationError("cdek_delivery_method_invalid")
        if not order.items:
            raise CdekRequestValidationError("cdek_items_missing")

        packages_count = sum(item.quantity for item in order.items)
        if packages_count > self.settings.cdek_max_packages:
            raise CdekRequestValidationError("cdek_package_limit_exceeded")

        client_order_number = f"GB-{order.id:010d}"
        payload: dict[str, object] = {
            "type": 1,
            "number": client_order_number,
            "tariff_code": self._tariff(order.delivery_method),
            "items_cost_currency": order.currency,
            "recipient_currency": order.currency,
            "sender": {
                "name": self._required(self.settings.cdek_sender_name, "cdek_sender_missing")
            },
            "recipient": self._recipient(order),
            "from_location": {"code": self.settings.cdek_sender_city_code},
            "to_location": self._destination(order),
            "packages": self._packages(order.items, client_order_number),
        }
        if order.delivery_method == CDEK_PICKUP_DELIVERY_METHOD:
            payload["delivery_point"] = self._required(
                order.cdek_point_code,
                "cdek_pickup_point_missing",
            )

        body = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return CanonicalCdekRequest(
            body=body,
            sha256=hashlib.sha256(body).hexdigest(),
            client_order_number=client_order_number,
        )

    def _tariff(self, delivery_method: str) -> int:
        if delivery_method == CDEK_PICKUP_DELIVERY_METHOD:
            return self.settings.cdek_warehouse_to_warehouse_tariff
        if delivery_method == CDEK_DOOR_DELIVERY_METHOD:
            return self.settings.cdek_warehouse_to_door_tariff
        raise CdekRequestValidationError("cdek_delivery_method_invalid")

    @staticmethod
    def _recipient(order: Order) -> dict[str, object]:
        name = " ".join(
            value.strip()
            for value in (order.first_name, order.last_name, order.patronymic)
            if value and value.strip()
        )
        if not name:
            raise CdekRequestValidationError("cdek_recipient_missing")
        try:
            phone = normalize_cdek_phone(order.phone)
        except ValueError as error:
            raise CdekRequestValidationError("cdek_phone_invalid") from error
        recipient: dict[str, object] = {
            "name": name,
            "phones": [{"number": phone}],
        }
        if order.email_normalized:
            recipient["email"] = order.email_normalized
        return recipient

    @staticmethod
    def _destination(order: Order) -> dict[str, str]:
        return {
            "country_code": "RU",
            "city": CdekCanonicalRequestBuilder._required(
                order.delivery_city,
                "cdek_delivery_city_missing",
            ),
            "address": CdekCanonicalRequestBuilder._required(
                order.delivery_address,
                "cdek_delivery_address_missing",
            ),
        }

    @staticmethod
    def _packages(
        items: list[OrderItem],
        client_order_number: str,
    ) -> list[dict[str, object]]:
        packages: list[dict[str, object]] = []
        for item in sorted(items, key=lambda value: value.sort_order):
            weight = CdekCanonicalRequestBuilder._grams(item.delivery_weight_kg_snapshot)
            height = CdekCanonicalRequestBuilder._centimeters(item.delivery_height_cm_snapshot)
            width = CdekCanonicalRequestBuilder._centimeters(item.delivery_width_cm_snapshot)
            length = CdekCanonicalRequestBuilder._centimeters(item.delivery_length_cm_snapshot)
            ware_key = (item.sku_snapshot or f"product-{item.product_id_snapshot}").strip()
            if not ware_key:
                raise CdekRequestValidationError("cdek_ware_key_missing")
            for unit_index in range(item.quantity):
                packages.append(
                    {
                        "number": (
                            f"{client_order_number}-{item.sort_order + 1:03d}-{unit_index + 1:03d}"
                        ),
                        "weight": weight,
                        "length": length,
                        "width": width,
                        "height": height,
                        "items": [
                            {
                                "name": item.title_snapshot,
                                "ware_key": ware_key,
                                "payment": {"value": 0},
                                "cost": CdekCanonicalRequestBuilder._money(item.unit_price),
                                "amount": 1,
                                "weight": weight,
                            }
                        ],
                    }
                )
        return packages

    @staticmethod
    def _grams(value: Decimal | None) -> int:
        try:
            return kilograms_to_grams(value)
        except CdekLogisticsValidationError as error:
            raise CdekRequestValidationError(error.code) from error

    @staticmethod
    def _centimeters(value: Decimal | None) -> int:
        try:
            return centimeters_to_integer(value)
        except CdekLogisticsValidationError as error:
            raise CdekRequestValidationError(error.code) from error

    @staticmethod
    def _money(value: Decimal) -> int | float:
        normalized = value.quantize(Decimal("0.01"))
        if normalized < 0:
            raise CdekRequestValidationError("cdek_item_cost_invalid")
        if normalized == normalized.to_integral_value():
            return int(normalized)
        return float(normalized)

    @staticmethod
    def _required(value: str | None, error_code: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise CdekRequestValidationError(error_code)
        return normalized
