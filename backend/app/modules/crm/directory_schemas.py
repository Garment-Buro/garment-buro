"""Shared reference pages carry bounded projections, not editor collections."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.crm.assortment_schemas import CrmGarmentFabricRequirementRead
from app.modules.crm.read_schemas import CrmFabricRead


class ReferenceDirectoryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(default="", max_length=100)
    active: bool | None = None
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)
    limit: int = Field(default=24, ge=1, le=100)

    @field_validator("query")
    @classmethod
    def trim_query(cls, value: str):
        return value.strip()


class ModelDirectoryQuery(ReferenceDirectoryQuery):
    category_id: int | None = Field(default=None, gt=0, le=2_147_483_647)
    sort: Literal["name:asc", "name:desc", "code:asc", "sizes:desc", "products:desc"] = "name:asc"


class FabricDirectoryQuery(ReferenceDirectoryQuery):
    stock: Literal["all", "available", "low"] = "all"
    sort: Literal["name:asc", "code:asc", "stock:asc", "stock:desc", "price:asc", "price:desc"] = (
        "name:asc"
    )


class ModelDirectoryCard(BaseModel):
    id: int
    category_id: int | None
    category_name: str | None
    code: str
    name: str
    is_active: bool
    base_weight_g: Decimal | None
    size_count: int
    product_count: int
    tech_card_name: str | None
    tech_card_revision: int | None


class ModelDirectoryPage(BaseModel):
    items: list[ModelDirectoryCard]
    next_cursor: str | None


class FabricDirectoryPage(BaseModel):
    items: list[CrmFabricRead]
    next_cursor: str | None


class ReferencePosition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: int = Field(ge=1, le=1)
    kind: Literal[
        "models",
        "fabrics",
        "fabric-requirements",
        "accessories",
        "boxes",
        "accessory-categories",
        "accessory-requirements",
        "packaging-rules",
        "tech-cards",
        "tech-card-models",
        "pattern-models",
        "patterns",
        "pattern-sizes",
        "model-categories",
        "product-categories",
    ]
    id: int = Field(gt=0, le=2_147_483_647)
    value: str = Field(max_length=255)
    filters: str = Field(pattern=r"^[a-f0-9]{64}$")


class RequirementDirectoryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    garment_model_id: int | None = Field(default=None, gt=0, le=2_147_483_647)
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)
    limit: int = Field(default=24, ge=1, le=100)


class FabricRequirementCard(CrmGarmentFabricRequirementRead):
    garment_model_name: str
    fabric_name: str


class FabricRequirementPage(BaseModel):
    items: list[FabricRequirementCard]
    next_cursor: str | None


class SelectedReferenceQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal[
        "models",
        "fabrics",
        "accessories",
        "boxes",
        "accessory-categories",
        "tech-card-models",
        "pattern-sizes",
        "model-categories",
        "product-categories",
    ]
    ids: list[int] = Field(min_length=1, max_length=50)

    @field_validator("ids")
    @classmethod
    def valid_ids(cls, values):
        if any(value < 1 or value > 2_147_483_647 for value in values):
            raise ValueError("Invalid reference ID")
        return values


class SelectedReference(BaseModel):
    max_items: int | None = None
    id: int
    name: str
    code: str
    is_active: bool
