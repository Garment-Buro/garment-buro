"""Validate shipping locally before creating an order; never call CDEK here."""

from datetime import datetime

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.delivery.quote_proof import DeliveryQuoteProof, InvalidDeliveryQuoteError
from app.modules.delivery.quote_schemas import CdekQuoteRequest
from app.modules.delivery.quote_service import CdekQuoteService
from app.modules.orders.schemas import OrderCreationCommand


class CheckoutDeliveryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def verify(
        self,
        session: AsyncSession,
        command: OrderCreationCommand,
        *,
        now: datetime | None = None,
    ) -> OrderCreationCommand:
        if not command.delivery_quote_token:
            raise InvalidDeliveryQuoteError("Missing delivery quote")
        try:
            request = CdekQuoteRequest.model_validate(
                {
                    "city": command.delivery_city,
                    "delivery_address": command.delivery_address,
                    "delivery_method": command.delivery_method,
                    "cdek_point_code": command.cdek_point_code,
                    "cart_items": [
                        {"product_id": item.product_id, "quantity": item.quantity}
                        for item in command.items
                    ],
                }
            )
        except ValidationError as exc:
            raise InvalidDeliveryQuoteError("Invalid delivery destination") from exc
        # Provider is unused: preparation only reads trusted catalog/directory.
        prepared = await CdekQuoteService(self.settings, None).prepare_for_verification(
            session, request, now=now
        )
        amount = DeliveryQuoteProof(self.settings).verify(
            command.delivery_quote_token, prepared, now=now
        )
        return command.model_copy(
            update={
                "delivery_price": amount,
                "delivery_city": prepared.delivery_city,
                "delivery_address": prepared.delivery_address,
                "cdek_point_code": prepared.cdek_point_code,
            }
        )
