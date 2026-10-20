from typing import Literal

from pydantic import BaseModel

from app.modules.crm.directory_schemas import ReferenceDirectoryQuery

CategoryKind = Literal["model-categories", "product-categories"]


class CategoryDirectoryQuery(ReferenceDirectoryQuery):
    sort: Literal["name:asc", "name:desc", "code:asc", "code:desc", "id:asc", "id:desc"] = (
        "name:asc"
    )


class CategoryCard(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool
    version: int
    item_count: int


class CategoryPage(BaseModel):
    items: list[CategoryCard]
    next_cursor: str | None
