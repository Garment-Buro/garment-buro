from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Station = Literal[
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
]


class EmployeeWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    first_name: str = Field(min_length=1, max_length=255)
    last_name: str = Field(default="", max_length=255)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)
    status: Literal["active", "blocked"] = "active"
    stations: list[Station] = Field(min_length=1, max_length=10)
    primary_station: Station

    @model_validator(mode="after")
    def validate_stations(self):
        if len(set(self.stations)) != len(self.stations):
            raise ValueError("Участки сотрудника не должны повторяться")
        if self.primary_station not in self.stations:
            raise ValueError("Основной участок должен входить в роли сотрудника")
        return self


class EmployeeRead(BaseModel):
    id: int
    first_name: str
    last_name: str
    name: str
    email: str | None
    phone: str | None
    status: Literal["active", "blocked"]
    created_at: datetime
    stations: list[Station]
    primary_station: Station
    code_active: bool
    code_updated_at: datetime | None


class EmployeeCodeResponse(BaseModel):
    employee: EmployeeRead
    code: str | None = Field(default=None, repr=False)
