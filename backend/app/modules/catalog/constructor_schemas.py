"""Public constructor data, independent of the preset editor and landing DTO."""

from typing import Literal

from pydantic import BaseModel


class ConstructorMedia(BaseModel):
    id: int
    url: str
    content_type: Literal["image/jpeg", "image/png", "image/webp"]


class ConstructorImage(BaseModel):
    media_id: int
    role: str
    sort_order: int


class ConstructorVariant(BaseModel):
    id: int
    size: str | None
    color: str | None
    color_hex: str | None
    stock_quantity: int
    width_cm: float | None
    height_cm: float | None
    images: list[ConstructorImage]


class ConstructorProductResponse(BaseModel):
    schema_version: Literal[1] = 1
    id: int
    title: str
    price: float
    stock_quantity: int
    sizes: list[str]
    images: list[ConstructorImage]
    variants: list[ConstructorVariant]
    media_assets: list[ConstructorMedia]
