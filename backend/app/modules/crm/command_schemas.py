from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.crm.models import CrmProductionUnitStatus, CrmProjectStatus

REASON_CODE_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"


class CrmProjectTransitionWrite(BaseModel):
    expected_version: int = Field(gt=0)
    to_status: CrmProjectStatus
    reason_code: str = Field(min_length=1, max_length=64, pattern=REASON_CODE_PATTERN)


class CrmUnitTransitionWrite(BaseModel):
    expected_version: int = Field(gt=0)
    to_status: CrmProductionUnitStatus
    reason_code: str = Field(min_length=1, max_length=64, pattern=REASON_CODE_PATTERN)


class CrmAssignmentWrite(BaseModel):
    expected_version: int = Field(gt=0)
    assigned_to_user_id: int | None = Field(default=None, gt=0)
    reason_code: str = Field(min_length=1, max_length=64, pattern=REASON_CODE_PATTERN)


class CrmUnitPlanWrite(BaseModel):
    expected_version: int = Field(gt=0)
    garment_size_id: int | None = Field(default=None, gt=0)
    tech_card_revision_id: int = Field(gt=0)


class CrmStaffCommandReceipt(BaseModel):
    command_id: int
    command_type: str
    target_id: int
    result_version: int
