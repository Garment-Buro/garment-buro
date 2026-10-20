"""The replaceable server policy for custom print/text placement prices.

Persisted project/cart prices are previews. New orders always run this policy.
Hardware SKUs need a real server catalog before a separate tariff can be offered.
"""

from copy import deepcopy
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

CUSTOM_DECORATION_BASE_PRICE = Decimal("80")
PRICING_POLICY_REVISION = "custom-scale-v1"
MONEY_QUANTUM = Decimal("0.01")


class PlacementPriceInput(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    uid: str = Field(min_length=1, max_length=100)
    scale: float = Field(gt=0, le=1000, allow_inf_nan=False)


class ConstructorPriceInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    decorations: Annotated[list[PlacementPriceInput], Field(max_length=100)]

    @model_validator(mode="after")
    def unique_placements(self) -> Self:
        ids = [item.uid for item in self.decorations]
        if len(set(ids)) != len(ids):
            raise ValueError("Decoration identifiers must be unique")
        return self


class CanvasPixelSizeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    width: float = Field(gt=0, le=16384, allow_inf_nan=False)
    height: float = Field(gt=0, le=16384, allow_inf_nan=False)


class ModelBoundsInput(CanvasPixelSizeInput):
    x: float = Field(ge=-1_000_000, le=1_000_000, allow_inf_nan=False)
    y: float = Field(ge=-1_000_000, le=1_000_000, allow_inf_nan=False)


class ConstructorGeometryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    canvas_pixel_size: CanvasPixelSizeInput = Field(alias="canvasPixelSize")
    model_bounds: ModelBoundsInput = Field(alias="modelBounds")


class ConstructorSnapshotPriceInput(ConstructorPriceInput):
    kind: Literal["constructor"]
    geometry: ConstructorGeometryInput | None = None


class PlacementPrice(BaseModel):
    uid: str
    price: Decimal


class CustomizationPrice(BaseModel):
    policy_revision: str = PRICING_POLICY_REVISION
    decoration_base_price: Decimal = CUSTOM_DECORATION_BASE_PRICE
    base_price: Decimal
    customization_price: Decimal
    total_price: Decimal
    decorations: list[PlacementPrice]


class ProductPriceResponse(CustomizationPrice):
    product_id: int


def custom_placement_price(scale: float) -> Decimal:
    """Change the formula here, and bump PRICING_POLICY_REVISION when changing it."""
    return max(
        CUSTOM_DECORATION_BASE_PRICE,
        (CUSTOM_DECORATION_BASE_PRICE * Decimal(str(scale))).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        ),
    )


def calculate_customization_price(
    base_price: Decimal, design: ConstructorPriceInput
) -> CustomizationPrice:
    placements = [
        PlacementPrice(uid=item.uid, price=custom_placement_price(item.scale))
        for item in design.decorations
    ]
    subtotal = sum((item.price for item in placements), Decimal("0"))
    base = base_price.quantize(MONEY_QUANTUM)
    return CustomizationPrice(
        base_price=base,
        customization_price=subtotal,
        total_price=base + subtotal,
        decorations=placements,
    )


def validate_customization(customization: dict[str, object] | None) -> ConstructorPriceInput | None:
    if customization is None:
        return None
    if customization.get("kind") == "constructor" or "decorations" in customization:
        return ConstructorSnapshotPriceInput.model_validate(customization)
    # Historical fit/comment metadata is not an offer of a priced decoration.
    return None


def price_customization(
    base_price: Decimal, customization: dict[str, object] | None
) -> tuple[Decimal, dict[str, object] | None]:
    design = validate_customization(customization)
    if design is None:
        return base_price.quantize(MONEY_QUANTUM), deepcopy(customization)
    quote = calculate_customization_price(base_price, design)
    snapshot = deepcopy(customization)
    snapshot["totalPrice"] = float(quote.total_price)
    for decoration, price in zip(snapshot["decorations"], quote.decorations, strict=True):
        decoration["price"] = float(price.price)
    return quote.total_price, snapshot
