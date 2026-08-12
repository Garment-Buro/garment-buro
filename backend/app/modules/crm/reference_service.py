from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crm.reference_models import (
    CrmCatalogProductModelLink,
    CrmFabric,
    CrmGarmentModel,
    CrmGarmentSize,
    CrmReferenceAction,
    CrmReferenceEntityType,
    CrmTechCard,
    CrmTechCardCheckpoint,
    CrmTechCardRevision,
    CrmTechCardRevisionStatus,
)
from app.modules.crm.reference_repository import CrmReferenceRepository
from app.modules.crm.reference_schemas import (
    CrmFabricWrite,
    CrmGarmentModelWrite,
    CrmGarmentSizeWrite,
    CrmTechCardCreate,
    CrmTechCardRevisionWrite,
)
from app.modules.identity.security import ensure_utc


class CrmReferenceNotFoundError(LookupError):
    pass


class CrmReferenceConflictError(ValueError):
    pass


class CrmReferenceVersionConflictError(RuntimeError):
    pass


class CrmReferenceService:
    def __init__(self, repository: CrmReferenceRepository | None = None) -> None:
        self.repository = repository or CrmReferenceRepository()

    async def create_fabric(
        self,
        session: AsyncSession,
        *,
        payload: CrmFabricWrite,
        actor_user_id: int | None,
        now: datetime | None = None,
    ) -> CrmFabric:
        fabric = CrmFabric(version=1)
        self._apply_fabric(fabric, payload)
        await self.repository.add(session, fabric)
        await self._audit(
            session,
            entity_type=CrmReferenceEntityType.FABRIC,
            entity_id=fabric.id,
            entity_version=fabric.version,
            action=CrmReferenceAction.CREATED,
            actor_user_id=actor_user_id,
            snapshot=payload.model_dump(mode="json"),
            details={},
            now=now,
        )
        return fabric

    async def update_fabric(
        self,
        session: AsyncSession,
        *,
        fabric_id: int,
        expected_version: int,
        payload: CrmFabricWrite,
        actor_user_id: int | None,
        now: datetime | None = None,
    ) -> CrmFabric:
        fabric = await self.repository.get_fabric_for_update(session, fabric_id=fabric_id)
        if fabric is None:
            raise CrmReferenceNotFoundError("CRM fabric was not found")
        self._require_version(fabric.version, expected_version)
        self._apply_fabric(fabric, payload)
        fabric.version += 1
        await session.flush()
        await self._audit(
            session,
            entity_type=CrmReferenceEntityType.FABRIC,
            entity_id=fabric.id,
            entity_version=fabric.version,
            action=CrmReferenceAction.UPDATED,
            actor_user_id=actor_user_id,
            snapshot=payload.model_dump(mode="json"),
            details={},
            now=now,
        )
        return fabric

    async def create_garment_model(
        self,
        session: AsyncSession,
        *,
        payload: CrmGarmentModelWrite,
        actor_user_id: int | None,
        now: datetime | None = None,
    ) -> CrmGarmentModel:
        garment_model = CrmGarmentModel(version=1)
        self._apply_garment_model(garment_model, payload)
        garment_model.sizes.extend(self._new_size(size) for size in payload.sizes)
        await self.repository.add(session, garment_model)
        await self._audit(
            session,
            entity_type=CrmReferenceEntityType.GARMENT_MODEL,
            entity_id=garment_model.id,
            entity_version=garment_model.version,
            action=CrmReferenceAction.CREATED,
            actor_user_id=actor_user_id,
            snapshot=payload.model_dump(mode="json"),
            details={"active_sizes_count": len(payload.sizes)},
            now=now,
        )
        return garment_model

    async def update_garment_model(
        self,
        session: AsyncSession,
        *,
        garment_model_id: int,
        expected_version: int,
        payload: CrmGarmentModelWrite,
        actor_user_id: int | None,
        now: datetime | None = None,
    ) -> CrmGarmentModel:
        garment_model = await self.repository.get_garment_model_for_update(
            session,
            garment_model_id=garment_model_id,
        )
        if garment_model is None:
            raise CrmReferenceNotFoundError("CRM garment model was not found")
        self._require_version(garment_model.version, expected_version)
        self._apply_garment_model(garment_model, payload)

        existing_by_code = {size.code: size for size in garment_model.sizes}
        requested_codes = {size.code for size in payload.sizes}
        for size_payload in payload.sizes:
            size = existing_by_code.get(size_payload.code)
            if size is None:
                garment_model.sizes.append(self._new_size(size_payload))
            else:
                self._apply_size(size, size_payload)
                size.is_active = True
                size.version += 1
        for code, size in existing_by_code.items():
            if code not in requested_codes and size.is_active:
                size.is_active = False
                size.version += 1

        garment_model.version += 1
        await session.flush()
        await self._audit(
            session,
            entity_type=CrmReferenceEntityType.GARMENT_MODEL,
            entity_id=garment_model.id,
            entity_version=garment_model.version,
            action=CrmReferenceAction.UPDATED,
            actor_user_id=actor_user_id,
            snapshot=payload.model_dump(mode="json"),
            details={
                "active_sizes_count": len(payload.sizes),
                "retained_sizes_count": len(garment_model.sizes),
            },
            now=now,
        )
        return garment_model

    async def link_catalog_product(
        self,
        session: AsyncSession,
        *,
        garment_model_id: int,
        catalog_product_id: int,
        actor_user_id: int | None,
        now: datetime | None = None,
    ) -> CrmCatalogProductModelLink:
        if catalog_product_id <= 0:
            raise CrmReferenceNotFoundError("Catalog product was not found")
        garment_model = await self.repository.get_garment_model_for_update(
            session,
            garment_model_id=garment_model_id,
        )
        if garment_model is None:
            raise CrmReferenceNotFoundError("CRM garment model was not found")
        if not await self.repository.catalog_product_exists(
            session,
            catalog_product_id=catalog_product_id,
        ):
            raise CrmReferenceNotFoundError("Catalog product was not found")
        existing = await self.repository.get_catalog_link_for_update(
            session,
            catalog_product_id=catalog_product_id,
        )
        if existing is not None:
            if existing.garment_model_id == garment_model.id:
                return existing
            raise CrmReferenceConflictError(
                "Catalog product is already linked to another CRM garment model"
            )

        occurred_at = self._now(now)
        link = CrmCatalogProductModelLink(
            garment_model_id=garment_model.id,
            catalog_product_id=catalog_product_id,
            created_by_user_id=actor_user_id,
            created_at=occurred_at,
        )
        await self.repository.add(session, link)
        await self._audit(
            session,
            entity_type=CrmReferenceEntityType.CATALOG_PRODUCT_LINK,
            entity_id=link.id,
            entity_version=1,
            action=CrmReferenceAction.LINKED,
            actor_user_id=actor_user_id,
            snapshot={
                "garment_model_id": garment_model.id,
                "catalog_product_id": catalog_product_id,
            },
            details={},
            now=occurred_at,
        )
        return link

    async def create_tech_card(
        self,
        session: AsyncSession,
        *,
        garment_model_id: int,
        payload: CrmTechCardCreate,
        actor_user_id: int | None,
        now: datetime | None = None,
    ) -> CrmTechCard:
        garment_model = await self.repository.get_garment_model_for_update(
            session,
            garment_model_id=garment_model_id,
        )
        if garment_model is None:
            raise CrmReferenceNotFoundError("CRM garment model was not found")
        existing = await self.repository.get_tech_card_by_model_for_update(
            session,
            garment_model_id=garment_model_id,
        )
        if existing is not None:
            raise CrmReferenceConflictError("CRM garment model already has a tech card")

        occurred_at = self._now(now)
        card = CrmTechCard(
            garment_model_id=garment_model.id,
            code=payload.code,
            latest_revision_number=1,
            is_active=True,
        )
        card.revisions.append(
            self._new_revision(
                revision_number=1,
                based_on_revision_id=None,
                payload=payload.revision,
                actor_user_id=actor_user_id,
                now=occurred_at,
            )
        )
        await self.repository.add(session, card)
        await self._audit(
            session,
            entity_type=CrmReferenceEntityType.TECH_CARD,
            entity_id=card.id,
            entity_version=1,
            action=CrmReferenceAction.CREATED,
            actor_user_id=actor_user_id,
            snapshot={
                "garment_model_id": garment_model.id,
                **payload.model_dump(mode="json"),
            },
            details={"checkpoints_count": len(payload.revision.checkpoints)},
            now=occurred_at,
        )
        return card

    async def create_tech_card_revision(
        self,
        session: AsyncSession,
        *,
        tech_card_id: int,
        expected_latest_revision: int,
        payload: CrmTechCardRevisionWrite,
        actor_user_id: int | None,
        now: datetime | None = None,
    ) -> CrmTechCardRevision:
        card = await self._require_card(session, tech_card_id)
        self._require_version(card.latest_revision_number, expected_latest_revision)
        if self._find_revision(card, status=CrmTechCardRevisionStatus.DRAFT) is not None:
            raise CrmReferenceConflictError(
                "Tech card already has a draft; publish or discard it first"
            )
        published = self._find_revision(card, status=CrmTechCardRevisionStatus.PUBLISHED)
        revision_number = card.latest_revision_number + 1
        revision = self._new_revision(
            revision_number=revision_number,
            based_on_revision_id=published.id if published is not None else None,
            payload=payload,
            actor_user_id=actor_user_id,
            now=self._now(now),
        )
        card.latest_revision_number = revision_number
        card.revisions.append(revision)
        await session.flush()
        await self._audit(
            session,
            entity_type=CrmReferenceEntityType.TECH_CARD_REVISION,
            entity_id=revision.id,
            entity_version=revision.revision_number,
            action=CrmReferenceAction.REVISION_CREATED,
            actor_user_id=actor_user_id,
            snapshot=payload.model_dump(mode="json"),
            details={
                "tech_card_id": card.id,
                "based_on_revision_id": revision.based_on_revision_id,
                "checkpoints_count": len(payload.checkpoints),
            },
            now=revision.created_at,
        )
        return revision

    async def publish_tech_card_revision(
        self,
        session: AsyncSession,
        *,
        tech_card_id: int,
        revision_number: int,
        actor_user_id: int,
        now: datetime | None = None,
    ) -> CrmTechCardRevision:
        if actor_user_id <= 0:
            raise CrmReferenceConflictError("Published tech-card revision requires an actor")
        card = await self._require_card(session, tech_card_id)
        revision = self._find_revision(card, revision_number=revision_number)
        if revision is None:
            raise CrmReferenceNotFoundError("CRM tech-card revision was not found")
        if revision.status != CrmTechCardRevisionStatus.DRAFT.value:
            raise CrmReferenceConflictError("Only a draft tech-card revision can be published")

        current = self._find_revision(card, status=CrmTechCardRevisionStatus.PUBLISHED)
        if current is not None:
            current.status = CrmTechCardRevisionStatus.ARCHIVED.value
            await session.flush()
        occurred_at = self._now(now)
        revision.status = CrmTechCardRevisionStatus.PUBLISHED.value
        revision.published_by_user_id = actor_user_id
        revision.published_at = occurred_at
        await session.flush()
        await self._audit(
            session,
            entity_type=CrmReferenceEntityType.TECH_CARD_REVISION,
            entity_id=revision.id,
            entity_version=revision.revision_number,
            action=CrmReferenceAction.PUBLISHED,
            actor_user_id=actor_user_id,
            snapshot=self._revision_snapshot(revision),
            details={
                "tech_card_id": card.id,
                "archived_revision_id": current.id if current is not None else None,
            },
            now=occurred_at,
        )
        return revision

    async def discard_tech_card_draft(
        self,
        session: AsyncSession,
        *,
        tech_card_id: int,
        revision_number: int,
        actor_user_id: int | None,
        now: datetime | None = None,
    ) -> CrmTechCardRevision:
        card = await self._require_card(session, tech_card_id)
        revision = self._find_revision(card, revision_number=revision_number)
        if revision is None:
            raise CrmReferenceNotFoundError("CRM tech-card revision was not found")
        if revision.status != CrmTechCardRevisionStatus.DRAFT.value:
            raise CrmReferenceConflictError("Only a draft tech-card revision can be discarded")
        revision.status = CrmTechCardRevisionStatus.DISCARDED.value
        await session.flush()
        await self._audit(
            session,
            entity_type=CrmReferenceEntityType.TECH_CARD_REVISION,
            entity_id=revision.id,
            entity_version=revision.revision_number,
            action=CrmReferenceAction.DISCARDED,
            actor_user_id=actor_user_id,
            snapshot=self._revision_snapshot(revision),
            details={"tech_card_id": card.id},
            now=now,
        )
        return revision

    async def _require_card(
        self,
        session: AsyncSession,
        tech_card_id: int,
    ) -> CrmTechCard:
        card = await self.repository.get_tech_card_for_update(
            session,
            tech_card_id=tech_card_id,
        )
        if card is None:
            raise CrmReferenceNotFoundError("CRM tech card was not found")
        return card

    @staticmethod
    def _find_revision(
        card: CrmTechCard,
        *,
        revision_number: int | None = None,
        status: CrmTechCardRevisionStatus | None = None,
    ) -> CrmTechCardRevision | None:
        return next(
            (
                revision
                for revision in card.revisions
                if (revision_number is None or revision.revision_number == revision_number)
                and (status is None or revision.status == status.value)
            ),
            None,
        )

    @staticmethod
    def _apply_fabric(fabric: CrmFabric, payload: CrmFabricWrite) -> None:
        fabric.code = payload.code
        fabric.name = payload.name
        fabric.material_type = payload.material_type
        fabric.color_name = payload.color_name
        fabric.color_hex = payload.color_hex
        fabric.density_gsm = payload.density_gsm
        fabric.width_cm = payload.width_cm
        fabric.cost_per_meter = payload.cost_per_meter
        fabric.currency = payload.currency
        fabric.is_active = payload.is_active

    @staticmethod
    def _apply_garment_model(
        garment_model: CrmGarmentModel,
        payload: CrmGarmentModelWrite,
    ) -> None:
        garment_model.code = payload.code
        garment_model.name = payload.name
        garment_model.description = payload.description
        garment_model.base_height_cm = payload.base_height_cm
        garment_model.base_length_cm = payload.base_length_cm
        garment_model.base_width_cm = payload.base_width_cm
        garment_model.base_weight_g = payload.base_weight_g
        garment_model.is_active = payload.is_active

    @classmethod
    def _new_size(cls, payload: CrmGarmentSizeWrite) -> CrmGarmentSize:
        size = CrmGarmentSize(version=1, is_active=True)
        cls._apply_size(size, payload)
        return size

    @staticmethod
    def _apply_size(size: CrmGarmentSize, payload: CrmGarmentSizeWrite) -> None:
        size.code = payload.code
        size.sort_order = payload.sort_order
        size.base_price = payload.base_price
        size.min_height_cm = payload.min_height_cm
        size.max_height_cm = payload.max_height_cm
        size.min_length_cm = payload.min_length_cm
        size.max_length_cm = payload.max_length_cm
        size.min_width_cm = payload.min_width_cm
        size.max_width_cm = payload.max_width_cm
        size.extra_width_price_per_cm = payload.extra_width_price_per_cm
        size.currency = payload.currency

    @staticmethod
    def _new_revision(
        *,
        revision_number: int,
        based_on_revision_id: int | None,
        payload: CrmTechCardRevisionWrite,
        actor_user_id: int | None,
        now: datetime,
    ) -> CrmTechCardRevision:
        return CrmTechCardRevision(
            revision_number=revision_number,
            based_on_revision_id=based_on_revision_id,
            status=CrmTechCardRevisionStatus.DRAFT.value,
            name_snapshot=payload.name,
            description_snapshot=payload.description,
            created_by_user_id=actor_user_id,
            created_at=now,
            checkpoints=[
                CrmTechCardCheckpoint(
                    position=checkpoint.position,
                    stage_code=checkpoint.stage_code,
                    name=checkpoint.name,
                    description=checkpoint.description,
                    standard_minutes=checkpoint.standard_minutes,
                    labor_cost=checkpoint.labor_cost,
                    currency=checkpoint.currency,
                )
                for checkpoint in sorted(payload.checkpoints, key=lambda item: item.position)
            ],
        )

    @staticmethod
    def _revision_snapshot(revision: CrmTechCardRevision) -> dict[str, object]:
        return {
            "tech_card_id": revision.tech_card_id,
            "revision_number": revision.revision_number,
            "based_on_revision_id": revision.based_on_revision_id,
            "status": revision.status,
            "name": revision.name_snapshot,
            "description": revision.description_snapshot,
            "checkpoints": [
                {
                    "position": checkpoint.position,
                    "stage_code": checkpoint.stage_code,
                    "name": checkpoint.name,
                    "description": checkpoint.description,
                    "standard_minutes": CrmReferenceService._decimal(checkpoint.standard_minutes),
                    "labor_cost": CrmReferenceService._decimal(checkpoint.labor_cost),
                    "currency": checkpoint.currency,
                }
                for checkpoint in sorted(revision.checkpoints, key=lambda item: item.position)
            ],
        }

    async def _audit(
        self,
        session: AsyncSession,
        *,
        entity_type: CrmReferenceEntityType,
        entity_id: int,
        entity_version: int,
        action: CrmReferenceAction,
        actor_user_id: int | None,
        snapshot: dict[str, object],
        details: dict[str, object],
        now: datetime | None,
    ) -> None:
        await self.repository.add_event(
            session,
            entity_type=entity_type.value,
            entity_id=entity_id,
            entity_version=entity_version,
            action=action.value,
            actor_user_id=actor_user_id,
            snapshot_sha256=self._checksum(snapshot),
            details=details,
            occurred_at=self._now(now),
        )

    @staticmethod
    def _require_version(actual: int, expected: int) -> None:
        if expected <= 0 or actual != expected:
            raise CrmReferenceVersionConflictError("CRM reference version has changed")

    @staticmethod
    def _checksum(snapshot: dict[str, object]) -> str:
        canonical = json.dumps(
            snapshot,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _now(value: datetime | None) -> datetime:
        return ensure_utc(value or datetime.now(timezone.utc))

    @staticmethod
    def _decimal(value: Decimal | None) -> str | None:
        return format(value, "f") if value is not None else None
