from __future__ import annotations

import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,63}$")


def _code(value: str) -> str:
    normalized = value.strip().upper()
    if not CODE_PATTERN.fullmatch(normalized):
        raise ValueError("Code contains unsupported characters")
    return normalized


def _required(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Value must not be blank")
    return normalized


class VersionedWrite(BaseModel):
    expected_version: int = Field(gt=0)


class CrmCatalogProductVariantReferenceRead(BaseModel):
    id: int
    sku: str | None
    size: str | None
    garment_size_id: int | None
    fabric_id: int | None
    color: str | None
    stock_quantity: int


class CrmCatalogProductReferenceRead(BaseModel):
    id: int
    title: str
    slug: str | None
    category_id: int | None
    garment_model_id: int | None
    price: Decimal
    old_price: Decimal | None
    image_url: str | None = None
    is_active: bool
    stock_quantity: int
    variants: list[CrmCatalogProductVariantReferenceRead]


class CrmGarmentPatternWrite(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    garment_model_id: int = Field(gt=0)
    garment_size_id: int = Field(gt=0)
    media_object_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=255)
    sleeve_variant: Literal["standard", "height"] = "standard"
    width_cm: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    length_cm: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return _code(value)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _required(value)


class CrmGarmentPatternUpdate(CrmGarmentPatternWrite, VersionedWrite):
    pass


class CrmGarmentPatternRead(CrmGarmentPatternWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    grid_key: str
    version: int


class CrmGarmentFabricRequirementWrite(BaseModel):
    garment_model_id: int = Field(gt=0)
    fabric_id: int = Field(gt=0)
    meters_per_unit: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    waste_percent: Decimal = Field(
        default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2
    )
    is_primary: bool = False


class CrmGarmentFabricRequirementUpdate(
    CrmGarmentFabricRequirementWrite,
    VersionedWrite,
):
    pass


class CrmGarmentFabricRequirementRead(CrmGarmentFabricRequirementWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int


class CrmAccessoryCategoryWrite(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return _code(value)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _required(value)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class CrmAccessoryCategoryUpdate(CrmAccessoryCategoryWrite, VersionedWrite):
    pass


class CrmAccessoryCategoryRead(CrmAccessoryCategoryWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int


class CrmAccessoryWrite(BaseModel):
    category_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="RUB", pattern=r"^RUB$")
    stock_quantity: int = Field(default=0, ge=0)
    minimum_stock_quantity: int = Field(default=0, ge=0)
    photo_media_object_id: int | None = Field(default=None, gt=0)
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return _code(value)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _required(value)


class CrmAccessoryUpdate(CrmAccessoryWrite, VersionedWrite):
    pass


class CrmAccessoryRead(CrmAccessoryWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int
    model_ids: list[int] = Field(default_factory=list)


class CrmGarmentAccessoryRequirementWrite(BaseModel):
    garment_model_id: int = Field(gt=0)
    accessory_id: int = Field(gt=0)
    quantity_per_unit: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    is_optional: bool = False
    notes: str | None = None

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class CrmGarmentAccessoryRequirementUpdate(
    CrmGarmentAccessoryRequirementWrite,
    VersionedWrite,
):
    pass


class CrmGarmentAccessoryRequirementRead(CrmGarmentAccessoryRequirementWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int


class CrmPackagingBoxWrite(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    inner_length_cm: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    inner_width_cm: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    inner_height_cm: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    max_items: int = Field(gt=0)
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="RUB", pattern=r"^RUB$")
    stock_quantity: int = Field(default=0, ge=0)
    minimum_stock_quantity: int = Field(default=0, ge=0)
    photo_media_object_id: int | None = Field(default=None, gt=0)
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return _code(value)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _required(value)

    @model_validator(mode="after")
    def validate_dimensions(self) -> CrmPackagingBoxWrite:
        if max(self.inner_length_cm, self.inner_width_cm, self.inner_height_cm) > Decimal("1000"):
            raise ValueError("Box dimensions are out of range")
        return self


class CrmPackagingBoxUpdate(CrmPackagingBoxWrite, VersionedWrite):
    pass


class CrmPackagingBoxRead(CrmPackagingBoxWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int


class CrmGarmentPackagingRuleWrite(BaseModel):
    garment_model_id: int = Field(gt=0)
    box_id: int = Field(gt=0)
    max_items: int = Field(gt=0)
    priority: int = Field(default=0, ge=0)


class CrmGarmentPackagingRuleUpdate(CrmGarmentPackagingRuleWrite, VersionedWrite):
    pass


class CrmGarmentPackagingRuleRead(CrmGarmentPackagingRuleWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int


class AssortmentPage(BaseModel):
    items: list[dict[str, object]]
    next_cursor: int | None
    limit: int
