from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Stage = Literal["cut", "application", "sewing", "press", "qc", "packing"]
STAGES = ("cut", "application", "sewing", "press", "qc", "packing")
STATIONS = (
    "tech",
    "kit",
    "cut",
    "dtf",
    "application",
    "sewing",
    "press",
    "qc",
    "packing",
    "shipping",
)
STAGE_LABELS = {
    "tech": "Входящие",
    "kit": "Комплектовка",
    "cut": "Раскрой",
    "dtf": "DTF печать",
    "application": "Нанесение",
    "sewing": "Пошив",
    "press": "ВТО",
    "qc": "ОТК",
    "packing": "Упаковка",
    "shipping": "Отправка",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Component(StrictModel):
    key: str = Field(pattern=r"^[a-z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=160)
    quantity: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    unit: Literal["шт", "м", "комплект"]
    location: str = Field(min_length=1, max_length=160)


class SpecificationWrite(StrictModel):
    tech_card_revision_id: int = Field(gt=0)
    garment_size_id: int | None = Field(default=None, gt=0)
    route: list[Stage] = Field(min_length=2, max_length=6)
    components: list[Component] = Field(min_length=1, max_length=100)
    pattern_file_ids: list[int] = Field(default_factory=list, max_length=20)
    print_file_ids: list[int] = Field(default_factory=list, max_length=50)
    instructions: str = Field(min_length=1, max_length=4000)
    quality_checks: list[str] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_evidence(self):
        if len(set(self.route)) != len(self.route) or self.route != sorted(
            self.route, key=STAGES.index
        ):
            raise ValueError("Маршрут должен идти по порядку без повторов")
        if self.route[-2:] != ["qc", "packing"]:
            raise ValueError("Маршрут должен завершаться ОТК и упаковкой")
        if "cut" in self.route and not self.pattern_file_ids:
            raise ValueError("Для раскроя нужны сохранённые лекала")
        if ("application" in self.route) != bool(self.print_file_ids):
            raise ValueError("Нанесение и файлы печати должны быть указаны вместе")
        if any(i <= 0 for i in self.pattern_file_ids + self.print_file_ids):
            raise ValueError("Некорректный идентификатор файла")
        if len({x.key for x in self.components}) != len(self.components):
            raise ValueError("Коды комплектующих должны быть уникальны")
        if any(not x.strip() or len(x) > 300 for x in self.quality_checks):
            raise ValueError("Заполните проверки ОТК")
        if len(set(self.quality_checks)) != len(self.quality_checks):
            raise ValueError("Проверки ОТК не должны повторяться")
        return self


class ProductionCommand(StrictModel):
    expected_version: int = Field(ge=0)
    action: Literal[
        "plan",
        "confirm_documents",
        "release",
        "check_component",
        "send_bag",
        "dtf_ready",
        "insert_dtf",
        "complete_stage",
        "return_to_dtf",
        "report_issue",
        "resolve_issue",
        "rework",
        "pack_bag",
        "dispatch",
    ]
    unit_id: int | None = Field(default=None, gt=0)
    specification: SpecificationWrite | None = None
    component_key: str | None = Field(default=None, max_length=64)
    checked: bool | None = None
    stage: Stage | None = None
    quality_confirmed: list[int] = Field(default_factory=list, max_length=30)
    note: str | None = Field(default=None, min_length=1, max_length=1000)
    tracking_number: str | None = Field(default=None, min_length=3, max_length=100)


class CommandReceipt(BaseModel):
    project_id: int
    version: int
    event_id: int
