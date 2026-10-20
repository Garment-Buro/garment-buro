from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.catalog.pricing import (
    ConstructorPriceInput,
    calculate_customization_price,
    price_customization,
)


@pytest.mark.parametrize(
    ("scale", "expected"), [(0.25, 80), (1, 80), (1.5, 120), (1.00625, 81), (4, 320)]
)
def test_scale_rule_and_positive_half_rounding(scale: float, expected: int) -> None:
    quote = calculate_customization_price(
        Decimal("100.25"), ConstructorPriceInput(decorations=[{"uid": "one", "scale": scale}])
    )
    assert quote.decorations[0].price == Decimal(expected)
    assert quote.total_price == Decimal("100.25") + expected


def test_prices_are_copied_over_untrusted_snapshot_and_each_placement_counts() -> None:
    snapshot = {
        "kind": "constructor",
        "totalPrice": 1,
        "comment": "Retain",
        "decorations": [
            {"uid": "a", "scale": 1.5, "price": 0, "view": "front"},
            {"uid": "b", "scale": 0.25, "price": 9999, "view": "back"},
        ],
    }
    price, normalized = price_customization(Decimal("100.25"), snapshot)
    assert price == Decimal("300.25")
    assert normalized["totalPrice"] == 300.25
    assert [d["price"] for d in normalized["decorations"]] == [120, 80]
    assert normalized["comment"] == "Retain"
    assert snapshot["totalPrice"] == 1
    assert snapshot["decorations"][0]["price"] == 0
    assert price_customization(Decimal("100.25"), None) == (Decimal("100.25"), None)
    legacy = {"fit": {"widthCm": 58}}
    assert price_customization(Decimal("100.25"), legacy) == (Decimal("100.25"), legacy)
    assert calculate_customization_price(
        Decimal("100.25"), ConstructorPriceInput(decorations=[])
    ).total_price == Decimal("100.25")


@pytest.mark.parametrize(
    "decorations",
    [
        [{"uid": "a", "scale": scale}]
        for scale in (0, -1, 1001, True, "1", float("inf"), float("nan"))
    ]
    + [
        [{"uid": "a", "scale": 1}, {"uid": "a", "scale": 2}],
        [{"uid": "", "scale": 1}],
        [{"uid": "a"}],
        [{"uid": str(i), "scale": 1} for i in range(101)],
    ],
)
def test_malformed_placements_are_rejected(decorations: list) -> None:
    with pytest.raises(ValidationError):
        ConstructorPriceInput(decorations=decorations)


@pytest.mark.parametrize(
    "snapshot",
    [
        {"decorations": [{"uid": "a", "scale": 1}]},
        {"kind": "constructor"},
        {"kind": "other", "decorations": []},
    ],
)
def test_constructor_cannot_bypass_pricing_by_omitting_kind_or_decorations(snapshot: dict) -> None:
    with pytest.raises(ValueError):
        price_customization(Decimal("100.25"), snapshot)


def test_editor_geometry_is_preserved_without_affecting_price() -> None:
    geometry = {
        "canvasPixelSize": {"width": 1000, "height": 900},
        "modelBounds": {"x": -10, "y": 85, "width": 600, "height": 700},
    }
    snapshot = {"kind": "constructor", "decorations": [], "geometry": geometry}
    price, normalized = price_customization(Decimal("100.25"), snapshot)
    assert price == Decimal("100.25")
    assert normalized["geometry"] == geometry


@pytest.mark.parametrize("value", [0, -1, 16385, True, "800", float("inf"), float("nan")])
def test_invalid_editor_geometry_cannot_be_accepted_with_a_valid_price(value: object) -> None:
    from app.modules.carts.schemas import CartItemWrite

    snapshot = {
        "kind": "constructor",
        "decorations": [],
        "geometry": {
            "canvasPixelSize": {"width": value, "height": 900},
            "modelBounds": {"x": 150, "y": 85, "width": 600, "height": 700},
        },
    }
    with pytest.raises(ValueError):
        price_customization(Decimal("100.25"), snapshot)
    with pytest.raises(ValueError):
        CartItemWrite(
            id="design",
            product_id=1,
            title="Test",
            price=100.25,
            quantity=1,
            customization=snapshot,
        )
