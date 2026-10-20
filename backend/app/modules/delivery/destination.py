"""Resolve one shipment destination from the current trusted directory snapshot."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.delivery.constants import CDEK_PICKUP_DELIVERY_METHOD
from app.modules.delivery.directory import DIRECTORY_KEY
from app.modules.delivery.directory_models import PickupDirectoryState, PickupPoint
from app.modules.delivery.quote_schemas import CdekQuoteRequest
from app.modules.identity.security import ensure_utc


class DeliveryDestinationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DeliveryDestination:
    city: str
    address: str
    point_code: str | None


async def resolve_delivery_destination(
    session: AsyncSession,
    command: CdekQuoteRequest,
    *,
    now: datetime | None = None,
) -> DeliveryDestination:
    if command.delivery_method != CDEK_PICKUP_DELIVERY_METHOD:
        return DeliveryDestination(command.city, command.delivery_address, None)
    state = await session.get(PickupDirectoryState, DIRECTORY_KEY)
    current_time = ensure_utc(now or datetime.now(timezone.utc))
    if (
        state is None
        or state.updated_at is None
        or current_time - ensure_utc(state.updated_at) > timedelta(days=7)
    ):
        raise DeliveryDestinationError("cdek_directory_unavailable")
    point = await session.get(PickupPoint, command.cdek_point_code)
    if point is None:
        raise DeliveryDestinationError("cdek_pickup_point_unavailable")
    location = point.payload.get("location")
    if not isinstance(location, dict):
        raise DeliveryDestinationError("cdek_pickup_point_unavailable")
    city = location.get("city")
    address = location.get("address_full") or location.get("address")
    if not isinstance(city, str) or not isinstance(address, str):
        raise DeliveryDestinationError("cdek_pickup_point_unavailable")
    city, address = " ".join(city.split()), " ".join(address.split())
    if not city or not address or len(city) > 255 or len(address) > 4096:
        raise DeliveryDestinationError("cdek_pickup_point_unavailable")
    return DeliveryDestination(city, address, point.code)
