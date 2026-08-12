from __future__ import annotations

from decimal import ROUND_CEILING, Decimal

MAX_CDEK_INTEGER = 2_147_483_647


class CdekLogisticsValidationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def kilograms_to_grams(value: Decimal | None) -> int:
    if value is None or value <= 0:
        raise CdekLogisticsValidationError("cdek_logistics_missing")
    grams = int((value * Decimal("1000")).to_integral_value(rounding=ROUND_CEILING))
    if not 1 <= grams <= MAX_CDEK_INTEGER:
        raise CdekLogisticsValidationError("cdek_logistics_out_of_range")
    return grams


def centimeters_to_integer(value: Decimal | None) -> int:
    if value is None or value <= 0:
        raise CdekLogisticsValidationError("cdek_logistics_missing")
    centimeters = int(value.to_integral_value(rounding=ROUND_CEILING))
    if not 1 <= centimeters <= MAX_CDEK_INTEGER:
        raise CdekLogisticsValidationError("cdek_logistics_out_of_range")
    return centimeters
