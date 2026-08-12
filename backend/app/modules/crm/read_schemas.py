from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.modules.crm.models import CrmProductionUnitStatus, CrmProjectStatus


class CrmProjectSummary(BaseModel):
    id: int
    order_id: int
    status: CrmProjectStatus
    version: int
    items_count: int
    units_count: int
    assigned_to_user_id: int | None
    paid_at: datetime
    started_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CrmProjectPage(BaseModel):
    items: list[CrmProjectSummary]
    next_cursor: int | None
    limit: int


class CrmProductionPlanSummary(BaseModel):
    id: int
    revision_number: int
    garment_model_id: int
    garment_size_id: int | None
    tech_card_revision_id: int
    planned_at: datetime


class CrmProductionUnitRead(BaseModel):
    id: int
    order_item_id: int
    product_id: int
    variant_id: int | None
    unit_number: int
    title: str
    sku: str | None
    size: str
    color: str
    status: CrmProductionUnitStatus
    version: int
    assigned_to_user_id: int | None
    started_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    active_plan: CrmProductionPlanSummary | None


class CrmProductionUnitPage(BaseModel):
    items: list[CrmProductionUnitRead]
    next_cursor: int | None
    limit: int


class CrmProjectDetail(BaseModel):
    project: CrmProjectSummary
    units: CrmProductionUnitPage


class CrmMaterialBalanceRead(BaseModel):
    on_hand_meters: Decimal
    reserved_meters: Decimal
    available_meters: Decimal
    version: int
    updated_at: datetime


class CrmFabricRead(BaseModel):
    id: int
    code: str
    name: str
    material_type: str | None
    color_name: str
    color_hex: str | None
    density_gsm: Decimal | None
    width_cm: Decimal
    cost_per_meter: Decimal | None
    currency: str
    is_active: bool
    version: int
    balance: CrmMaterialBalanceRead | None


class CrmFabricPage(BaseModel):
    items: list[CrmFabricRead]
    next_cursor: int | None
    limit: int


class CrmGarmentSizeRead(BaseModel):
    id: int
    code: str
    sort_order: int
    base_price: Decimal
    currency: str
    is_active: bool
    version: int


class CrmPublishedTechCardRead(BaseModel):
    tech_card_id: int
    code: str
    revision_id: int
    revision_number: int
    name: str
    published_at: datetime


class CrmGarmentModelRead(BaseModel):
    id: int
    code: str
    name: str
    base_height_cm: Decimal | None
    base_length_cm: Decimal | None
    base_width_cm: Decimal | None
    base_weight_g: Decimal | None
    is_active: bool
    version: int
    catalog_product_ids: list[int]
    sizes: list[CrmGarmentSizeRead]
    published_tech_card: CrmPublishedTechCardRead | None


class CrmGarmentModelPage(BaseModel):
    items: list[CrmGarmentModelRead]
    next_cursor: int | None
    limit: int
