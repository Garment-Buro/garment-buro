from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.catalog.schemas import ProductDetailResponse, ProductVariantResponse


class CatalogAdminQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(default="", max_length=100)
    garment_model_id: int | None = Field(default=None, ge=1, le=2_147_483_647)
    category_id: int | None = Field(default=None, ge=1, le=2_147_483_647)
    community_id: int | None = Field(default=None, ge=1, le=2_147_483_647)
    active: bool | None = None
    source: Literal["all", "garment_buro", "user"] = "all"
    stock: Literal["all", "available", "empty"] = "all"
    sort: Literal[
        "id:asc",
        "id:desc",
        "title:asc",
        "title:desc",
        "price:asc",
        "price:desc",
        "stock:asc",
        "stock:desc",
        "variants:asc",
        "variants:desc",
    ] = "title:asc"
    limit: int = Field(default=24, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)

    @field_validator("query")
    @classmethod
    def trim_query(cls, value: str) -> str:
        return value.strip()


class CatalogAdminCommunity(BaseModel):
    id: int
    title: str
    slug: str


class CatalogAdminProduct(BaseModel):
    preset_source: Literal["garment_buro", "user"] = "garment_buro"
    tags: list[str] = Field(default_factory=list)
    id: int
    title: str
    slug: str | None
    category_id: int | None
    garment_model_id: int | None
    category_name: str | None
    garment_model_name: str | None
    price: Decimal
    old_price: Decimal | None
    image_url: str | None = None
    is_active: bool
    stock_quantity: int
    variant_count: int
    sku: str | None
    community_count: int | None
    communities: list[CatalogAdminCommunity] = Field(max_length=3)


class CatalogAdminPage(BaseModel):
    items: list[CatalogAdminProduct]
    next_cursor: str | None


class CatalogAdminCounts(BaseModel):
    garment_buro: int
    user: int
    communities: int | None


class CatalogAdminVariantDetail(ProductVariantResponse):
    sku: str | None
    garment_size_id: int | None
    fabric_id: int | None
    reserved_quantity: int
    available_stock_quantity: int


class CatalogAdminDetail(ProductDetailResponse):
    """Editable physical stock is separate from derived sellable capacity."""

    reserved_quantity: int
    available_stock_quantity: int
    variants: list[CatalogAdminVariantDetail]
