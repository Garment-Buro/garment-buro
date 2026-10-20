from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.crm.assortment_schemas import CrmGarmentPatternRead
from app.modules.crm.directory_schemas import ReferenceDirectoryQuery, SelectedReference


class PatternModelQuery(ReferenceDirectoryQuery):
    model_id: int | None = Field(default=None, gt=0, le=2_147_483_647)
    pattern_active: bool | None = None
    sort: Literal["model:asc", "model:desc", "code:asc", "code:desc"] = "model:asc"


class PatternFileQuery(ReferenceDirectoryQuery):
    model_id: int | None = Field(default=None, gt=0, le=2_147_483_647)
    size_id: int | None = Field(default=None, gt=0, le=2_147_483_647)
    sort: Literal["id:desc", "code:asc"] = "id:desc"


class PatternSizeQuery(ReferenceDirectoryQuery):
    model_id: int = Field(gt=0, le=2_147_483_647)
    sort: Literal["position:asc", "name:asc"] = "position:asc"


class PatternGridQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    size_id: int | None = Field(default=None, gt=0, le=2_147_483_647)
    width_page: int = Field(default=0, ge=0, le=2_147_483_647)
    length_page: int = Field(default=0, ge=0, le=2_147_483_647)
    expected_size_version: int | None = Field(default=None, gt=0, le=2_147_483_647)


class PatternModelBrief(SelectedReference):
    version: int


class PatternModelCard(PatternModelBrief):
    pattern_count: int
    uploaded_count: int
    required_count: str


class PatternModelPage(BaseModel):
    items: list[PatternModelCard]
    next_cursor: str | None


class PatternFileCard(CrmGarmentPatternRead):
    garment_model_name: str
    size_code: str
    size_is_active: bool


class PatternFilePage(BaseModel):
    items: list[PatternFileCard]
    next_cursor: str | None


class PatternSizePage(BaseModel):
    items: list[SelectedReference]
    next_cursor: str | None


class PatternSize(BaseModel):
    id: int
    code: str
    is_active: bool
    version: int
    min_width_cm: Decimal | None
    max_width_cm: Decimal | None
    min_length_cm: Decimal | None
    max_length_cm: Decimal | None
    allow_standard_sleeve: bool
    allow_height_sleeve: bool


class PatternContext(BaseModel):
    model: PatternModelBrief
    size: PatternSize | None
    pattern: CrmGarmentPatternRead | None = None


class PatternCoverage(PatternContext):
    step_cm: Decimal
    width_values: list[Decimal]
    length_values: list[Decimal]
    width_page: int
    length_page: int
    width_count: int
    length_count: int
    width_pages: int
    length_pages: int
    required_count: str
    uploaded_count: int
    items: list[CrmGarmentPatternRead]
