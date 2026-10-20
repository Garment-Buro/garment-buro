"""Stock reference pages and joined rules, independent of editor aggregates."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.modules.crm.assortment_schemas import (
    CrmAccessoryCategoryRead,
    CrmAccessoryWrite,
    CrmGarmentAccessoryRequirementRead,
    CrmGarmentPackagingRuleRead,
    CrmPackagingBoxRead,
)
from app.modules.crm.directory_schemas import ReferenceDirectoryQuery, RequirementDirectoryQuery


class AccessoryDirectoryQuery(ReferenceDirectoryQuery):
    category_id: int | None = Field(default=None, gt=0, le=2_147_483_647)
    garment_model_id: int | None = Field(default=None, gt=0, le=2_147_483_647)
    stock: Literal["all", "available", "low"] = "all"
    sort: Literal["name:asc", "code:asc", "stock:asc", "stock:desc", "price:asc", "price:desc"] = (
        "name:asc"
    )


class BoxDirectoryQuery(ReferenceDirectoryQuery):
    stock: Literal["all", "available", "low"] = "all"
    sort: Literal[
        "name:asc",
        "code:asc",
        "stock:asc",
        "stock:desc",
        "price:asc",
        "price:desc",
        "capacity:asc",
        "capacity:desc",
    ] = "name:asc"


class AccessoryCategoryQuery(ReferenceDirectoryQuery):
    sort: Literal["name:asc", "code:asc"] = "name:asc"


class StockRelationQuery(RequirementDirectoryQuery):
    query: str = Field(default="", max_length=100)

    @field_validator("query")
    @classmethod
    def trim_query(cls, value: str):
        return value.strip()


class AccessoryRequirementQuery(StockRelationQuery):
    sort: Literal["id:desc"] = "id:desc"


class PackagingRuleQuery(StockRelationQuery):
    sort: Literal["priority:asc"] = "priority:asc"


class AccessoryCard(CrmAccessoryWrite):
    id: int
    version: int
    category_name: str
    model_count: int


class AccessoryRequirementCard(CrmGarmentAccessoryRequirementRead):
    garment_model_name: str
    accessory_name: str


class PackagingRuleCard(CrmGarmentPackagingRuleRead):
    garment_model_name: str
    box_name: str
    box_capacity: int


class AccessoryDirectoryPage(BaseModel):
    items: list[AccessoryCard]
    next_cursor: str | None


class BoxDirectoryPage(BaseModel):
    items: list[CrmPackagingBoxRead]
    next_cursor: str | None


class AccessoryCategoryPage(BaseModel):
    items: list[CrmAccessoryCategoryRead]
    next_cursor: str | None


class AccessoryRequirementPage(BaseModel):
    items: list[AccessoryRequirementCard]
    next_cursor: str | None


class PackagingRulePage(BaseModel):
    items: list[PackagingRuleCard]
    next_cursor: str | None
