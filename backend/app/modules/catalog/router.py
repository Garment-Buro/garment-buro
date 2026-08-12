from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.catalog.dependencies import require_catalog_writer
from app.modules.catalog.mapper import CatalogResponseMapper
from app.modules.catalog.schemas import (
    ProductDeletedResponse,
    ProductDetailResponse,
    ProductResponse,
    ProductVariantResponse,
    ProductVariantWriteRequest,
    ProductWriteRequest,
)
from app.modules.catalog.service import (
    CatalogInventoryReservedError,
    CatalogProductNotFoundError,
    CatalogService,
    CatalogVariantNotFoundError,
    CatalogWriteService,
    UnknownCatalogMediaError,
)
from app.modules.identity.models import User

router = APIRouter(prefix="/api/products", tags=["catalog"])
write_router = APIRouter(prefix="/api/products", tags=["catalog-admin"])
variant_write_router = APIRouter(prefix="/api/variants", tags=["catalog-admin"])


def get_catalog_service(request: Request) -> CatalogService:
    return CatalogService(CatalogResponseMapper(request.app.state.settings))


def get_catalog_write_service(request: Request) -> CatalogWriteService:
    return CatalogWriteService(request.app.state.settings)


@router.get("", response_model=list[ProductResponse])
async def list_products(
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> list[ProductResponse]:
    return await service.list_products(session)


@router.get("/{product_id}", response_model=ProductDetailResponse)
async def get_product(
    product_id: int,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> ProductDetailResponse:
    product = await service.get_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/{product_id}/variants", response_model=list[ProductVariantResponse])
async def list_product_variants(
    product_id: int,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
) -> list[ProductVariantResponse]:
    return await service.list_variants(session, product_id)


@write_router.post("", response_model=ProductDetailResponse)
async def create_product(
    payload: ProductWriteRequest,
    user: Annotated[User, Depends(require_catalog_writer)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CatalogWriteService, Depends(get_catalog_write_service)],
) -> ProductDetailResponse:
    try:
        product = await service.create_product(
            session,
            payload=payload,
            actor_user_id=user.id,
        )
        await session.commit()
        return product
    except UnknownCatalogMediaError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Catalog write conflict") from error


@write_router.put("/{product_id}", response_model=ProductDetailResponse)
async def update_product(
    product_id: int,
    payload: ProductWriteRequest,
    user: Annotated[User, Depends(require_catalog_writer)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CatalogWriteService, Depends(get_catalog_write_service)],
) -> ProductDetailResponse:
    try:
        product = await service.update_product(
            session,
            product_id=product_id,
            payload=payload,
            actor_user_id=user.id,
        )
        await session.commit()
        return product
    except CatalogProductNotFoundError as error:
        raise HTTPException(status_code=404, detail="Product not found") from error
    except CatalogInventoryReservedError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error
    except UnknownCatalogMediaError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Catalog write conflict") from error


@write_router.delete("/{product_id}", response_model=ProductDeletedResponse)
async def delete_product(
    product_id: int,
    user: Annotated[User, Depends(require_catalog_writer)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CatalogWriteService, Depends(get_catalog_write_service)],
) -> ProductDeletedResponse:
    try:
        await service.delete_product(
            session,
            product_id=product_id,
            actor_user_id=user.id,
        )
        await session.commit()
        return ProductDeletedResponse()
    except CatalogProductNotFoundError as error:
        raise HTTPException(status_code=404, detail="Product not found") from error
    except CatalogInventoryReservedError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Catalog write conflict") from error


@variant_write_router.put("/{variant_id}", response_model=ProductVariantResponse)
async def update_variant(
    variant_id: int,
    payload: ProductVariantWriteRequest,
    user: Annotated[User, Depends(require_catalog_writer)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CatalogWriteService, Depends(get_catalog_write_service)],
) -> ProductVariantResponse:
    try:
        variant = await service.update_variant(
            session,
            variant_id=variant_id,
            payload=payload,
            actor_user_id=user.id,
        )
        await session.commit()
        return variant
    except CatalogVariantNotFoundError as error:
        raise HTTPException(status_code=404, detail="Variant not found") from error
    except CatalogInventoryReservedError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error
    except UnknownCatalogMediaError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Catalog write conflict") from error
