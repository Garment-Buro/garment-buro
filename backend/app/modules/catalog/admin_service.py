from __future__ import annotations

import base64
import hashlib
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.admin_repository import CatalogAdminRepository
from app.modules.catalog.admin_schemas import (
    CatalogAdminCommunity,
    CatalogAdminCounts,
    CatalogAdminDetail,
    CatalogAdminPage,
    CatalogAdminProduct,
    CatalogAdminQuery,
    CatalogAdminVariantDetail,
)
from app.modules.catalog.availability import available_stock, load_availability
from app.modules.catalog.editor_repository import CatalogEditorRepository
from app.modules.catalog.mapper import CatalogResponseMapper
from app.modules.partners.models import PartnerLanding


class InvalidCatalogAdminCursor(ValueError):
    pass


class AdminPosition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: int = Field(ge=1, le=1)
    product_id: int = Field(gt=0, le=2_147_483_647)
    value: str = Field(max_length=255)
    filters: str = Field(pattern=r"^[a-f0-9]{64}$")


def fingerprint(query: CatalogAdminQuery) -> str:
    return hashlib.sha256(query.model_dump_json(exclude={"cursor", "limit"}).encode()).hexdigest()


def read_position(query: CatalogAdminQuery) -> tuple[int | None, str | Decimal | int | None]:
    if query.cursor is None:
        return None, None
    try:
        position = AdminPosition.model_validate_json(
            base64.b64decode(query.cursor, altchars=b"-_", validate=True)
        )
        if position.filters != fingerprint(query):
            raise ValueError("Different filters")
        field = query.sort.split(":")[0]
        if field == "title":
            return position.product_id, position.value
        value = Decimal(position.value)
        if not value.is_finite() or not 0 <= value <= Decimal("999999999999999"):
            raise ValueError("Invalid numeric position")
        if field != "price":
            if value != value.to_integral_value():
                raise ValueError("Invalid integer position")
            value = int(value)
        if field == "id" and value != position.product_id:
            raise ValueError("Invalid ID position")
        return position.product_id, value
    except (ValueError, ValidationError, InvalidOperation) as error:
        raise InvalidCatalogAdminCursor("Invalid cursor for these catalog filters") from error


class CatalogAdminReadService:
    def __init__(self, mapper: CatalogResponseMapper):
        self.mapper = mapper

    async def detail(self, session: AsyncSession, product_id: int) -> CatalogAdminDetail | None:
        source = await CatalogEditorRepository.detail(
            session, product_id, settings=self.mapper.settings
        )
        if source is None:
            return None
        product = source.product
        await load_availability(
            session, [product], variants_by_product={product.id: source.variants}
        )
        mapped = self.mapper.product_detail_from_parts(
            product, source.variants, source.media_links, source.variant_media
        )
        return CatalogAdminDetail(
            **mapped.model_dump(exclude={"variants", "stock_quantity"}),
            stock_quantity=product.stock_quantity,
            reserved_quantity=product.reserved_quantity,
            available_stock_quantity=available_stock(product),
            variants=[
                CatalogAdminVariantDetail(
                    **view.model_dump(exclude={"stock_quantity"}),
                    sku=row.sku,
                    garment_size_id=row.garment_size_id,
                    fabric_id=row.fabric_id,
                    stock_quantity=row.stock_quantity,
                    reserved_quantity=row.reserved_quantity,
                    available_stock_quantity=available_stock(row),
                )
                for row, view in zip(source.variants, mapped.variants, strict=True)
            ],
        )

    @staticmethod
    async def counts(
        session: AsyncSession, *, include_communities: bool = False
    ) -> CatalogAdminCounts:
        counts = await CatalogAdminRepository.counts(session)
        return CatalogAdminCounts(
            garment_buro=counts.get("garment_buro", 0),
            user=counts.get("user", 0),
            communities=(await session.scalar(select(func.count()).select_from(PartnerLanding)))
            if include_communities
            else None,
        )

    async def list_page(
        self, session: AsyncSession, query: CatalogAdminQuery, *, include_communities: bool = False
    ) -> CatalogAdminPage:
        after_id, after_value = read_position(query)
        records = await CatalogAdminRepository.list_page(
            session, query, after_id=after_id, after_value=after_value
        )
        selected = records[: query.limit]
        products = [record[0] for record in selected]
        communities = (
            await CatalogAdminRepository.community_previews(session, [p.id for p in products])
            if include_communities
            else {}
        )
        items = []
        for product, _, category_name, garment_model_name, capacity, variant_count, sku in selected:
            mapped = self.mapper.product(product)
            image = next(
                (
                    candidate
                    for candidate in (
                        mapped.mobile_card_image,
                        mapped.image_left,
                        mapped.desktop_card_images,
                        mapped.gallery_images,
                    )
                    if candidate
                ),
                None,
            )
            items.append(
                CatalogAdminProduct(
                    id=product.id,
                    title=product.title,
                    slug=product.slug,
                    preset_source=product.preset_source,
                    tags=product.tags,
                    category_id=product.category_id,
                    garment_model_id=product.garment_model_id,
                    category_name=category_name,
                    garment_model_name=garment_model_name,
                    price=product.price,
                    old_price=product.old_price,
                    image_url=image.split(",", maxsplit=1)[0].strip() if image else None,
                    is_active=product.is_active,
                    stock_quantity=int(capacity),
                    variant_count=variant_count,
                    sku=sku,
                    community_count=(
                        communities[product.id][0]["total"] if product.id in communities else 0
                    )
                    if include_communities
                    else None,
                    communities=[
                        CatalogAdminCommunity(id=row["id"], title=row["title"], slug=row["slug"])
                        for row in communities.get(product.id, [])
                    ],
                )
            )
        cursor = None
        if len(records) > query.limit:
            product, value, *_ = selected[-1]
            cursor = base64.urlsafe_b64encode(
                AdminPosition(
                    version=1,
                    product_id=product.id,
                    value=str(value),
                    filters=fingerprint(query),
                )
                .model_dump_json()
                .encode()
            ).decode()
        return CatalogAdminPage(items=items, next_cursor=cursor)
