from __future__ import annotations

import json
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_CART_ITEMS = 100
MAX_CART_PAYLOAD_BYTES = 512 * 1024
MAX_CUSTOMIZATION_BYTES = 64 * 1024


class CartItemWrite(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=255)
    product_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    image: str = Field(default="", max_length=4096)
    size: str = Field(default="", max_length=32)
    color: str = Field(default="", max_length=64)
    quantity: int = Field(ge=1, le=999)
    customization: dict[str, object] | None = None

    @field_validator("id", "title")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Cart item text must not be blank")
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
            raise ValueError("Cart customization must contain JSON values") from error
        if len(encoded) > MAX_CUSTOMIZATION_BYTES:
            raise ValueError("Cart item customization is too large")
        return value


class CartUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[CartItemWrite] = Field(default_factory=list, max_length=MAX_CART_ITEMS)
    updated_at_ms: int | None = Field(default=None, ge=0, le=9_999_999_999_999)

    @model_validator(mode="after")
    def validate_cart_payload(self) -> CartUpdateRequest:
        item_ids = [item.id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Cart item IDs must be unique")
        encoded = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > MAX_CART_PAYLOAD_BYTES:
            raise ValueError("Cart payload is too large")
        return self


class CartItemResponse(BaseModel):
    id: str
    product_id: int
    title: str
    price: float
    image: str
    size: str
    color: str
    quantity: int
    customization: dict[str, object] | None = None


class CartSnapshotResponse(BaseModel):
    cart_id: str
    items: list[CartItemResponse]
    updated_at_ms: int
    ttl_seconds: int


class CartUpdatedResponse(BaseModel):
    status: str = "ok"
    cart_id: str
    items_count: int
    updated_at_ms: int
    ttl_seconds: int


class CartDeletedResponse(BaseModel):
    status: str = "deleted"
    cart_id: str
