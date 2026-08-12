from __future__ import annotations

from pydantic import BaseModel, Field


class CrmFileUploadReceipt(BaseModel):
    attachment_id: int = Field(gt=0)
    media_id: int = Field(gt=0)
    content_type: str = Field(min_length=1, max_length=100)
    size_bytes: int = Field(gt=0)
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CrmFileDownloadReceipt(BaseModel):
    attachment_id: int = Field(gt=0)
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)
    size_bytes: int = Field(gt=0)
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expires_seconds: int = Field(ge=60, le=604_800)
    url: str = Field(min_length=1, max_length=8_192)
