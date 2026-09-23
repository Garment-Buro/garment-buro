from __future__ import annotations

from collections.abc import Awaitable
from typing import Annotated, TypeVar

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.modules.catalog.mapper import CatalogResponseMapper
from app.modules.catalog.schemas import (
    ProductCategoryResponse,
    ProductCategoryUpdate,
    ProductCategoryWrite,
    ProductDetailResponse,
    ProductWriteRequest,
)
from app.modules.catalog.service import (
    CatalogInventoryReservedError,
    CatalogProductNotFoundError,
    CatalogReferenceNotFoundError,
    CatalogService,
    CatalogVersionConflictError,
    CatalogWriteService,
    UnknownCatalogMediaError,
)
from app.modules.crm.assortment_schemas import (
    CrmAccessoryCategoryRead,
    CrmAccessoryCategoryUpdate,
    CrmAccessoryCategoryWrite,
    CrmAccessoryRead,
    CrmAccessoryUpdate,
    CrmAccessoryWrite,
    CrmCatalogProductReferenceRead,
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
from app.modules.crm.read_schemas import CrmFabricPage, CrmGarmentModelPage
from app.modules.crm.read_service import CrmReadService
from app.modules.crm.reference_schemas import (
    CrmFabricReferenceRead,
    CrmFabricUpdate,
    CrmFabricWrite,
    CrmGarmentModelCategoryRead,
    CrmGarmentModelReferenceRead,
    CrmGarmentModelUpdate,
    CrmGarmentModelWrite,
    CrmTechCardCreate,
    CrmTechCardRead,
    CrmTechCardRevisionCreate,
    CrmTechCardRevisionRead,
)
from app.modules.crm.reference_service import (
    CrmReferenceConflictError,
    CrmReferenceNotFoundError,
    CrmReferenceService,
    CrmReferenceVersionConflictError,
)
from app.modules.media.models import MediaObject, MediaStatus
from app.modules.media.service import MediaService, UnsupportedMediaError
from app.modules.partners.repository import PartnerRepository
from app.modules.production.admin_router import Session
from app.modules.production.admin_router import SystemAdmin as Admin
from app.modules.production.assortment_media_service import (
    AssortmentMediaService,
    UnsupportedCrmFileError,
)

router = APIRouter(prefix="/admin/assortment", tags=["production-admin-assortment"])
T = TypeVar("T")


class ProductCommunityRead(BaseModel):
    id: int
    title: str
    slug: str
    image_url: str | None
    status: str
    partner_name: str
    product_ids: list[int]


def _writes_enabled(request: Request) -> None:
    if not request.app.state.settings.crm_writes_enabled:
        raise HTTPException(503, "Изменение справочников временно выключено")


def _catalog_writes_enabled(request: Request) -> None:
    _writes_enabled(request)
    if not request.app.state.settings.catalog_writes_enabled:
        raise HTTPException(503, "Изменение каталога временно выключено")


async def _write(session: Session, operation: Awaitable[T]) -> T:
    try:
        result = await operation
        await session.commit()
        return result
    except (CrmAssortmentNotFoundError, CrmReferenceNotFoundError) as error:
        await session.rollback()
        raise HTTPException(404, str(error)) from error
    except (
        CrmAssortmentConflictError,
        CrmAssortmentVersionConflictError,
        CrmReferenceConflictError,
        CrmReferenceVersionConflictError,
    ) as error:
        await session.rollback()
        raise HTTPException(409, str(error)) from error
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(409, "Запись уже существует или используется") from error


@router.get("/models", response_model=CrmGarmentModelPage)
async def models(_admin: Admin, session: Session, active: bool | None = None):
    return await CrmReadService().list_garment_models(
        session,
        is_active=active,
        cursor=None,
        limit=100,
    )


@router.get("/model-categories", response_model=list[CrmGarmentModelCategoryRead])
async def model_categories(_admin: Admin, session: Session):
    return await CrmReferenceService().repository.list_garment_model_categories(session)


@router.post("/models", response_model=CrmGarmentModelReferenceRead, status_code=201)
async def create_model(
    payload: CrmGarmentModelWrite,
    request: Request,
    admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(
        session,
        CrmReferenceService().create_garment_model(
            session,
            payload=payload,
            actor_user_id=admin.id,
        ),
    )


@router.put("/models/{model_id}", response_model=CrmGarmentModelReferenceRead)
async def update_model(
    model_id: int,
    payload: CrmGarmentModelUpdate,
    request: Request,
    admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(
        session,
        CrmReferenceService().update_garment_model(
            session,
            garment_model_id=model_id,
            expected_version=payload.expected_version,
            payload=CrmGarmentModelWrite.model_validate(
                payload.model_dump(exclude={"expected_version"})
            ),
            actor_user_id=admin.id,
        ),
    )


@router.get("/fabrics", response_model=CrmFabricPage)
async def fabrics(_admin: Admin, session: Session, active: bool | None = None):
    return await CrmReadService().list_fabrics(
        session,
        is_active=active,
        cursor=None,
        limit=100,
    )


@router.post("/fabrics", response_model=CrmFabricReferenceRead, status_code=201)
async def create_fabric(
    payload: CrmFabricWrite,
    request: Request,
    admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(
        session,
        CrmReferenceService().create_fabric(
            session,
            payload=payload,
            actor_user_id=admin.id,
        ),
    )


@router.put("/fabrics/{fabric_id}", response_model=CrmFabricReferenceRead)
async def update_fabric(
    fabric_id: int,
    payload: CrmFabricUpdate,
    request: Request,
    admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(
        session,
        CrmReferenceService().update_fabric(
            session,
            fabric_id=fabric_id,
            expected_version=payload.expected_version,
            payload=CrmFabricWrite.model_validate(payload.model_dump(exclude={"expected_version"})),
            actor_user_id=admin.id,
        ),
    )


@router.get("/patterns", response_model=list[CrmGarmentPatternRead])
async def patterns(
    _admin: Admin,
    session: Session,
    model_id: Annotated[int | None, Query(ge=1)] = None,
    query: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
):
    return await CrmAssortmentService().list_patterns(
        session, model_id=model_id, active=None, query=query
    )


@router.post("/patterns", response_model=CrmGarmentPatternRead, status_code=201)
async def create_pattern(
    payload: CrmGarmentPatternWrite,
    request: Request,
    _admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(session, CrmAssortmentService().create_pattern(session, payload))


@router.put("/patterns/{pattern_id}", response_model=CrmGarmentPatternRead)
async def update_pattern(
    pattern_id: int,
    payload: CrmGarmentPatternUpdate,
    request: Request,
    _admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(
        session,
        CrmAssortmentService().update_pattern(
            session,
            pattern_id=pattern_id,
            expected_version=payload.expected_version,
            payload=CrmGarmentPatternWrite.model_validate(
                payload.model_dump(exclude={"expected_version"})
            ),
        ),
    )


@router.get("/fabric-requirements", response_model=list[CrmGarmentFabricRequirementRead])
async def fabric_requirements(
    _admin: Admin,
    session: Session,
    model_id: Annotated[int | None, Query(ge=1)] = None,
):
    return await CrmAssortmentService().list_fabric_requirements(
        session,
        model_id=model_id,
    )


@router.post(
    "/fabric-requirements",
    response_model=CrmGarmentFabricRequirementRead,
    status_code=201,
)
async def create_fabric_requirement(
    payload: CrmGarmentFabricRequirementWrite,
    request: Request,
    _admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(
        session,
        CrmAssortmentService().create_fabric_requirement(session, payload),
    )


@router.put(
    "/fabric-requirements/{requirement_id}",
    response_model=CrmGarmentFabricRequirementRead,
)
async def update_fabric_requirement(
    requirement_id: int,
    payload: CrmGarmentFabricRequirementUpdate,
    request: Request,
    _admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(
        session,
        CrmAssortmentService().update_fabric_requirement(
            session,
            requirement_id=requirement_id,
            expected_version=payload.expected_version,
            payload=CrmGarmentFabricRequirementWrite.model_validate(
                payload.model_dump(exclude={"expected_version"})
            ),
        ),
    )


@router.get("/tech-cards", response_model=list[CrmTechCardRead])
async def tech_cards(
    _admin: Admin,
    session: Session,
    model_id: Annotated[int | None, Query(ge=1)] = None,
):
    return await CrmReferenceService().list_tech_cards(
        session,
        garment_model_id=model_id,
    )


@router.post("/models/{model_id}/tech-cards", response_model=CrmTechCardRead, status_code=201)
async def create_tech_card(
    model_id: int,
    payload: CrmTechCardCreate,
    request: Request,
    admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(
        session,
        CrmReferenceService().create_tech_card(
            session,
            garment_model_id=model_id,
            payload=payload,
            actor_user_id=admin.id,
        ),
    )


@router.post("/tech-cards/{card_id}/revisions", response_model=CrmTechCardRevisionRead)
async def create_tech_card_revision(
    card_id: int,
    payload: CrmTechCardRevisionCreate,
    request: Request,
    admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(
        session,
        CrmReferenceService().create_tech_card_revision(
            session,
            tech_card_id=card_id,
            expected_latest_revision=payload.expected_latest_revision,
            payload=payload.revision,
            actor_user_id=admin.id,
        ),
    )


@router.post(
    "/tech-cards/{card_id}/revisions/{revision_number}/publish",
    response_model=CrmTechCardRevisionRead,
)
async def publish_tech_card_revision(
    card_id: int,
    revision_number: int,
    request: Request,
    admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(
        session,
        CrmReferenceService().publish_tech_card_revision(
            session,
            tech_card_id=card_id,
            revision_number=revision_number,
            actor_user_id=admin.id,
        ),
    )


@router.get("/accessory-categories", response_model=list[CrmAccessoryCategoryRead])
async def accessory_categories(_admin: Admin, session: Session):
    return await CrmAssortmentService().list_categories(session, active=None)


@router.post("/accessory-categories", response_model=CrmAccessoryCategoryRead, status_code=201)
async def create_accessory_category(
    payload: CrmAccessoryCategoryWrite,
    request: Request,
    _admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(session, CrmAssortmentService().create_category(session, payload))


@router.put("/accessory-categories/{category_id}", response_model=CrmAccessoryCategoryRead)
async def update_accessory_category(
    category_id: int,
    payload: CrmAccessoryCategoryUpdate,
    request: Request,
    _admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(
        session,
        CrmAssortmentService().update_category(
            session,
            category_id=category_id,
            expected_version=payload.expected_version,
            payload=CrmAccessoryCategoryWrite.model_validate(
                payload.model_dump(exclude={"expected_version"})
            ),
        ),
    )


@router.get("/accessories", response_model=list[CrmAccessoryRead])
async def accessories(_admin: Admin, session: Session):
    return await CrmAssortmentService().list_accessories(
        session,
        category_id=None,
        model_id=None,
        active=None,
    )


@router.post("/accessories", response_model=CrmAccessoryRead, status_code=201)
async def create_accessory(
    payload: CrmAccessoryWrite,
    request: Request,
    _admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(session, CrmAssortmentService().create_accessory(session, payload))


@router.put("/accessories/{accessory_id}", response_model=CrmAccessoryRead)
async def update_accessory(
    accessory_id: int,
    payload: CrmAccessoryUpdate,
    request: Request,
    _admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(
        session,
        CrmAssortmentService().update_accessory(
            session,
            accessory_id=accessory_id,
            expected_version=payload.expected_version,
            payload=CrmAccessoryWrite.model_validate(
                payload.model_dump(exclude={"expected_version"})
            ),
        ),
    )


@router.get(
    "/accessory-requirements",
    response_model=list[CrmGarmentAccessoryRequirementRead],
)
async def accessory_requirements(_admin: Admin, session: Session):
    return await CrmAssortmentService().list_accessory_requirements(session, model_id=None)


@router.post(
    "/accessory-requirements",
    response_model=CrmGarmentAccessoryRequirementRead,
    status_code=201,
)
async def create_accessory_requirement(
    payload: CrmGarmentAccessoryRequirementWrite,
    request: Request,
    _admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(
        session,
        CrmAssortmentService().create_accessory_requirement(session, payload),
    )


@router.put(
    "/accessory-requirements/{requirement_id}",
    response_model=CrmGarmentAccessoryRequirementRead,
)
async def update_accessory_requirement(
    requirement_id: int,
    payload: CrmGarmentAccessoryRequirementUpdate,
    request: Request,
    _admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(
        session,
        CrmAssortmentService().update_accessory_requirement(
            session,
            requirement_id=requirement_id,
            expected_version=payload.expected_version,
            payload=CrmGarmentAccessoryRequirementWrite.model_validate(
                payload.model_dump(exclude={"expected_version"})
            ),
        ),
    )


@router.get("/boxes", response_model=list[CrmPackagingBoxRead])
async def boxes(_admin: Admin, session: Session):
    return await CrmAssortmentService().list_boxes(session, active=None)


@router.post("/boxes", response_model=CrmPackagingBoxRead, status_code=201)
async def create_box(
    payload: CrmPackagingBoxWrite,
    request: Request,
    _admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(session, CrmAssortmentService().create_box(session, payload))


@router.put("/boxes/{box_id}", response_model=CrmPackagingBoxRead)
async def update_box(
    box_id: int,
    payload: CrmPackagingBoxUpdate,
    request: Request,
    _admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(
        session,
        CrmAssortmentService().update_box(
            session,
            box_id=box_id,
            expected_version=payload.expected_version,
            payload=CrmPackagingBoxWrite.model_validate(
                payload.model_dump(exclude={"expected_version"})
            ),
        ),
    )


@router.get("/packaging-rules", response_model=list[CrmGarmentPackagingRuleRead])
async def packaging_rules(_admin: Admin, session: Session):
    return await CrmAssortmentService().list_packaging_rules(session, model_id=None)


@router.post(
    "/packaging-rules",
    response_model=CrmGarmentPackagingRuleRead,
    status_code=201,
)
async def create_packaging_rule(
    payload: CrmGarmentPackagingRuleWrite,
    request: Request,
    _admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(
        session,
        CrmAssortmentService().create_packaging_rule(session, payload),
    )


@router.put(
    "/packaging-rules/{rule_id}",
    response_model=CrmGarmentPackagingRuleRead,
)
async def update_packaging_rule(
    rule_id: int,
    payload: CrmGarmentPackagingRuleUpdate,
    request: Request,
    _admin: Admin,
    session: Session,
):
    _writes_enabled(request)
    return await _write(
        session,
        CrmAssortmentService().update_packaging_rule(
            session,
            rule_id=rule_id,
            expected_version=payload.expected_version,
            payload=CrmGarmentPackagingRuleWrite.model_validate(
                payload.model_dump(exclude={"expected_version"})
            ),
        ),
    )


@router.get("/products", response_model=list[CrmCatalogProductReferenceRead])
async def products(request: Request, _admin: Admin, session: Session):
    return await CrmAssortmentService().list_products(
        session,
        model_id=None,
        category_id=None,
        active=None,
        mapper=CatalogResponseMapper(request.app.state.settings),
    )


@router.get("/products/{product_id}", response_model=ProductDetailResponse)
async def product(product_id: int, request: Request, _admin: Admin, session: Session):
    result = await CatalogService(CatalogResponseMapper(request.app.state.settings)).get_product(
        session,
        product_id,
    )
    if result is None:
        raise HTTPException(404, "Товар не найден")
    return result


async def _catalog_write(session: Session, operation: Awaitable[T]) -> T:
    try:
        result = await operation
        await session.commit()
        return result
    except CatalogProductNotFoundError as error:
        await session.rollback()
        raise HTTPException(404, "Товар не найден") from error
    except (
        CatalogInventoryReservedError,
        CatalogReferenceNotFoundError,
        CatalogVersionConflictError,
        UnknownCatalogMediaError,
    ) as error:
        await session.rollback()
        raise HTTPException(409, str(error)) from error
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(409, "Товар или категория уже существует") from error


@router.post("/products", response_model=ProductDetailResponse, status_code=201)
async def create_product(
    payload: ProductWriteRequest,
    request: Request,
    admin: Admin,
    session: Session,
):
    _catalog_writes_enabled(request)
    return await _catalog_write(
        session,
        CatalogWriteService(request.app.state.settings).create_product(
            session,
            payload=payload,
            actor_user_id=admin.id,
        ),
    )


@router.put("/products/{product_id}", response_model=ProductDetailResponse)
async def update_product(
    product_id: int,
    payload: ProductWriteRequest,
    request: Request,
    admin: Admin,
    session: Session,
):
    _catalog_writes_enabled(request)
    return await _catalog_write(
        session,
        CatalogWriteService(request.app.state.settings).update_product(
            session,
            product_id=product_id,
            payload=payload,
            actor_user_id=admin.id,
        ),
    )


@router.get("/product-categories", response_model=list[ProductCategoryResponse])
async def product_categories(request: Request, _admin: Admin, session: Session):
    return await CatalogService(CatalogResponseMapper(request.app.state.settings)).list_categories(
        session
    )


@router.get("/product-communities", response_model=list[ProductCommunityRead])
async def product_communities(_admin: Admin, session: Session):
    landings = await PartnerRepository().list_all_landings(session)
    return [
        ProductCommunityRead(
            id=landing.id,
            title=landing.title,
            slug=landing.slug,
            image_url=landing.image_url,
            status=landing.status,
            partner_name=landing.partner.display_name,
            product_ids=landing.product_ids,
        )
        for landing in landings
    ]


@router.post("/product-categories", response_model=ProductCategoryResponse, status_code=201)
async def create_product_category(
    payload: ProductCategoryWrite,
    request: Request,
    _admin: Admin,
    session: Session,
):
    _catalog_writes_enabled(request)
    return await _catalog_write(
        session,
        CatalogWriteService(request.app.state.settings).create_category(session, payload=payload),
    )


@router.put("/product-categories/{category_id}", response_model=ProductCategoryResponse)
async def update_product_category(
    category_id: int,
    payload: ProductCategoryUpdate,
    request: Request,
    _admin: Admin,
    session: Session,
):
    _catalog_writes_enabled(request)
    return await _catalog_write(
        session,
        CatalogWriteService(request.app.state.settings).update_category(
            session,
            category_id=category_id,
            expected_version=payload.expected_version,
            payload=ProductCategoryWrite.model_validate(
                payload.model_dump(exclude={"expected_version"})
            ),
        ),
    )


@router.post("/media/public", status_code=201)
async def upload_public_media(
    request: Request,
    admin: Admin,
    session: Session,
    file: Annotated[UploadFile, File()],
):
    _writes_enabled(request)
    limit = request.app.state.settings.media_max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, "Файл слишком большой")
    try:
        uploaded = await MediaService(request.app.state.storage).upload_catalog_media(
            session,
            data=data,
            original_filename=file.filename or "upload",
            actor_user_id=admin.id,
        )
    except UnsupportedMediaError as error:
        raise HTTPException(415, str(error)) from error
    return {"id": uploaded.media_id, "url": uploaded.public_url}


@router.get("/media/public/{media_id}", include_in_schema=False)
async def view_public_media(
    media_id: int,
    request: Request,
    _admin: Admin,
    session: Session,
):
    media = await session.scalar(select(MediaObject).where(MediaObject.id == media_id))
    if media is None or not media.is_public or media.status != MediaStatus.READY.value:
        raise HTTPException(404, "Изображение не найдено")
    return RedirectResponse(
        request.app.state.storage.public_url(media.object_key),
        status_code=307,
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.post("/media/pattern", status_code=201)
async def upload_pattern_media(
    request: Request,
    admin: Admin,
    session: Session,
    file: Annotated[UploadFile, File()],
):
    _writes_enabled(request)
    limit = request.app.state.settings.crm_file_max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, "Файл слишком большой")
    try:
        receipt = await AssortmentMediaService(request.app.state.storage).upload_pattern(
            session,
            data=data,
            original_filename=file.filename or "pattern",
            actor_user_id=admin.id,
        )
    except UnsupportedCrmFileError as error:
        raise HTTPException(415, str(error)) from error
    return {
        "id": receipt.media_id,
        "filename": receipt.original_filename,
        "content_type": receipt.content_type,
    }
