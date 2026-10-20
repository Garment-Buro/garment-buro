from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class DesignImage(BaseModel):
    url: str
    content_type: str
    size_bytes: int
    expires_at: datetime


class DesignImageImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    media_ids: list[Annotated[int, Field(strict=True, gt=0, le=2_147_483_647)]] = Field(
        min_length=1, max_length=102
    )


class ImportedDesignImage(DesignImage):
    media_id: int


class ImportedDesignImages(BaseModel):
    items: list[ImportedDesignImage]
