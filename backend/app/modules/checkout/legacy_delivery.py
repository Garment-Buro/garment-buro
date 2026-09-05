"""Compatibility delivery quote: provider failures are never free delivery."""

from decimal import Decimal

from fastapi import HTTPException

from cdek_client import CdekClient


async def quote_legacy_delivery(city: str, method: str, items: list[dict]) -> dict:
    if not city.strip() or method not in {"cdek_pickup", "cdek_door"}:
        raise HTTPException(422, "Укажите город и способ доставки")
    client = CdekClient()
    city_code = await client.get_city_code(city)
    if not city_code:
        raise HTTPException(503, "Не удалось рассчитать доставку. Попробуйте позже.")
    packages = []
    for item in items:
        quantity = int(item.get("quantity", 1))
        if not 1 <= quantity <= 99 or len(packages) + quantity > 100:
            raise HTTPException(422, "Слишком много мест для доставки")
        # Matches the existing legacy packaging contract until catalog logistics cutover.
        packages.extend([{"weight": 500, "length": 20, "width": 20, "height": 10}] * quantity)
    if not packages:
        raise HTTPException(422, "Корзина пуста")
    tariff = (client.warehouse_to_door_tariff if method == "cdek_door"
              else client.warehouse_to_warehouse_tariff)
    result = await client.calculate_tariffs_by_code(
        client.sender_city_code, city_code, tariff, packages,
    )
    if not result or "delivery_sum" not in result:
        raise HTTPException(503, "Расчёт доставки временно недоступен")
    price = Decimal(str(result["delivery_sum"]))
    if not price.is_finite() or price < 0:
        raise HTTPException(503, "Сервис доставки вернул некорректный тариф")
    return {"delivery_price": float(price), "period_min": result.get("period_min"),
            "period_max": result.get("period_max"), "tariff_code": tariff}
