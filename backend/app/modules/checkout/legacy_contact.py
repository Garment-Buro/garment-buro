"""Adapt new buyer/recipient data to the transitional order storage."""

import json
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

from app.db.session import DatabaseManager
from app.modules.checkout.contact import CheckoutContact
from app.modules.checkout.customer import prepare_checkout_customer
from app.modules.checkout.legacy_delivery import quote_legacy_delivery
from app.modules.delivery.directory import DIRECTORY_KEY
from app.modules.delivery.directory_models import PickupDirectoryState, PickupPoint


async def prepare_legacy_contact_order(
    payload: dict, *, buyer: CheckoutContact, recipient: CheckoutContact | None,
    database: DatabaseManager | None,
) -> dict:
    if database is None or not database.enabled:
        raise HTTPException(503, "Личный кабинет временно недоступен")
    if not str(payload.get("delivery_city") or "").strip() or not str(
        payload.get("delivery_address") or ""
    ).strip():
        raise HTTPException(422, "Укажите адрес доставки")
    method = payload.get("delivery_method")
    if method not in {"cdek_pickup", "cdek_door"}:
        raise HTTPException(422, "Выберите способ доставки")
    if method == "cdek_pickup":
        async with database.session() as session:
            state = await session.get(PickupDirectoryState, DIRECTORY_KEY)
            if state is None or state.updated_at is None or (
                datetime.now(UTC) - state.updated_at.replace(tzinfo=UTC) > timedelta(days=7)
            ):
                raise HTTPException(503, "Справочник СДЭК требует обновления")
            point = await session.get(PickupPoint, payload.get("cdek_point_code") or "")
            if point is None:
                raise HTTPException(422, "Выберите действующий пункт СДЭК")
            location = point.payload["location"]
            payload.update(delivery_city=location["city"], delivery_address=(
                location.get("address_full") or f'{location["city"]}, {location["address"]}'
            ))
    else:
        payload["cdek_point_code"] = None
    try:
        items = json.loads(payload.get("cart_items") or "[]")
        if not isinstance(items, list) or not items or len(items) > 100:
            raise ValueError("Invalid cart")
    except (TypeError, ValueError) as error:
        raise HTTPException(422, "Проверьте состав корзины") from error
    try:
        quote = await quote_legacy_delivery(payload["delivery_city"], method, items)
    except HTTPException:
        raise
    except Exception as error:  # noqa: BLE001 - do not disclose provider/configuration errors
        raise HTTPException(503, "Расчёт доставки временно недоступен") from error
    if payload.get("delivery_price") != quote["delivery_price"]:
        raise HTTPException(409, "Стоимость доставки изменилась. Повторите расчёт.")
    await prepare_checkout_customer(database, buyer.email)
    recipient = recipient or buyer
    payload.update(email=buyer.email, buyer_name=buyer.name, buyer_phone=buyer.phone,
                   first_name=recipient.name, last_name="", patronymic="",
                   phone=recipient.phone, recipient_email=recipient.email)
    return payload
