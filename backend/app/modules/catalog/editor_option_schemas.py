from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EditorOptionsQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(default="", max_length=100)
    cursor: int | None = Field(default=None, gt=0, le=2_147_483_647)
    limit: int = Field(default=24, ge=1, le=100)
    model_id: int | None = Field(default=None, gt=0, le=2_147_483_647)

    @field_validator("query")
    @classmethod
    def trim(cls, value: str):
        return value.strip()


class ModelOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    is_active: bool


class SizeOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    is_active: bool


class SelectedSizeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_size_ids: list[Annotated[int, Field(gt=0, le=2_147_483_647)]] = Field(
        default_factory=list, max_length=200
    )


class EditorSizeQuery(EditorOptionsQuery):
    model_id: int = Field(gt=0, le=2_147_483_647)


class SizeOptionsPage(BaseModel):
    items: list[SizeOption]
    next_cursor: int | None


class EditorModel(ModelOption):
    sizes: list[SizeOption]


class ModelOptionsPage(BaseModel):
    items: list[ModelOption]
    next_cursor: int | None


class FabricOption(ModelOption):
    color_name: str
    color_hex: str | None


class FabricOptionsPage(BaseModel):
    items: list[FabricOption]
    next_cursor: int | None


class SelectedFabricQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[Annotated[int, Field(gt=0, le=2_147_483_647)]] = Field(min_length=1, max_length=200)
