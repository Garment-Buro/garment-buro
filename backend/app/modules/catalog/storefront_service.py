from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from datetime import timezone
from decimal import Decimal
from typing import Any
from urllib.parse import quote

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.catalog.constructor_schemas import ConstructorProductResponse
from app.modules.catalog.constructor_service import ConstructorService
from app.modules.catalog.pricing import (
    ConstructorPriceInput,
    ProductPriceResponse,
    calculate_customization_price,
)
from app.modules.catalog.storefront_repository import COLLECTION_IMAGE_ROLES, StorefrontRepository
from app.modules.catalog.storefront_schemas import (
    CollectionProductResponse,
    Price,
    StorefrontCardResponse,
    StorefrontOptionsResponse,
    StorefrontPageResponse,
    StorefrontQuery,
)


class InvalidStorefrontCursor(ValueError):
    pass


class CursorPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(strict=True, ge=1, le=1)
    product_id: int = Field(strict=True, gt=0, le=2_147_483_647)
    price: Price
    created_at: AwareDatetime
    filters: str = Field(pattern=r"^[a-f0-9]{64}$")


def filter_fingerprint(query: StorefrontQuery) -> str:
    data = query.model_dump(mode="json", exclude={"limit", "cursor"})
    for key in ("ids", "colors", "category_ids"):
        data[key] = sorted(set(data[key]))
    data["query"] = data["query"].strip()
    # Decimal spelling must not make equal filters incompatible (e.g. 3 and 3.00).
    for key in ("min_price", "max_price"):
        if data[key] is not None:
            data[key] = str(Decimal(data[key]).normalize())
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class StorefrontService:
    def __init__(self, settings: Settings, repository: StorefrontRepository | None = None):
        self.settings = settings
        self.repository = repository or StorefrontRepository()

    async def price_product(
        self,
        session: AsyncSession,
        product_id: int,
        design: ConstructorPriceInput,
    ) -> ProductPriceResponse | None:
        base_price = await self.repository.public_price(session, product_id)
        if base_price is None:
            return None
        quote = calculate_customization_price(base_price, design)
        return ProductPriceResponse(product_id=product_id, **quote.model_dump())

    async def get_product(
        self, session: AsyncSession, product_id: int
    ) -> ConstructorProductResponse | None:
        return await ConstructorService(self.settings).get_product(session, product_id)

    async def collection_products(
        self, session: AsyncSession, *, product_ids: list[int]
    ) -> list[CollectionProductResponse]:
        ids = list(dict.fromkeys(product_ids))
        records = await self.repository.collection_products(session, ids)
        by_id = {row["id"]: row for row in records}
        images = await self.repository.card_images(
            session, list(by_id), roles=COLLECTION_IMAGE_ROLES
        )
        return [
            CollectionProductResponse(
                **by_id[product_id],
                **self._image_fields(images.get(product_id), by_id[product_id]["title"]),
            )
            for product_id in ids
            if product_id in by_id
        ]

    def _image_fields(self, image: Mapping[str, Any] | None, title: str) -> dict[str, str | None]:
        if not image:
            return {"image_url": None, "image_alt": None}
        public_base = (self.settings.minio_public_base_url or "").rstrip("/")
        if not public_base:
            raise RuntimeError("MINIO_PUBLIC_BASE_URL is required for storefront images")
        return {
            "image_url": f"{public_base}/{image['bucket_name']}/{quote(image['object_key'], safe='/')}",
            "image_alt": image["alt_text"] or title,
        }

    async def list_page(
        self, session: AsyncSession, *, query: StorefrontQuery
    ) -> StorefrontPageResponse:
        fingerprint = filter_fingerprint(query)
        position = None
        if query.cursor is not None:
            try:
                decoded = base64.b64decode(query.cursor, altchars=b"-_", validate=True)
                position = CursorPosition.model_validate_json(decoded)
                if position.filters != fingerprint:
                    raise InvalidStorefrontCursor
            except (ValueError, ValidationError) as error:
                raise InvalidStorefrontCursor("Invalid cursor for these catalog filters") from error
        records = await self.repository.list_page(
            session,
            query=query,
            after_id=position.product_id if position else None,
            after_price=position.price if position else None,
            after_created_at=position.created_at if position else None,
        )
        page = records[: query.limit]
        images = await self.repository.card_images(session, [row["id"] for row in page])
        items = []
        for row in page:
            card = StorefrontCardResponse.model_validate(
                {**row, **self._image_fields(images.get(row["id"]), row["title"])}
            )
            items.append(card)
        cursor = None
        if len(records) > query.limit:
            cursor = base64.urlsafe_b64encode(
                CursorPosition(
                    version=1,
                    product_id=page[-1]["id"],
                    price=page[-1]["price"],
                    created_at=page[-1]["_created_at"].replace(tzinfo=timezone.utc)
                    if page[-1]["_created_at"].tzinfo is None
                    else page[-1]["_created_at"],
                    filters=fingerprint,
                )
                .model_dump_json()
                .encode()
            ).decode()
        return StorefrontPageResponse(items=items, next_cursor=cursor)

    async def options(self, session: AsyncSession) -> StorefrontOptionsResponse:
        categories, colors = await self.repository.options(session)
        return StorefrontOptionsResponse(categories=categories, colors=colors)
