import base64
import hashlib
from datetime import timezone
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.production.client_repository import ClientScope, ProductionClientRepository
from app.modules.production.client_schemas import (
    ClientHistoryPage,
    ClientHistoryQuery,
    ClientOrderSummary,
    ClientTicketSummary,
)


def money(value):
    return format(value or 0, ".2f")


class InvalidClientHistoryCursor(ValueError):
    pass


class ClientHistoryPosition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: int = Field(ge=1, le=1)
    id: int = Field(gt=0, le=2_147_483_647)
    at: AwareDatetime
    filters: str = Field(pattern=r"^[a-f0-9]{64}$")


class ProductionClientService:
    async def detail(self, session: AsyncSession, *, key: str):
        scope = ClientScope.parse(key)
        latest = await ProductionClientRepository.latest(session, scope)
        if latest is None:
            return None
        account = (
            await ProductionClientRepository.account(session, scope.value)
            if scope.kind == "user"
            else None
        )
        totals = await ProductionClientRepository.totals(session, scope)
        return {
            "key": key,
            "name": latest.buyer_name
            or " ".join(x for x in (latest.first_name, latest.last_name) if x),
            "email": latest.email,
            "phone": latest.buyer_phone or latest.phone,
            "orders_count": totals.orders_count,
            "orders_total": money(totals.orders_total),
            "paid_orders_total": money(totals.paid_orders_total),
            "tickets_count": totals.tickets_count,
            "account": None
            if account is None
            else {
                "id": account.id,
                "email": account.email,
                "phone": account.phone,
                "username": account.username,
                "registered_at": account.registered_at,
                "email_verified": account.email_verified_at is not None,
                "gender": account.gender,
                "birth_date": account.birth_date,
                "height_cm": money(account.height_cm) if account.height_cm is not None else None,
                "weight_kg": money(account.weight_kg) if account.weight_kg is not None else None,
            },
            "recipient": {
                "name": " ".join(
                    x for x in (latest.first_name, latest.last_name, latest.patronymic) if x
                ),
                "phone": latest.phone,
                "email": latest.recipient_email,
                "patronymic": latest.patronymic,
                "city": latest.delivery_city,
                "address": latest.delivery_address,
                "delivery_method": latest.delivery_method,
                "pickup_point": latest.cdek_point_code,
            },
        }

    async def history(
        self,
        session: AsyncSession,
        *,
        kind: Literal["orders", "tickets"],
        query: ClientHistoryQuery,
    ):
        scope = ClientScope.parse(query.key)
        fingerprint = hashlib.sha256(f"{kind}:{query.key}".encode()).hexdigest()
        after = None
        if query.cursor is not None:
            try:
                position = ClientHistoryPosition.model_validate_json(
                    base64.b64decode(query.cursor, altchars=b"-_", validate=True)
                )
                if position.filters != fingerprint:
                    raise ValueError("Different client or history")
                after = (position.at, position.id)
            except (ValueError, ValidationError) as error:
                raise InvalidClientHistoryCursor(
                    "Invalid cursor for this client history"
                ) from error
        reader = (
            ProductionClientRepository.orders
            if kind == "orders"
            else ProductionClientRepository.tickets
        )
        records = await reader(session, scope, limit=query.limit + 1, after=after)
        selected = records[: query.limit]
        cursor = None
        if len(records) > query.limit:
            last = selected[-1]
            at = last.created_at if kind == "orders" else last.updated_at
            at = at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at
            cursor = base64.urlsafe_b64encode(
                ClientHistoryPosition(version=1, id=last.id, at=at, filters=fingerprint)
                .model_dump_json()
                .encode()
            ).decode()
        if kind == "orders":
            items = [
                ClientOrderSummary(**{**dict(row), "total": money(row.total_price)})
                for row in selected
            ]
            return ClientHistoryPage[ClientOrderSummary](items=items, next_cursor=cursor)
        return ClientHistoryPage[ClientTicketSummary](
            items=[ClientTicketSummary.model_validate(dict(row)) for row in selected],
            next_cursor=cursor,
        )
