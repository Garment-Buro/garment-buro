from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

PartnerState = Literal["invited", "active", "suspended"]
LandingState = Literal["draft", "published", "archived"]
PayoutState = Literal["requested", "approved", "paid", "rejected", "canceled"]


class PartnerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    code: str
    display_name: str
    status: PartnerState
    commission_bps: int
    created_at: datetime


class PartnerCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    code: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]+$")
    display_name: str = Field(min_length=1, max_length=255)
    commission_bps: int = Field(ge=0, le=10_000)
    status: PartnerState = "invited"

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().casefold()

    @field_validator("email")
    @classmethod
    def normalize_email_input(cls, value: str) -> str:
        return value.strip()

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        return value.strip()


class PartnerUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    commission_bps: int | None = Field(default=None, ge=0, le=10_000)
    status: PartnerState | None = None

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class PartnerLandingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    eyebrow: str | None
    headline: str
    description: str
    cta_label: str
    cta_href: str
    image_url: str | None
    product_ids: list[int]
    status: LandingState
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PublicPartnerLandingResponse(BaseModel):
    slug: str
    partner_name: str
    title: str
    eyebrow: str | None
    headline: str
    description: str
    cta_label: str
    cta_href: str
    image_url: str | None
    product_ids: list[int]


class PartnerLandingCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=3, max_length=96, pattern=r"^[a-z0-9][a-z0-9-]+$")
    title: str = Field(min_length=1, max_length=255)
    eyebrow: str | None = Field(default=None, max_length=120)
    headline: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=4000)
    cta_label: str = Field(min_length=1, max_length=80)
    cta_href: str = Field(min_length=1, max_length=2048)
    image_url: str | None = Field(default=None, max_length=4096)
    product_ids: list[int] = Field(default_factory=list, max_length=50)
    status: LandingState = "draft"

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        return value.strip().casefold()

    @field_validator("title", "headline", "description", "cta_label", "cta_href")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("cta_href")
    @classmethod
    def validate_cta_href(cls, value: str) -> str:
        if value.startswith("/") and not value.startswith("//"):
            return value
        parsed = urlsplit(value)
        if parsed.scheme == "https" and parsed.hostname in {
            "garment-buro.ru",
            "www.garment-buro.ru",
        }:
            return value
        raise ValueError("CTA URL must point to GARMENT BURO")

    @field_validator("eyebrow", "image_url")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, value: str | None) -> str | None:
        if value is None or (value.startswith("/") and not value.startswith("//")):
            return value
        parsed = urlsplit(value)
        if parsed.scheme == "https" and parsed.hostname:
            return value
        raise ValueError("Image URL must be a relative path or an HTTPS URL")

    @field_validator("product_ids")
    @classmethod
    def validate_product_ids(cls, value: list[int]) -> list[int]:
        if any(product_id <= 0 for product_id in value):
            raise ValueError("Product IDs must be positive")
        if len(value) != len(set(value)):
            raise ValueError("Product IDs must be unique")
        return value


class PartnerVisitResponse(BaseModel):
    attributed: bool = True


class PartnerDashboardResponse(BaseModel):
    partner: PartnerProfileResponse
    visits: int
    orders: int
    conversion_percent: Decimal
    earned: Decimal
    available: Decimal
    paid: Decimal
    currency: Literal["RUB"] = "RUB"


class PartnerCommissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    amount: Decimal
    currency: Literal["RUB"]
    status: Literal["pending", "canceled"]
    available_at: datetime
    created_at: datetime


class PartnerPayoutCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class PartnerPayoutReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["approved", "paid", "rejected", "canceled"]
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class PartnerPayoutResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: Decimal
    currency: Literal["RUB"]
    status: PayoutState
    reviewed_at: datetime | None
    paid_at: datetime | None
    note: str | None
    created_at: datetime
