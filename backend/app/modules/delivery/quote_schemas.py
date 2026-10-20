from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_CDEK_QUOTE_ITEMS = 100
MAX_CDEK_QUOTE_PAYLOAD_BYTES = 64 * 1024


class CdekQuoteItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    product_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=999)


class CdekQuoteRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    city: str = Field(min_length=1, max_length=255)
    delivery_method: Literal["cdek_pickup", "cdek_door"]
    delivery_address: str = Field(default="", max_length=4096)
    cdek_point_code: str | None = Field(default=None, max_length=64)
    cart_items: list[CdekQuoteItem] = Field(min_length=1, max_length=MAX_CDEK_QUOTE_ITEMS)

    @field_validator("city", "delivery_address")
    @classmethod
    def normalize_city(cls, value: str) -> str:
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("CDEK city contains control characters")
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("CDEK city must not be blank")
        return normalized

    @field_validator("cdek_point_code")
    @classmethod
    def normalize_point_code(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def require_destination(self) -> CdekQuoteRequest:
        if self.delivery_method == "cdek_pickup" and not self.cdek_point_code:
            raise ValueError("Pickup delivery requires a point code")
        if self.delivery_method == "cdek_door" and not self.delivery_address:
            raise ValueError("Courier delivery requires an address")
        return self


class CdekQuoteResponse(BaseModel):
    delivery_price: float
    quote_token: str
    delivery_city: str
    delivery_address: str
    cdek_point_code: str | None
    period_min: int | None = None
    period_max: int | None = None
    tariff_code: int
    currency: Literal["RUB"] = "RUB"
