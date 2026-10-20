"""Short tech-card summaries and one revision source, independent of history."""

from typing import Literal

from pydantic import BaseModel

from app.modules.crm.directory_schemas import ReferenceDirectoryQuery, SelectedReference
from app.modules.crm.reference_schemas import CrmTechCardCheckpointRead

RevisionStatus = Literal["draft", "published", "archived", "discarded"]


class TechCardDirectoryQuery(ReferenceDirectoryQuery):
    revision_status: RevisionStatus | None = None
    sort: Literal["model:asc", "code:asc", "revision:asc", "revision:desc"] = "model:asc"


class TechCardModelQuery(ReferenceDirectoryQuery):
    sort: Literal["name:asc", "code:asc"] = "name:asc"


class TechCardSummary(BaseModel):
    id: int
    garment_model_id: int
    garment_model_name: str
    code: str
    is_active: bool
    latest_revision_number: int
    latest_revision_status: RevisionStatus | None
    latest_revision_name: str | None
    checkpoint_count: int
    draft_revision_number: int | None


class TechCardPage(BaseModel):
    items: list[TechCardSummary]
    next_cursor: str | None


class TechCardModelPage(BaseModel):
    items: list[SelectedReference]
    next_cursor: str | None


class TechRevisionSource(BaseModel):
    id: int
    revision_number: int
    name_snapshot: str
    description_snapshot: str | None
    checkpoints: list[CrmTechCardCheckpointRead]


class TechCardEditorSource(BaseModel):
    id: int
    code: str
    garment_model_id: int
    garment_model_name: str
    latest_revision_number: int
    draft_revision_number: int | None
    source: TechRevisionSource | None
