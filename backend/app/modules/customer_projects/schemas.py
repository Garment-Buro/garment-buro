from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

PositiveId = Annotated[int, Field(strict=True, gt=0, le=2_147_483_647)]
Version = Annotated[int, Field(strict=True, gt=0, le=2_147_483_646)]
Dimension = Annotated[float, Field(gt=0, le=2000, allow_inf_nan=False)]
PixelDimension = Annotated[float, Field(gt=0, le=16384, allow_inf_nan=False)]
Coordinate = Annotated[float, Field(ge=-1_000_000, le=1_000_000, allow_inf_nan=False)]
Price = Annotated[float, Field(ge=0, le=1_000_000_000, allow_inf_nan=False)]
ProjectKind = Literal["draft", "collection"]
ClientKey = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")]
View = Literal["front", "back"]


class ProjectInputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @field_validator("*")
    @classmethod
    def postgres_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            if "\x00" in value:
                raise ValueError("Project text must not contain NUL characters")
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as error:
                raise ValueError("Project text must be valid UTF-8") from error
        return value


class DocumentModel(ProjectInputModel):
    model_config = ConfigDict(extra="forbid", strict=True, alias_generator=to_camel)


class ImageReference(DocumentModel):
    media_id: PositiveId


class ModelImages(DocumentModel):
    front: ImageReference
    back: ImageReference


class Dimensions(DocumentModel):
    width_cm: Dimension
    height_cm: Dimension


class PixelSize(DocumentModel):
    width: PixelDimension
    height: PixelDimension


class ModelBounds(PixelSize):
    x: Coordinate
    y: Coordinate


class MeasurementRange(DocumentModel):
    min: Dimension
    max: Dimension

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.min > self.max:
            raise ValueError("Measurement range is reversed")
        return self


class GarmentFit(DocumentModel):
    selected_size: Annotated[str, Field(max_length=32)]
    sleeve_mode: Literal["standard", "height"]
    # Human height; retain the historical JSON key for saved projects.
    length_cm: Dimension
    width_cm: Dimension
    length_range: MeasurementRange
    width_range: MeasurementRange

    @model_validator(mode="after")
    def within_ranges(self) -> Self:
        if not self.length_range.min <= self.length_cm <= self.length_range.max:
            raise ValueError("Length is outside its range")
        if not self.width_range.min <= self.width_cm <= self.width_range.max:
            raise ValueError("Width is outside its range")
        return self


class TextDecoration(DocumentModel):
    content: Annotated[str, Field(min_length=1, max_length=2000)]
    font_id: Literal["manrope", "inter", "mono", "serif"]
    font_size: Annotated[float, Field(gt=0, le=1024, allow_inf_nan=False)]
    color: Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")]


class Decoration(DocumentModel):
    category_id: (
        Literal["prints", "rivets", "distress", "zippers", "pullers", "embroidery"] | None
    ) = None
    text: TextDecoration | None = None
    original_width: PixelDimension | None = None
    original_height: PixelDimension | None = None
    view: View
    uid: Annotated[str, Field(min_length=1, max_length=100)]
    variant_id: Annotated[str, Field(min_length=1, max_length=128)]
    name: Annotated[str, Field(max_length=255)]
    price: Price
    image: ImageReference
    width_cm: Dimension
    height_cm: Dimension
    x: Coordinate
    y: Coordinate
    scale: Annotated[float, Field(gt=0, le=1000, allow_inf_nan=False)]
    rotation: Annotated[float, Field(ge=-36000, le=36000, allow_inf_nan=False)]


class Customization(DocumentModel):
    kind: Literal["constructor"]
    selected_size: Annotated[str, Field(max_length=32)]
    selected_color: Annotated[str, Field(max_length=64)] | None = None
    model_images: ModelImages
    canvas: Dimensions
    garment: Dimensions
    fit: GarmentFit | None = None
    decorations: Annotated[list[Decoration], Field(max_length=100)]
    # An editor preview, never a trusted checkout quote.
    total_price: Price
    comment: Annotated[str, Field(max_length=4000)] | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        uids = [decoration.uid for decoration in self.decorations]
        if len(set(uids)) != len(uids):
            raise ValueError("Decoration identifiers must be unique")
        if self.fit is not None and self.selected_size != self.fit.selected_size:
            raise ValueError("Selected size differs from garment fit")
        return self


class ProjectSnapshot(DocumentModel):
    schema_version: Annotated[int, Field(strict=True, ge=1, le=1)]
    active_view: View
    canvas_pixel_size: PixelSize
    model_bounds: ModelBounds
    customization: Customization

    @model_validator(mode="after")
    def bounded_document(self) -> Self:
        if len(self.model_dump_json(by_alias=True).encode("utf-8")) > 262_144:
            raise ValueError("Project document exceeds 256 KiB")
        return self

    def media_ids(self) -> set[int]:
        images = self.customization.model_images
        return {images.front.media_id, images.back.media_id} | {
            decoration.image.media_id for decoration in self.customization.decorations
        }


class ProjectWrite(ProjectInputModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    kind: ProjectKind
    title: Annotated[str, Field(min_length=1, max_length=200)]
    snapshot: ProjectSnapshot


class ProjectCreate(ProjectWrite):
    client_key: ClientKey
    product_id: PositiveId


class ProjectUpdate(ProjectWrite):
    expected_version: Version


class ProjectSummary(BaseModel):
    id: int
    product_id: int | None
    kind: ProjectKind
    title: str
    version: int
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectSummary):
    snapshot: ProjectSnapshot


class ProjectPage(BaseModel):
    items: list[ProjectSummary]
    next_cursor: int | None
