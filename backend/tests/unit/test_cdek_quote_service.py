from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.catalog.models import Product
from app.modules.delivery.provider import CdekTariffQuote
from app.modules.delivery.quote_schemas import CdekQuoteRequest
from app.modules.delivery.quote_service import CdekQuoteService, CdekQuoteValidationError


class QuoteProvider:
    def __init__(self) -> None:
        self.bodies: list[bytes] = []

    async def calculate_tariff(self, request_body: bytes) -> CdekTariffQuote:
        self.bodies.append(request_body)
        return CdekTariffQuote(
            delivery_sum=Decimal("450.25"),
            period_min=2,
            period_max=4,
        )


def _settings(path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
        catalog_reads_enabled=True,
        catalog_migration_fingerprint="a" * 64,
        minio_enabled=True,
        minio_access_key="access",
        minio_secret_key="secret",
        minio_public_base_url="https://cdn.example.test",
        cdek_quote_enabled=True,
        cdek_client_id="cdek-client",
        cdek_client_secret="cdek-secret",
    )


async def _create_database(path: Path) -> tuple[DatabaseManager, Product, Product]:
    database = DatabaseManager(_settings(path))
    await database.startup()
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    active = Product(
        title="Coat",
        price=Decimal("100.00"),
        is_active=True,
        weight_kg=Decimal("0.501"),
        height_cm=Decimal("10.01"),
        width_cm=Decimal("20.00"),
        length_cm=Decimal("30.20"),
    )
    inactive = Product(
        title="Archived coat",
        price=Decimal("100.00"),
        is_active=False,
        weight_kg=Decimal("1"),
        height_cm=Decimal("10"),
        width_cm=Decimal("20"),
        length_cm=Decimal("30"),
    )
    async with database.session() as session:
        session.add_all([active, inactive])
        await session.commit()
    return database, active, inactive


def test_cdek_quote_uses_server_catalog_and_stable_packages(tmp_path: Path) -> None:
    async def scenario() -> None:
        database, product, _ = await _create_database(tmp_path / "quote.db")
        provider = QuoteProvider()
        service = CdekQuoteService(database.settings, provider)
        command = CdekQuoteRequest.model_validate(
            {
                "city": "  Санкт-Петербург  ",
                "delivery_method": "cdek_pickup",
                "cart_items": [
                    {
                        "product_id": product.id,
                        "quantity": 1,
                        "weight": 1,
                        "length": 1,
                    },
                    {"product_id": product.id, "quantity": 1},
                ],
            }
        )
        try:
            async with database.session() as session:
                prepared = await service.prepare(session, command)
            quote = await service.calculate(prepared)
            payload = json.loads(prepared.body)

            assert provider.bodies == [prepared.body]
            assert quote.delivery_sum == Decimal("450.25")
            assert prepared.tariff_code == 136
            assert len(prepared.sha256) == 64
            assert payload["to_location"] == {
                "country_code": "RU",
                "city": "Санкт-Петербург",
            }
            assert payload["packages"] == [
                {
                    "height": 11,
                    "length": 31,
                    "number": f"quote-{product.id}-1",
                    "weight": 501,
                    "width": 20,
                },
                {
                    "height": 11,
                    "length": 31,
                    "number": f"quote-{product.id}-2",
                    "weight": 501,
                    "width": 20,
                },
            ]
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_cdek_quote_rejects_spoofed_or_incomplete_catalog_items(tmp_path: Path) -> None:
    async def scenario() -> None:
        database, product, inactive = await _create_database(tmp_path / "invalid-quote.db")
        service = CdekQuoteService(database.settings, QuoteProvider())
        try:
            for product_id, code in (
                (999999, "cdek_product_unavailable"),
                (inactive.id, "cdek_product_unavailable"),
            ):
                command = CdekQuoteRequest.model_validate(
                    {
                        "city": "Москва",
                        "delivery_method": "cdek_door",
                        "cart_items": [{"product_id": product_id, "quantity": 1}],
                    }
                )
                async with database.session() as session:
                    with pytest.raises(CdekQuoteValidationError, match=code):
                        await service.prepare(session, command)

            async with database.session() as session:
                catalog_product = await session.get(Product, product.id)
                assert catalog_product is not None
                catalog_product.weight_kg = Decimal("0")
                await session.commit()
            command = CdekQuoteRequest.model_validate(
                {
                    "city": "Москва",
                    "delivery_method": "cdek_door",
                    "cart_items": [{"product_id": product.id, "quantity": 1}],
                }
            )
            async with database.session() as session:
                with pytest.raises(CdekQuoteValidationError, match="cdek_logistics_missing"):
                    await service.prepare(session, command)
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_cdek_quote_enforces_package_limit_before_database_io(tmp_path: Path) -> None:
    settings = _settings(tmp_path / "limit.db").model_copy(update={"cdek_max_packages": 2})
    service = CdekQuoteService(settings, QuoteProvider())
    command = CdekQuoteRequest.model_validate(
        {
            "city": "Москва",
            "delivery_method": "cdek_door",
            "cart_items": [{"product_id": 1, "quantity": 3}],
        }
    )

    async def scenario() -> None:
        with pytest.raises(CdekQuoteValidationError, match="cdek_package_limit_exceeded"):
            await service.prepare(None, command)  # type: ignore[arg-type]

    asyncio.run(scenario())
