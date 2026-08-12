from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductVariantWriteRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    size: str | None = Field(default=None, max_length=32)
    color: str | None = Field(default=None, max_length=64)
    color_hex: str | None = Field(default=None, max_length=7)
    stock_quantity: int = Field(default=0, ge=0)
    width_cm: Decimal | None = Field(default=None, ge=0)
    height_cm: Decimal | None = Field(default=None, ge=0)
    preview_image: str | None = Field(default=None, max_length=4096)
    images: str | None = Field(default=None, max_length=32768)


class ProductWriteRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    title: str = Field(min_length=1, max_length=255)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    old_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    video_src: str | None = Field(default=None, max_length=4096)
    image_left: str | None = Field(default=None, max_length=4096)
    image_right: str | None = Field(default=None, max_length=4096)
    description: str | None = None
    composition: str | None = None
    model_info: str | None = None
    sizes: str = Field(default="S,M,L,XL", max_length=2048)
    colors: str = Field(default="black,white", max_length=4096)
    gallery_images: str | None = Field(default=None, max_length=32768)
    is_active: bool = True
    product_type: str = Field(default="normal", alias="type", max_length=64)
    weight: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=3)
    height: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    width: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    length: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    stock_quantity: int = Field(default=0, ge=0)
    size_chart_img_1: str | None = Field(default=None, max_length=4096)
    size_chart_img_2: str | None = Field(default=None, max_length=4096)
    desktop_video: str | None = Field(default=None, max_length=4096)
    desktop_video_poster: str | None = Field(default=None, max_length=4096)
    desktop_card_images: str | None = Field(default=None, max_length=32768)
    desktop_slider_images: str | None = Field(default=None, max_length=32768)
    mobile_card_image: str | None = Field(default=None, max_length=4096)
    mobile_video_poster: str | None = Field(default=None, max_length=4096)
    mobile_slider_images: str | None = Field(default=None, max_length=32768)
    mobile_product_slider_images: str | None = Field(default=None, max_length=32768)
    mobile_size_chart_first: str | None = Field(default=None, max_length=4096)
    variants: list[ProductVariantWriteRequest] = Field(default_factory=list, max_length=200)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Product title must not be blank")
        return normalized


class ProductDeletedResponse(BaseModel):
    status: str = "deleted"


class ProductVariantResponse(BaseModel):
    id: int
    product_id: int
    size: str | None
    color: str | None
    color_hex: str | None
    stock_quantity: int
    width_cm: float | None
    height_cm: float | None
    preview_image: str | None
    images: str | None


class ProductResponse(BaseModel):
    id: int
    title: str
    price: float
    old_price: float | None
    video_src: str | None
    image_left: str | None
    image_right: str | None
    description: str | None
    composition: str | None
    model_info: str | None
    sizes: str
    colors: str
    gallery_images: str | None
    is_active: bool
    type: str
    weight: float
    height: float
    width: float
    length: float
    stock_quantity: int
    size_chart_img_1: str | None
    size_chart_img_2: str | None
    desktop_video: str | None
    desktop_video_poster: str | None
    desktop_card_images: str | None
    desktop_slider_images: str | None
    mobile_card_image: str | None
    mobile_video_poster: str | None
    mobile_slider_images: str | None
    mobile_product_slider_images: str | None
    mobile_size_chart_first: str | None


class ProductDetailResponse(ProductResponse):
    variants: list[ProductVariantResponse]
