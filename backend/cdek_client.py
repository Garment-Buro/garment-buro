from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import aiohttp

from app.core.config import Settings, get_settings
from app.core.exceptions import ExternalServiceError, IntegrationNotConfiguredError

logger = logging.getLogger(__name__)


class CdekClient:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        """Create a client without contacting CDEK during module import."""
        runtime_settings = settings or get_settings()
        self.client_id = client_id or Settings.secret_value(runtime_settings.cdek_client_id)
        self.client_secret = client_secret or Settings.secret_value(
            runtime_settings.cdek_client_secret
        )
        self.base_url = (base_url or runtime_settings.cdek_api_url).rstrip("/")
        self.sender_city_code = runtime_settings.cdek_sender_city_code
        self.warehouse_to_warehouse_tariff = runtime_settings.cdek_warehouse_to_warehouse_tariff
        self.warehouse_to_door_tariff = runtime_settings.cdek_warehouse_to_door_tariff
        self._token = {
            "access_token": "",
            "expires_at": datetime.min.replace(tzinfo=timezone.utc),
        }

    def _require_configured(self) -> None:
        if not self.client_id or not self.client_secret:
            raise IntegrationNotConfiguredError("CDEK is not configured")

    async def get_token(self) -> str:
        """Получает новый OAuth токен или возвращает действующий из кэша."""
        self._require_configured()
        if datetime.now(timezone.utc) < self._token["expires_at"]:
            return self._token["access_token"]

        url = f"{self.base_url}/oauth/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload) as resp:
                if resp.status != 200:
                    raise ExternalServiceError(f"CDEK OAuth returned HTTP {resp.status}")

                data = await resp.json()
                self._token["access_token"] = data["access_token"]
                self._token["expires_at"] = datetime.now(timezone.utc) + timedelta(
                    seconds=data["expires_in"] - 60
                )
                return self._token["access_token"]

    async def get_cities_by_name(self, city_name: str) -> list:
        """Поиск городов по названию (возвращает список совпадений)."""
        token = await self.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        params = {"city": city_name}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/location/cities", headers=headers, params=params
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        return data.get("items", [])
                return []

    async def get_city_code(self, city_name: str) -> int:
        """Получить код города (возвращает первый совпавший вариант)."""
        token = await self.get_token()
        url = f"{self.base_url}/location/cities?country_codes=RU&size=5&city={city_name}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={"Authorization": f"Bearer {token}"}) as resp:
                data = await resp.json()
                if isinstance(data, list) and data:
                    return data[0]["code"]
                return None

    async def get_delivery_points(self, city_code: int) -> list:
        """Получить список ПВЗ в городе по коду города."""
        token = await self.get_token()
        url = f"{self.base_url}/deliverypoints?city_code={city_code}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={"Authorization": f"Bearer {token}"}) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None

    async def calculate_tariffs_by_code(
        self, from_code: int, to_code: int, tariff_code: int, packages: list
    ) -> dict:
        token = await self.get_token()
        url = f"{self.base_url}/calculator/tariff"
        payload = {
            "type": 1,
            "tariff_code": tariff_code,
            "from_location": {"code": from_code},
            "to_location": {"code": to_code},
            "packages": packages,
        }

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = {
                        "delivery_sum": data.get("delivery_sum"),
                        "period_min": data.get("period_min"),
                        "period_max": data.get("period_max"),
                        "total_sum": data.get("total_sum"),
                    }
                    return results
                return None

    async def register_order(self, order) -> str:
        """Регистрация заказа в СДЭК."""
        token = await self.get_token()
        url = f"{self.base_url}/orders"

        tariff_code = (
            self.warehouse_to_door_tariff
            if order.delivery_method == "cdek_door"
            else self.warehouse_to_warehouse_tariff
        )

        packages = []
        if order.cart_items:
            import json

            try:
                items = json.loads(order.cart_items)
                for item in items:
                    qty = item.get("quantity", 1)
                    packages.append(
                        {
                            "weight": int(item.get("weight", 500)),
                            "length": int(item.get("length", 20)),
                            "width": int(item.get("width", 20)),
                            "height": int(item.get("height", 10)),
                            "items": [
                                {
                                    "name": str(item.get("title", "Товар")),
                                    "ware_key": str(item.get("id", "1")),
                                    "payment": {"value": 0},
                                    "cost": item.get("price", 0),
                                    "amount": qty,
                                    "weight": int(item.get("weight", 500)),
                                }
                            ],
                        }
                    )
            except (TypeError, ValueError):
                logger.warning("Unable to parse order items for CDEK payload")

        if not packages:
            packages = [{"weight": 1000, "length": 20, "width": 20, "height": 10}]

        recipient_name = " ".join(
            filter(None, [order.last_name, order.first_name, getattr(order, "patronymic", None)])
        )
        if not recipient_name:
            recipient_name = "Покупатель"

        payload = {
            "type": 1,
            "tariff_code": tariff_code,
            "recipient": {
                "name": recipient_name,
                "phones": [{"number": order.phone}],
            },
            "packages": packages,
            "from_location": {"code": self.sender_city_code},
        }

        recipient_email = getattr(order, "recipient_email", None) or order.email
        if recipient_email:
            payload["recipient"]["email"] = recipient_email

        if tariff_code == self.warehouse_to_warehouse_tariff:
            payload["delivery_point"] = order.cdek_point_code
        else:
            payload["to_location"] = {"address": order.delivery_address}

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status in (200, 201, 202):
                    data = await resp.json()
                    entity = data.get("entity", {})
                    return entity.get("uuid")
                logger.warning(
                    "CDEK order registration returned HTTP %s",
                    resp.status,
                )
                return None

    async def get_order_info(self, order_uuid: str) -> tuple:
        """Получить полную информацию о существующем заказе по UUID."""
        token = await self.get_token()
        url = f"{self.base_url}/orders/{order_uuid}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={"Authorization": f"Bearer {token}"}) as resp:
                return resp.status, await resp.json()

    async def get_barcode_url(self, order_uuid: str) -> str:
        """Сгенерировать и получить URL для скачивания PDF баркода заказа."""
        token = await self.get_token()
        post_data = {"orders": [{"order_uuid": order_uuid}], "format": "A6"}
        url = f"{self.base_url}/print/barcodes"

        async with aiohttp.ClientSession() as session:
            # Запрос на генерацию файла
            async with session.post(
                url, json=post_data, headers={"Authorization": f"Bearer {token}"}
            ) as resp:
                if resp.status == 202:
                    data = await resp.json()
                    barcode_uuid = data.get("entity", {}).get("uuid")

                    await asyncio.sleep(5)  # Ожидаем готовности файла на сервере

                    # Забираем ссылку на сгенерированный файл
                    get_url = f"{self.base_url}/print/barcodes/{barcode_uuid}"
                    async with session.get(
                        get_url, headers={"Authorization": f"Bearer {token}"}
                    ) as get_resp:
                        if get_resp.status == 200:
                            get_data = await get_resp.json()
                            return get_data.get("entity", {}).get("url")
        return None

    async def download_pdf_bytes(self, pdf_url: str) -> bytes:
        """Скачивает готовый PDF-файл (накладная или баркод) в виде байт-строки."""
        token = await self.get_token()
        async with aiohttp.ClientSession() as session:
            async with session.get(pdf_url, headers={"Authorization": f"Bearer {token}"}) as resp:
                if resp.status == 200:
                    return await resp.read()
                return None
