from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import invalid_cursor_error
from app.db.session import get_database_session
from app.modules.catalog.constructor_schemas import ConstructorProductResponse
from app.modules.catalog.pricing import ConstructorPriceInput, ProductPriceResponse
from app.modules.catalog.storefront_schemas import (
    CollectionProductResponse,
    CollectionProductsQuery,
    StorefrontOptionsResponse,
    StorefrontPageResponse,
    StorefrontQuery,
)
from app.modules.catalog.storefront_service import InvalidStorefrontCursor, StorefrontService

router = APIRouter(prefix="/api/catalog", tags=["storefront"])
Session = Annotated[AsyncSession, Depends(get_database_session)]


def get_storefront_service(request: Request) -> StorefrontService:
    return StorefrontService(request.app.state.settings)


Service = Annotated[StorefrontService, Depends(get_storefront_service)]


@router.post("/products/{product_id}/price", response_model=ProductPriceResponse)
async def price_product(
    product_id: Annotated[int, Path(gt=0, le=2_147_483_647)],
    design: ConstructorPriceInput,
    session: Session,
    service: Service,
    response: Response,
):
    quote = await service.price_product(session, product_id, design)
    if quote is None:
        raise HTTPException(
            status_code=404, detail="Product not found", headers={"Cache-Control": "no-store"}
        )
    response.headers["Cache-Control"] = "no-store"
    return quote


@router.get("/products/{product_id}", response_model=ConstructorProductResponse)
async def get_product(
    product_id: Annotated[int, Path(gt=0, le=2_147_483_647)],
    session: Session,
    service: Service,
    response: Response,
):
    product = await service.get_product(session, product_id)
    if product is None:
        raise HTTPException(
            status_code=404, detail="Product not found", headers={"Cache-Control": "no-store"}
        )
    response.headers["Cache-Control"] = "no-store"
    return product


@router.get("/collection-products", response_model=list[CollectionProductResponse])
async def get_collection_products(
    query: Annotated[CollectionProductsQuery, Query()], session: Session, service: Service
):
    return await service.collection_products(session, product_ids=query.ids)


@router.get("/products", response_model=StorefrontPageResponse)
async def list_products(
    query: Annotated[StorefrontQuery, Query()], session: Session, service: Service
):
    try:
        return await service.list_page(session, query=query)
    except InvalidStorefrontCursor as error:
        raise invalid_cursor_error() from error


@router.get("/options", response_model=StorefrontOptionsResponse)
async def get_options(session: Session, service: Service, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return await service.options(session)
