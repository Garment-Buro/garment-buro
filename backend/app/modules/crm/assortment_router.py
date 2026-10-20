from __future__ import annotations

from collections.abc import Awaitable
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.catalog.admin_api import get_catalog_admin_service, read_catalog_admin_page
from app.modules.catalog.admin_schemas import (
    CatalogAdminCounts,
    CatalogAdminPage,
    CatalogAdminQuery,
)
from app.modules.catalog.admin_service import CatalogAdminReadService
from app.modules.crm.assortment_schemas import (
    CrmAccessoryCategoryRead,
    CrmAccessoryCategoryUpdate,
    CrmAccessoryCategoryWrite,
    CrmAccessoryRead,
    CrmAccessoryUpdate,
    CrmAccessoryWrite,
    CrmGarmentAccessoryRequirementRead,
    CrmGarmentAccessoryRequirementUpdate,
    CrmGarmentAccessoryRequirementWrite,
    CrmGarmentFabricRequirementRead,
    CrmGarmentFabricRequirementUpdate,
    CrmGarmentFabricRequirementWrite,
    CrmGarmentPackagingRuleRead,
    CrmGarmentPackagingRuleUpdate,
    CrmGarmentPackagingRuleWrite,
    CrmGarmentPatternRead,
    CrmGarmentPatternUpdate,
    CrmGarmentPatternWrite,
    CrmPackagingBoxRead,
    CrmPackagingBoxUpdate,
    CrmPackagingBoxWrite,
)
from app.modules.crm.assortment_service import (
    CrmAssortmentConflictError,
    CrmAssortmentNotFoundError,
    CrmAssortmentService,
    CrmAssortmentVersionConflictError,
)
from app.modules.crm.dependencies import require_crm_reader
from app.modules.crm.directory_api import read_reference_page
from app.modules.crm.directory_schemas import FabricRequirementPage, RequirementDirectoryQuery
from app.modules.crm.directory_service import ReferenceDirectoryService
from app.modules.crm.pattern_directory_schemas import PatternFilePage, PatternFileQuery
from app.modules.crm.pattern_directory_service import PatternDirectoryService
from app.modules.crm.stock_directory_schemas import (
    AccessoryCategoryPage,
    AccessoryCategoryQuery,
    AccessoryDirectoryPage,
    AccessoryDirectoryQuery,
    AccessoryRequirementPage,
    AccessoryRequirementQuery,
    BoxDirectoryPage,
    BoxDirectoryQuery,
    PackagingRulePage,
    PackagingRuleQuery,
)
from app.modules.crm.stock_directory_service import StockDirectoryService
from app.modules.identity.models import User

router = APIRouter(prefix="/api/crm/assortment", tags=["crm-assortment"])
write_router = APIRouter(prefix="/api/crm/assortment", tags=["crm-assortment-write"])
T = TypeVar("T")


def get_assortment_service() -> CrmAssortmentService:
    return CrmAssortmentService()


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.get("/products", response_model=CatalogAdminPage)
async def list_assortment_products(
    response: Response,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CatalogAdminReadService, Depends(get_catalog_admin_service)],
    query: Annotated[CatalogAdminQuery, Query()],
) -> CatalogAdminPage:
    return await read_catalog_admin_page(response, session, service, query)


@router.get("/product-counts", response_model=CatalogAdminCounts)
async def assortment_product_counts(
    response: Response,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> CatalogAdminCounts:
    _no_store(response)
    return await CatalogAdminReadService.counts(session)


async def _write(session: AsyncSession, operation: Awaitable[T]) -> T:
    try:
        result = await operation
        await session.commit()
        return result
    except CrmAssortmentNotFoundError as error:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(error)) from error
    except CrmAssortmentVersionConflictError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error
    except CrmAssortmentConflictError as error:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Assortment write conflict") from error


@router.get("/patterns", response_model=PatternFilePage)
async def list_patterns(
    response: Response,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    query: Annotated[PatternFileQuery, Query()],
) -> PatternFilePage:
    return await read_reference_page(
        response, PatternDirectoryService().page(session, "patterns", query)
    )


@write_router.post("/patterns", response_model=CrmGarmentPatternRead, status_code=201)
async def create_pattern(
    payload: CrmGarmentPatternWrite,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmAssortmentService, Depends(get_assortment_service)],
) -> CrmGarmentPatternRead:
    return await _write(session, service.create_pattern(session, payload))


@write_router.put("/patterns/{pattern_id}", response_model=CrmGarmentPatternRead)
async def update_pattern(
    pattern_id: Annotated[int, Path(ge=1)],
    payload: CrmGarmentPatternUpdate,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmAssortmentService, Depends(get_assortment_service)],
) -> CrmGarmentPatternRead:
    return await _write(
        session,
        service.update_pattern(
            session,
            pattern_id=pattern_id,
            expected_version=payload.expected_version,
            payload=CrmGarmentPatternWrite.model_validate(payload.model_dump()),
        ),
    )


@router.get("/fabric-requirements", response_model=FabricRequirementPage)
async def list_fabric_requirements(
    response: Response,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    query: Annotated[RequirementDirectoryQuery, Query()],
) -> FabricRequirementPage:
    return await read_reference_page(
        response, ReferenceDirectoryService().fabric_requirements(session, query)
    )


@write_router.post(
    "/fabric-requirements",
    response_model=CrmGarmentFabricRequirementRead,
    status_code=201,
)
async def create_fabric_requirement(
    payload: CrmGarmentFabricRequirementWrite,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmAssortmentService, Depends(get_assortment_service)],
) -> CrmGarmentFabricRequirementRead:
    return await _write(session, service.create_fabric_requirement(session, payload))


@write_router.put(
    "/fabric-requirements/{requirement_id}",
    response_model=CrmGarmentFabricRequirementRead,
)
async def update_fabric_requirement(
    requirement_id: Annotated[int, Path(ge=1)],
    payload: CrmGarmentFabricRequirementUpdate,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmAssortmentService, Depends(get_assortment_service)],
) -> CrmGarmentFabricRequirementRead:
    return await _write(
        session,
        service.update_fabric_requirement(
            session,
            requirement_id=requirement_id,
            expected_version=payload.expected_version,
            payload=CrmGarmentFabricRequirementWrite.model_validate(payload.model_dump()),
        ),
    )


@router.get("/accessory-categories", response_model=AccessoryCategoryPage)
async def list_accessory_categories(
    response: Response,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    query: Annotated[AccessoryCategoryQuery, Query()],
) -> AccessoryCategoryPage:
    return await read_reference_page(
        response, StockDirectoryService().page(session, "accessory-categories", query)
    )


@write_router.post(
    "/accessory-categories",
    response_model=CrmAccessoryCategoryRead,
    status_code=201,
)
async def create_accessory_category(
    payload: CrmAccessoryCategoryWrite,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmAssortmentService, Depends(get_assortment_service)],
) -> CrmAccessoryCategoryRead:
    return await _write(session, service.create_category(session, payload))


@write_router.put(
    "/accessory-categories/{category_id}",
    response_model=CrmAccessoryCategoryRead,
)
async def update_accessory_category(
    category_id: Annotated[int, Path(ge=1)],
    payload: CrmAccessoryCategoryUpdate,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmAssortmentService, Depends(get_assortment_service)],
) -> CrmAccessoryCategoryRead:
    return await _write(
        session,
        service.update_category(
            session,
            category_id=category_id,
            expected_version=payload.expected_version,
            payload=CrmAccessoryCategoryWrite.model_validate(payload.model_dump()),
        ),
    )


@router.get("/accessories", response_model=AccessoryDirectoryPage)
async def list_accessories(
    response: Response,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    query: Annotated[AccessoryDirectoryQuery, Query()],
) -> AccessoryDirectoryPage:
    return await read_reference_page(
        response, StockDirectoryService().page(session, "accessories", query)
    )


@write_router.post("/accessories", response_model=CrmAccessoryRead, status_code=201)
async def create_accessory(
    payload: CrmAccessoryWrite,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmAssortmentService, Depends(get_assortment_service)],
) -> CrmAccessoryRead:
    return await _write(session, service.create_accessory(session, payload))


@write_router.put("/accessories/{accessory_id}", response_model=CrmAccessoryRead)
async def update_accessory(
    accessory_id: Annotated[int, Path(ge=1)],
    payload: CrmAccessoryUpdate,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmAssortmentService, Depends(get_assortment_service)],
) -> CrmAccessoryRead:
    return await _write(
        session,
        service.update_accessory(
            session,
            accessory_id=accessory_id,
            expected_version=payload.expected_version,
            payload=CrmAccessoryWrite.model_validate(payload.model_dump()),
        ),
    )


@router.get("/accessory-requirements", response_model=AccessoryRequirementPage)
async def list_accessory_requirements(
    response: Response,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    query: Annotated[AccessoryRequirementQuery, Query()],
) -> AccessoryRequirementPage:
    return await read_reference_page(
        response, StockDirectoryService().page(session, "accessory-requirements", query)
    )


@write_router.post(
    "/accessory-requirements",
    response_model=CrmGarmentAccessoryRequirementRead,
    status_code=201,
)
async def create_accessory_requirement(
    payload: CrmGarmentAccessoryRequirementWrite,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmAssortmentService, Depends(get_assortment_service)],
) -> CrmGarmentAccessoryRequirementRead:
    return await _write(session, service.create_accessory_requirement(session, payload))


@write_router.put(
    "/accessory-requirements/{requirement_id}",
    response_model=CrmGarmentAccessoryRequirementRead,
)
async def update_accessory_requirement(
    requirement_id: Annotated[int, Path(ge=1)],
    payload: CrmGarmentAccessoryRequirementUpdate,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmAssortmentService, Depends(get_assortment_service)],
) -> CrmGarmentAccessoryRequirementRead:
    return await _write(
        session,
        service.update_accessory_requirement(
            session,
            requirement_id=requirement_id,
            expected_version=payload.expected_version,
            payload=CrmGarmentAccessoryRequirementWrite.model_validate(payload.model_dump()),
        ),
    )


@router.get("/boxes", response_model=BoxDirectoryPage)
async def list_boxes(
    response: Response,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    query: Annotated[BoxDirectoryQuery, Query()],
) -> BoxDirectoryPage:
    return await read_reference_page(
        response, StockDirectoryService().page(session, "boxes", query)
    )


@write_router.post("/boxes", response_model=CrmPackagingBoxRead, status_code=201)
async def create_box(
    payload: CrmPackagingBoxWrite,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmAssortmentService, Depends(get_assortment_service)],
) -> CrmPackagingBoxRead:
    return await _write(session, service.create_box(session, payload))


@write_router.put("/boxes/{box_id}", response_model=CrmPackagingBoxRead)
async def update_box(
    box_id: Annotated[int, Path(ge=1)],
    payload: CrmPackagingBoxUpdate,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmAssortmentService, Depends(get_assortment_service)],
) -> CrmPackagingBoxRead:
    return await _write(
        session,
        service.update_box(
            session,
            box_id=box_id,
            expected_version=payload.expected_version,
            payload=CrmPackagingBoxWrite.model_validate(payload.model_dump()),
        ),
    )


@router.get("/packaging-rules", response_model=PackagingRulePage)
async def list_packaging_rules(
    response: Response,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    query: Annotated[PackagingRuleQuery, Query()],
) -> PackagingRulePage:
    return await read_reference_page(
        response, StockDirectoryService().page(session, "packaging-rules", query)
    )


@write_router.post(
    "/packaging-rules",
    response_model=CrmGarmentPackagingRuleRead,
    status_code=201,
)
async def create_packaging_rule(
    payload: CrmGarmentPackagingRuleWrite,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmAssortmentService, Depends(get_assortment_service)],
) -> CrmGarmentPackagingRuleRead:
    return await _write(session, service.create_packaging_rule(session, payload))


@write_router.put(
    "/packaging-rules/{rule_id}",
    response_model=CrmGarmentPackagingRuleRead,
)
async def update_packaging_rule(
    rule_id: Annotated[int, Path(ge=1)],
    payload: CrmGarmentPackagingRuleUpdate,
    _actor: Annotated[User, Depends(require_crm_reader)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CrmAssortmentService, Depends(get_assortment_service)],
) -> CrmGarmentPackagingRuleRead:
    return await _write(
        session,
        service.update_packaging_rule(
            session,
            rule_id=rule_id,
            expected_version=payload.expected_version,
            payload=CrmGarmentPackagingRuleWrite.model_validate(payload.model_dump()),
        ),
    )
