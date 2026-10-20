from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

CatalogSort = Literal["newest", "oldest", "cheap", "expensive"]
CatalogSource = Literal["garment_buro", "user"]
PositiveId = Annotated[int, Field(gt=0, le=2_147_483_647)]
Color = Annotated[str, Field(min_length=1, max_length=64)]
Price = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class StorefrontQuery(BaseModel):
    query: str = Field(default="", max_length=200)
    category_ids: list[PositiveId] = Field(default_factory=list, max_length=20)
    colors: list[Color] = Field(default_factory=list, max_length=20)
    source: CatalogSource | None = None
    min_price: Price | None = None
    max_price: Price | None = None
    sort: CatalogSort = "newest"
    ids: list[PositiveId] = Field(default_factory=list, max_length=100)
    limit: int = Field(default=24, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("min_price must not exceed max_price")
        return self


class StorefrontCardResponse(BaseModel):
    id: int
    title: str
    price: Decimal
    category_id: int | None
    category_name: str | None
    colors: list[str]
    tags: list[str]
    source: CatalogSource
    image_url: str | None = None
    image_alt: str | None = None


class StorefrontPageResponse(BaseModel):
    items: list[StorefrontCardResponse]
    next_cursor: str | None


class CollectionProductsQuery(BaseModel):
    ids: list[PositiveId] = Field(min_length=1, max_length=50)


class CollectionProductResponse(BaseModel):
    id: int
    title: str
    price: Decimal
    description: str | None
    image_url: str | None = None
    image_alt: str | None = None


class StorefrontCategoryResponse(BaseModel):
    id: int
    name: str


class StorefrontOptionsResponse(BaseModel):
    categories: list[StorefrontCategoryResponse]
    colors: list[str]
