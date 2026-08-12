from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_database_session
from app.modules.catalog.content import CatalogContentService, LandingSettings, VariantOptions
from app.modules.catalog.dependencies import require_catalog_writer
from app.modules.identity.models import User

router = APIRouter(tags=["catalog-content"])


def get_catalog_content_service() -> CatalogContentService:
    return CatalogContentService()


@router.get("/api/settings", response_model=LandingSettings)
async def get_settings(
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CatalogContentService, Depends(get_catalog_content_service)],
) -> LandingSettings:
    return await service.get_settings(session)


@router.put("/api/settings", response_model=LandingSettings)
async def update_settings(
    payload: LandingSettings,
    user: Annotated[User, Depends(require_catalog_writer)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CatalogContentService, Depends(get_catalog_content_service)],
) -> LandingSettings:
    updated = await service.update_settings(
        session,
        payload=payload,
        actor_user_id=user.id,
    )
    await session.commit()
    return updated


@router.get("/api/options", response_model=VariantOptions)
async def get_options(
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CatalogContentService, Depends(get_catalog_content_service)],
) -> VariantOptions:
    return await service.get_options(session)


@router.put("/api/options", response_model=VariantOptions)
async def update_options(
    payload: VariantOptions,
    user: Annotated[User, Depends(require_catalog_writer)],
    session: Annotated[AsyncSession, Depends(get_database_session)],
    service: Annotated[CatalogContentService, Depends(get_catalog_content_service)],
) -> VariantOptions:
    updated = await service.update_options(
        session,
        payload=payload,
        actor_user_id=user.id,
    )
    await session.commit()
    return updated
