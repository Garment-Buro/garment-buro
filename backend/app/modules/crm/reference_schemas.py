from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

REFERENCE_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,63}$")
SIZE_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_+./-]{0,31}$")
STAGE_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _strip_required(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Value must not be blank")
    return normalized


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class CrmFabricWrite(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    material_type: str | None = Field(default=None, max_length=100)
    color_name: str = Field(min_length=1, max_length=64)
    color_hex: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    density_gsm: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    width_cm: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    cost_per_meter: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )
    cost_per_kg: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )
    minimum_stock_meters: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        max_digits=14,
        decimal_places=3,
    )
    currency: str = Field(default="RUB", pattern=r"^RUB$")
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not REFERENCE_CODE_PATTERN.fullmatch(normalized):
            raise ValueError("Fabric code contains unsupported characters")
        return normalized

    @field_validator("name", "color_name")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("material_type")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("color_hex")
    @classmethod
    def normalize_color_hex(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class CrmGarmentSizeWrite(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    sort_order: int = Field(default=0, ge=0)
    base_price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    base_length_cm: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    base_width_cm: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    min_height_cm: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    max_height_cm: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    min_length_cm: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    max_length_cm: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    min_width_cm: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    max_width_cm: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    min_sleeve_length_cm: Decimal | None = Field(
        default=None, gt=0, max_digits=10, decimal_places=2
    )
    max_sleeve_length_cm: Decimal | None = Field(
        default=None, gt=0, max_digits=10, decimal_places=2
    )
    allow_standard_sleeve: bool = True
    allow_height_sleeve: bool = True
    extra_width_price_per_cm: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )
    currency: str = Field(default="RUB", pattern=r"^RUB$")

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not SIZE_CODE_PATTERN.fullmatch(normalized):
            raise ValueError("Garment size code contains unsupported characters")
        return normalized

    @model_validator(mode="after")
    def validate_ranges(self) -> CrmGarmentSizeWrite:
        for minimum, maximum, label in (
            (self.min_height_cm, self.max_height_cm, "height"),
            (self.min_length_cm, self.max_length_cm, "length"),
            (self.min_width_cm, self.max_width_cm, "width"),
            (self.min_sleeve_length_cm, self.max_sleeve_length_cm, "sleeve"),
        ):
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError(f"Garment size {label} range is inverted")
        for base, minimum, maximum, label in (
            (self.base_length_cm, self.min_length_cm, self.max_length_cm, "length"),
            (self.base_width_cm, self.min_width_cm, self.max_width_cm, "width"),
        ):
            if base is not None and minimum is not None and base < minimum:
                raise ValueError(f"Garment size base {label} is below the allowed range")
            if base is not None and maximum is not None and base > maximum:
                raise ValueError(f"Garment size base {label} is above the allowed range")
        if not self.allow_standard_sleeve and not self.allow_height_sleeve:
            raise ValueError("At least one sleeve option must be enabled")
        return self


class CrmGarmentModelWrite(BaseModel):
    category_id: int | None = Field(default=None, gt=0)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    base_size_code: str | None = Field(default=None, min_length=1, max_length=32)
    fit_model_name: str | None = Field(default=None, max_length=120)
    fit_model_height_cm: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    base_length_cm: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    base_width_cm: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    base_weight_g: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    size_chart_media_object_id: int | None = Field(default=None, gt=0)
    is_active: bool = True
    sizes: list[CrmGarmentSizeWrite] = Field(default_factory=list, max_length=100)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not REFERENCE_CODE_PATTERN.fullmatch(normalized):
            raise ValueError("Garment model code contains unsupported characters")
        return normalized

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("base_size_code")
    @classmethod
    def normalize_base_size_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @field_validator("fit_model_name")
    @classmethod
    def normalize_fit_model_name(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @model_validator(mode="after")
    def validate_size_identity(self) -> CrmGarmentModelWrite:
        codes = [size.code for size in self.sizes]
        if len(codes) != len(set(codes)):
            raise ValueError("Garment size codes must be unique within a model")
        sort_orders = [size.sort_order for size in self.sizes]
        if len(sort_orders) != len(set(sort_orders)):
            raise ValueError("Active garment size sort orders must be unique")
        if self.base_size_code is not None and self.base_size_code not in codes:
            raise ValueError("Base size must be selected from the model sizes")
        return self


class CrmTechCardCheckpointWrite(BaseModel):
    position: int = Field(gt=0)
    stage_code: str = Field(min_length=1, max_length=64)
    role_code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    standard_minutes: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=10,
        decimal_places=2,
    )
    labor_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="RUB", pattern=r"^RUB$")

    @field_validator("stage_code")
    @classmethod
    def normalize_stage_code(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not STAGE_CODE_PATTERN.fullmatch(normalized):
            raise ValueError("Tech-card stage code contains unsupported characters")
        return normalized

    @field_validator("role_code")
    @classmethod
    def normalize_role_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not STAGE_CODE_PATTERN.fullmatch(normalized):
            raise ValueError("Tech-card role code contains unsupported characters")
        return normalized

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class CrmTechCardRevisionWrite(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    checkpoints: list[CrmTechCardCheckpointWrite] = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @model_validator(mode="after")
    def validate_checkpoint_identity(self) -> CrmTechCardRevisionWrite:
        positions = [checkpoint.position for checkpoint in self.checkpoints]
        if len(positions) != len(set(positions)):
            raise ValueError("Tech-card checkpoint positions must be unique")
        return self


class CrmTechCardCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    revision: CrmTechCardRevisionWrite

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not REFERENCE_CODE_PATTERN.fullmatch(normalized):
            raise ValueError("Tech-card code contains unsupported characters")
        return normalized


class CrmFabricReferenceRead(CrmFabricWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int


class CrmFabricUpdate(CrmFabricWrite):
    expected_version: int = Field(gt=0)


class CrmGarmentSizeReferenceRead(CrmGarmentSizeWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    version: int


class CrmGarmentModelCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    is_active: bool
    version: int


class CrmGarmentModelCategoryWrite(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _strip_required(value)


class CrmGarmentModelCategoryUpdate(CrmGarmentModelCategoryWrite):
    expected_version: int = Field(gt=0)


class CrmGarmentModelReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int | None
    code: str
    name: str
    description: str | None
    base_size_code: str | None
    fit_model_name: str | None
    fit_model_height_cm: Decimal | None
    base_length_cm: Decimal | None
    base_width_cm: Decimal | None
    base_weight_g: Decimal | None
    size_chart_media_object_id: int | None
    is_active: bool
    version: int
    sizes: list[CrmGarmentSizeReferenceRead]


class CrmGarmentModelUpdate(CrmGarmentModelWrite):
    expected_version: int = Field(gt=0)


class CrmCatalogProductModelAssignmentRead(BaseModel):
    garment_model_id: int
    catalog_product_id: int


class CrmCatalogProductModelAssignmentWrite(BaseModel):
    catalog_product_id: int = Field(gt=0)


class CrmTechCardCheckpointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    stage_code: str
    role_code: str
    name: str
    description: str | None
    standard_minutes: Decimal | None
    labor_cost: Decimal
    currency: str


class CrmTechCardRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    revision_number: int
    based_on_revision_id: int | None
    status: str
    name_snapshot: str
    description_snapshot: str | None
    created_by_user_id: int | None
    published_by_user_id: int | None
    created_at: datetime
    published_at: datetime | None
    checkpoints: list[CrmTechCardCheckpointRead]


class CrmTechCardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    garment_model_id: int
    code: str
    latest_revision_number: int
    is_active: bool
    revisions: list[CrmTechCardRevisionRead]


class CrmTechCardRevisionCreate(BaseModel):
    expected_latest_revision: int = Field(gt=0)
    revision: CrmTechCardRevisionWrite
