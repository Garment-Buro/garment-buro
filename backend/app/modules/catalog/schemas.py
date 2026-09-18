from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProductCategoryWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, max_length=96, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    is_active: bool = True

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        return value.strip().casefold()

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ProductCategoryUpdate(ProductCategoryWrite):
    expected_version: int = Field(gt=0)


class ProductCategoryResponse(ProductCategoryWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int


class ProductVariantWriteRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    size: str | None = Field(default=None, max_length=32)
    garment_size_id: int | None = Field(default=None, gt=0)
    fabric_id: int | None = Field(default=None, gt=0)
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
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
    )
    category_id: int | None = Field(default=None, gt=0)
    garment_model_id: int | None = Field(default=None, gt=0)
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

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str | None) -> str | None:
        return value.strip().casefold() if value is not None else None

    @model_validator(mode="after")
    def validate_prices(self) -> ProductWriteRequest:
        if self.old_price is not None and self.old_price < self.price:
            raise ValueError("Old price must not be lower than the current price")
        return self


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
