from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    cart_items: list[CdekQuoteItem] = Field(min_length=1, max_length=MAX_CDEK_QUOTE_ITEMS)

    @field_validator("city")
    @classmethod
    def normalize_city(cls, value: str) -> str:
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("CDEK city contains control characters")
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("CDEK city must not be blank")
        return normalized


class CdekQuoteResponse(BaseModel):
    delivery_price: float
    period_min: int | None = None
    period_max: int | None = None
    tariff_code: int
    currency: Literal["RUB"] = "RUB"
