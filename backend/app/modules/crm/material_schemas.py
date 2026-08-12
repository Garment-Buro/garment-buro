from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.crm.command_schemas import REASON_CODE_PATTERN
from app.modules.crm.material_models import CrmMaterialMovementType


class CrmMaterialQuantityWrite(BaseModel):
    quantity_meters: Decimal = Field(
        gt=0,
        max_digits=14,
        decimal_places=3,
    )
    reason_code: str = Field(min_length=1, max_length=64, pattern=REASON_CODE_PATTERN)


class CrmMaterialAdjustmentWrite(CrmMaterialQuantityWrite):
    direction: Literal["in", "out"]


class CrmMaterialReservationWrite(BaseModel):
    plan_revision_id: int = Field(gt=0)
    fabric_id: int = Field(gt=0)
    quantity_meters: Decimal = Field(
        gt=0,
        max_digits=14,
        decimal_places=3,
    )


class CrmMaterialMovementReceipt(BaseModel):
    movement_id: int
    fabric_id: int
    reservation_id: int | None
    movement_type: CrmMaterialMovementType
    quantity_meters: Decimal
    balance_on_hand_after: Decimal
    balance_reserved_after: Decimal
    balance_available_after: Decimal
    occurred_at: datetime
