from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.delivery.constants import (
    CDEK_DELIVERY_METHODS,
    CDEK_PICKUP_DELIVERY_METHOD,
)
from app.modules.delivery.validation import normalize_cdek_phone

MAX_ORDER_ITEMS = 100
MAX_ORDER_PAYLOAD_BYTES = 512 * 1024
MAX_ORDER_CUSTOMIZATION_BYTES = 64 * 1024


class LegacyOrderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    email: str | None = None
    phone: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    patronymic: str | None = None
    delivery_city: str | None = None
    delivery_method: str | None = None
    delivery_address: str | None = None
    payment_method: str | None = None
    cart_items: str | None = None
    total_price: float | None = None
    status: str | None = None
    cdek_uuid: str | None = None
    cdek_point_code: str | None = None
    delivery_price: float | None = None
    payment_id: str | None = None
    payment_status: str | None = None
    created_at: datetime | None = None
    cdek_number: str | None = None
    cdek_status: str | None = None


class OrderLineCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=255)
    product_id: int = Field(gt=0)
    title: str = Field(default="", max_length=255)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    image: str = Field(default="", max_length=4096)
    size: str = Field(default="", max_length=32)
    color: str = Field(default="", max_length=64)
    quantity: int = Field(ge=1, le=999)
    customization: dict[str, object] | None = None

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Order item id must not be blank")
        return normalized

    @field_validator("customization")
    @classmethod
    def limit_customization(
        cls,
        value: dict[str, object] | None,
    ) -> dict[str, object] | None:
        if value is None:
            return None
        try:
            encoded = json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise ValueError("Order customization must contain JSON values") from error
        if len(encoded) > MAX_ORDER_CUSTOMIZATION_BYTES:
            raise ValueError("Order item customization is too large")
        return value


class OrderCreationCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str = Field(min_length=3, max_length=320)
    phone: str = Field(min_length=3, max_length=64)
    first_name: str = Field(min_length=1, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    patronymic: str | None = Field(default=None, max_length=255)
    delivery_city: str = Field(min_length=1, max_length=255)
    delivery_method: str = Field(min_length=1, max_length=64)
    delivery_address: str = Field(min_length=1, max_length=4096)
    cdek_point_code: str | None = Field(default=None, max_length=64)
    payment_method: str = Field(min_length=1, max_length=64)
    payment_capture_mode: Literal["automatic", "manual"] = "automatic"
    items: list[OrderLineCreate] = Field(min_length=1, max_length=MAX_ORDER_ITEMS)
    claimed_total_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    delivery_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency: Literal["RUB"] = "RUB"

    @field_validator(
        "email",
        "phone",
        "first_name",
        "delivery_city",
        "delivery_method",
        "delivery_address",
        "payment_method",
    )
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Required order text must not be blank")
        return normalized

    @field_validator("last_name", "patronymic", "cdek_point_code")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def validate_command(self) -> OrderCreationCommand:
        item_ids = [item.id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Order item IDs must be unique")
        if self.delivery_method in CDEK_DELIVERY_METHODS:
            try:
                normalize_cdek_phone(self.phone)
            except ValueError as error:
                raise ValueError("CDEK delivery requires a valid recipient phone") from error
        if self.delivery_method == CDEK_PICKUP_DELIVERY_METHOD and not self.cdek_point_code:
            raise ValueError("CDEK pickup delivery requires a pickup point code")
        encoded = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > MAX_ORDER_PAYLOAD_BYTES:
            raise ValueError("Order payload is too large")
        return self


class OrderCreationResult(BaseModel):
    order_id: int
    replayed: bool
    status: str
    payment_status: str
    items_subtotal: Decimal
    delivery_price: Decimal
    total_price: Decimal
    currency: Literal["RUB"]
    version: int
