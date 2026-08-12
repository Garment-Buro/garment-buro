from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.delivery.constants import CDEK_PICKUP_DELIVERY_METHOD
from app.modules.delivery.logistics import centimeters_to_integer, kilograms_to_grams
from app.modules.delivery.provider import CdekQuoteProvider, CdekTariffQuote
from app.modules.delivery.quote_repository import CdekQuoteProduct, CdekQuoteRepository
from app.modules.delivery.quote_schemas import CdekQuoteRequest


class CdekQuoteValidationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class PreparedCdekQuote:
    body: bytes
    sha256: str
    tariff_code: int


class CdekQuoteService:
    """Build quotes from trusted catalog logistics before calling CDEK."""

    def __init__(
        self,
        settings: Settings,
        provider: CdekQuoteProvider,
        *,
        repository: CdekQuoteRepository | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.repository = repository or CdekQuoteRepository()

    async def prepare(
        self,
        session: AsyncSession,
        command: CdekQuoteRequest,
    ) -> PreparedCdekQuote:
        if not self.settings.cdek_quote_enabled:
            raise CdekQuoteValidationError("cdek_quote_disabled")

        quantities: dict[int, int] = {}
        for item in command.cart_items:
            quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity
        packages_count = sum(quantities.values())
        if packages_count > self.settings.cdek_max_packages:
            raise CdekQuoteValidationError("cdek_package_limit_exceeded")

        products = await self.repository.list_products(session, set(quantities))
        products_by_id = {product.product_id: product for product in products}
        if set(products_by_id) != set(quantities) or any(
            not product.is_active for product in products
        ):
            raise CdekQuoteValidationError("cdek_product_unavailable")

        tariff_code = (
            self.settings.cdek_warehouse_to_warehouse_tariff
            if command.delivery_method == CDEK_PICKUP_DELIVERY_METHOD
            else self.settings.cdek_warehouse_to_door_tariff
        )
        payload = {
            "type": 1,
            "currency": 1,
            "tariff_code": tariff_code,
            "from_location": {"code": self.settings.cdek_sender_city_code},
            "to_location": {"country_code": "RU", "city": command.city},
            "packages": self._packages(products_by_id, quantities),
        }
        body = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return PreparedCdekQuote(
            body=body,
            sha256=hashlib.sha256(body).hexdigest(),
            tariff_code=tariff_code,
        )

    async def calculate(self, prepared: PreparedCdekQuote) -> CdekTariffQuote:
        return await self.provider.calculate_tariff(prepared.body)

    @staticmethod
    def _packages(
        products: dict[int, CdekQuoteProduct],
        quantities: dict[int, int],
    ) -> list[dict[str, int | str]]:
        packages: list[dict[str, int | str]] = []
        for product_id in sorted(quantities):
            product = products[product_id]
            try:
                weight = kilograms_to_grams(product.weight_kg)
                height = centimeters_to_integer(product.height_cm)
                width = centimeters_to_integer(product.width_cm)
                length = centimeters_to_integer(product.length_cm)
            except ValueError as error:
                code = getattr(error, "code", "cdek_logistics_invalid")
                raise CdekQuoteValidationError(code) from error
            for unit_index in range(quantities[product_id]):
                packages.append(
                    {
                        "number": f"quote-{product_id}-{unit_index + 1}",
                        "weight": weight,
                        "length": length,
                        "width": width,
                        "height": height,
                    }
                )
        return packages
