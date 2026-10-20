"""The production lattice is measured from each size minimum, in exact cents."""

from decimal import Decimal

GRID_STEP_CM = Decimal("2.00")
GRID_SIDE = 6


def axis(minimum: Decimal | None, maximum: Decimal | None, page: int):
    if minimum is None or maximum is None or maximum < minimum:
        if page:
            raise ValueError("Grid page is outside the size range")
        return [], 0, 0
    count = int((maximum - minimum) // GRID_STEP_CM) + 1
    pages = (count + GRID_SIDE - 1) // GRID_SIDE
    if page >= pages:
        raise ValueError("Grid page is outside the size range")
    start = page * GRID_SIDE
    return (
        [minimum + GRID_STEP_CM * index for index in range(start, min(start + GRID_SIDE, count))],
        count,
        pages,
    )
