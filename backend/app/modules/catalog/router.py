from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.catalog.admin_api import (
    get_catalog_admin_service,
    read_catalog_admin_detail,
    read_catalog_admin_page,
)
from app.modules.catalog.admin_schemas import (
    CatalogAdminCounts,
    CatalogAdminDetail,
    CatalogAdminPage,
    CatalogAdminQuery,
)
from app.modules.catalog.admin_service import CatalogAdminReadService
from app.modules.catalog.dependencies import require_catalog_writer
from app.modules.catalog.editor_media import (
    CatalogEditorMediaLimitError,
    catalog_editor_media_limit_detail,
)
from app.modules.catalog.editor_repository import (
    CatalogEditorVariantLimitError,
    catalog_editor_variant_limit_detail,
)
from app.modules.catalog.schemas import (
    ProductCategoryResponse,
    ProductCategoryUpdate,
    ProductCategoryWrite,
    ProductDeletedResponse,
    ProductDetailResponse,
    ProductUpdateRequest,
    ProductWriteRequest,
)
from app.modules.catalog.service import (
    CatalogInventoryReservedError,
    CatalogProductNotFoundError,
    CatalogProductVersionConflictError,
    CatalogReferenceNotFoundError,
    CatalogVersionConflictError,
    CatalogWriteService,
    UnknownCatalogMediaError,
    product_version_conflict_detail,
)
from app.modules.crm.category_directory_schemas import CategoryDirectoryQuery, CategoryPage
from app.modules.crm.category_directory_service import CategoryDirectoryService
from app.modules.crm.directory_api import read_reference_page
from app.modules.identity.models import User

router = APIRouter(
    prefix="/api/products", tags=["catalog-admin"], dependencies=[Depends(require_catalog_writer)]
)
write_router = APIRouter(prefix="/api/products", tags=["catalog-admin"])
category_router = APIRouter(
    prefix="/api/product-categories",
    tags=["catalog-admin"],
    dependencies=[Depends(require_catalog_writer)],
)
category_write_router = APIRouter(prefix="/api/product-categories", tags=["catalog-admin"])


def get_catalog_write_service(request: Request) -> CatalogWriteService:
    return CatalogWriteService(request.app.state.settings)


@router.get("", response_model=CatalogAdminPage)
async def list_products(
    response: Response,
    query: Annotated[CatalogAdminQuery, Query()],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CatalogAdminReadService, Depends(get_catalog_admin_service)],
) -> CatalogAdminPage:
    return await read_catalog_admin_page(response, session, service, query)


@router.get("/counts", response_model=CatalogAdminCounts)
async def product_counts(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CatalogAdminReadService, Depends(get_catalog_admin_service)],
) -> CatalogAdminCounts:
    response.headers["Cache-Control"] = "no-store"
    return await service.counts(session)


@category_router.get("", response_model=CategoryPage)
async def list_product_categories(
    response: Response,
    query: Annotated[CategoryDirectoryQuery, Query()],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> CategoryPage:
    return await read_reference_page(
        response, CategoryDirectoryService().page(session, "product-categories", query)
    )


@router.get("/{product_id}", response_model=CatalogAdminDetail)
async def get_product(
    product_id: int,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CatalogAdminReadService, Depends(get_catalog_admin_service)],
) -> CatalogAdminDetail:
    return await read_catalog_admin_detail(response, session, service, product_id)


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
    except CatalogReferenceNotFoundError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Catalog write conflict") from error


@write_router.put("/{product_id}", response_model=ProductDetailResponse)
async def update_product(
    product_id: int,
    payload: ProductUpdateRequest,
    user: Annotated[User, Depends(require_catalog_writer)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CatalogWriteService, Depends(get_catalog_write_service)],
) -> ProductDetailResponse:
    try:
        product = await service.update_product(
            session,
            product_id=product_id,
            expected_version=payload.expected_version,
            payload=payload,
            actor_user_id=user.id,
        )
        await session.commit()
        return product
    except CatalogProductNotFoundError as error:
        raise HTTPException(status_code=404, detail="Product not found") from error
    except CatalogProductVersionConflictError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail=product_version_conflict_detail()) from error
    except CatalogEditorVariantLimitError as error:
        await session.rollback()
        raise HTTPException(
            409, catalog_editor_variant_limit_detail(), headers={"Cache-Control": "no-store"}
        ) from error
    except CatalogEditorMediaLimitError as error:
        await session.rollback()
        raise HTTPException(
            409, catalog_editor_media_limit_detail(), headers={"Cache-Control": "no-store"}
        ) from error
    except CatalogInventoryReservedError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error
    except UnknownCatalogMediaError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except CatalogReferenceNotFoundError as error:
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


@category_write_router.post("", response_model=ProductCategoryResponse, status_code=201)
async def create_product_category(
    payload: ProductCategoryWrite,
    _user: Annotated[User, Depends(require_catalog_writer)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CatalogWriteService, Depends(get_catalog_write_service)],
) -> ProductCategoryResponse:
    try:
        category = await service.create_category(session, payload=payload)
        await session.commit()
        return category
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Product category conflict") from error


@category_write_router.put("/{category_id}", response_model=ProductCategoryResponse)
async def update_product_category(
    category_id: int,
    payload: ProductCategoryUpdate,
    _user: Annotated[User, Depends(require_catalog_writer)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CatalogWriteService, Depends(get_catalog_write_service)],
) -> ProductCategoryResponse:
    try:
        category = await service.update_category(
            session,
            category_id=category_id,
            expected_version=payload.expected_version,
            payload=ProductCategoryWrite.model_validate(
                payload.model_dump(exclude={"expected_version"})
            ),
        )
        await session.commit()
        return category
    except CatalogReferenceNotFoundError as error:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(error)) from error
    except CatalogVersionConflictError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Product category conflict") from error
