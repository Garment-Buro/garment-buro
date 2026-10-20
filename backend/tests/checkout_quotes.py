"""Issue actual server proofs from fixture catalog/directory, without CDEK I/O."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.delivery.directory_models import PickupDirectoryState, PickupPoint
from app.modules.delivery.quote_proof import DeliveryQuoteProof
from app.modules.delivery.quote_schemas import CdekQuoteRequest
from app.modules.delivery.quote_service import CdekQuoteService
from app.modules.orders.schemas import OrderCreationCommand


async def seed_checkout_point(session: AsyncSession, *, now: datetime | None = None) -> None:
    # Alembic seeds the directory state; create_all-based SQLite fixtures do not.
    await session.merge(
        PickupDirectoryState(key="cdek-ru", updated_at=now or datetime.now(timezone.utc))
    )
    await session.merge(
        PickupPoint(
            code="MSK1",
            search_text="moscow",
            payload={
                "code": "MSK1",
                "location": {"city": "Moscow", "address": "Moscow pickup point"},
            },
        )
    )


async def quote_checkout_command(
    settings: Settings,
    session: AsyncSession,
    command: OrderCreationCommand,
    *,
    now: datetime | None = None,
) -> OrderCreationCommand:
    prepared = await CdekQuoteService(settings, None).prepare_for_verification(
        session,
        CdekQuoteRequest(
            city=command.delivery_city,
            delivery_address=command.delivery_address,
            delivery_method=command.delivery_method,
            cdek_point_code=command.cdek_point_code,
            cart_items=[
                {"product_id": i.product_id, "quantity": i.quantity} for i in command.items
            ],
        ),
        now=now,
    )
    return command.model_copy(
        update={
            "delivery_quote_token": DeliveryQuoteProof(settings).issue(
                prepared, Decimal("50.00"), now=now
            ),
        }
    )
