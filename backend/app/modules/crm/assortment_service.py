from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.mapper import CatalogResponseMapper
from app.modules.catalog.models import Product
from app.modules.crm.assortment_models import (
    CrmAccessory,
    CrmAccessoryCategory,
    CrmGarmentAccessoryRequirement,
    CrmGarmentFabricRequirement,
    CrmGarmentPackagingRule,
    CrmGarmentPattern,
    CrmPackagingBox,
)
from app.modules.crm.assortment_repository import CrmAssortmentRepository
from app.modules.crm.assortment_schemas import (
    CrmAccessoryCategoryRead,
    CrmAccessoryCategoryWrite,
    CrmAccessoryRead,
    CrmAccessoryWrite,
    CrmCatalogProductReferenceRead,
    CrmCatalogProductVariantReferenceRead,
    CrmGarmentAccessoryRequirementRead,
    CrmGarmentAccessoryRequirementWrite,
    CrmGarmentFabricRequirementRead,
    CrmGarmentFabricRequirementWrite,
    CrmGarmentPackagingRuleRead,
    CrmGarmentPackagingRuleWrite,
    CrmGarmentPatternRead,
    CrmGarmentPatternWrite,
    CrmPackagingBoxRead,
    CrmPackagingBoxWrite,
)
from app.modules.crm.reference_models import CrmGarmentSize

GRID_STEP_CM = Decimal("2.00")


class CrmAssortmentNotFoundError(LookupError):
    pass


class CrmAssortmentConflictError(ValueError):
    pass


class CrmAssortmentVersionConflictError(RuntimeError):
    pass


class CrmAssortmentService:
    def __init__(self, repository: CrmAssortmentRepository | None = None) -> None:
        self.repository = repository or CrmAssortmentRepository()

    async def list_products(
        self,
        session: AsyncSession,
        *,
        model_id: int | None,
        category_id: int | None,
        active: bool | None,
        mapper: CatalogResponseMapper | None = None,
    ) -> list[CrmCatalogProductReferenceRead]:
        rows = await self.repository.list_products(
            session,
            model_id=model_id,
            category_id=category_id,
            active=active,
        )

        def image_url(row: Product) -> str | None:
            if mapper is None:
                return None
            product = mapper.product(row)
            for candidate in (
                product.mobile_card_image,
                product.image_left,
                product.desktop_card_images,
                product.gallery_images,
            ):
                if candidate:
                    return candidate.split(",", maxsplit=1)[0].strip()
            return None

        return [
            CrmCatalogProductReferenceRead(
                id=row.id,
                title=row.title,
                slug=row.slug,
                category_id=row.category_id,
                garment_model_id=row.garment_model_id,
                price=row.price,
                old_price=row.old_price,
                image_url=image_url(row),
                is_active=row.is_active,
                stock_quantity=row.stock_quantity - row.reserved_quantity,
                variants=[
                    CrmCatalogProductVariantReferenceRead(
                        id=variant.id,
                        sku=variant.sku,
                        size=variant.size,
                        garment_size_id=variant.garment_size_id,
                        fabric_id=variant.fabric_id,
                        color=variant.color,
                        stock_quantity=variant.stock_quantity - variant.reserved_quantity,
                    )
                    for variant in row.variants
                ],
            )
            for row in rows
        ]

    async def list_patterns(
        self,
        session: AsyncSession,
        *,
        model_id: int | None,
        active: bool | None,
        query: str | None = None,
    ) -> list[CrmGarmentPatternRead]:
        rows = await self.repository.list_patterns(
            session, model_id=model_id, active=active, query=query
        )
        return [CrmGarmentPatternRead.model_validate(row) for row in rows]

    async def create_pattern(
        self, session: AsyncSession, payload: CrmGarmentPatternWrite
    ) -> CrmGarmentPatternRead:
        size = await self._validate_pattern(session, payload)
        row = CrmGarmentPattern(version=1)
        self._apply_pattern(row, payload, size)
        await self.repository.add(session, row)
        return CrmGarmentPatternRead.model_validate(row)

    async def update_pattern(
        self,
        session: AsyncSession,
        *,
        pattern_id: int,
        expected_version: int,
        payload: CrmGarmentPatternWrite,
    ) -> CrmGarmentPatternRead:
        row = await self.repository.get_pattern_for_update(session, pattern_id)
        if row is None:
            raise CrmAssortmentNotFoundError("Pattern was not found")
        self._version(row.version, expected_version)
        size = await self._validate_pattern(session, payload)
        self._apply_pattern(row, payload, size)
        row.version += 1
        await session.flush()
        return CrmGarmentPatternRead.model_validate(row)

    async def list_fabric_requirements(
        self, session: AsyncSession, *, model_id: int | None
    ) -> list[CrmGarmentFabricRequirementRead]:
        rows = await self.repository.list_fabric_requirements(session, model_id=model_id)
        return [CrmGarmentFabricRequirementRead.model_validate(row) for row in rows]

    async def create_fabric_requirement(
        self, session: AsyncSession, payload: CrmGarmentFabricRequirementWrite
    ) -> CrmGarmentFabricRequirementRead:
        await self._validate_fabric_requirement(session, payload)
        row = CrmGarmentFabricRequirement(version=1)
        self._apply_fabric_requirement(row, payload)
        await self.repository.add(session, row)
        return CrmGarmentFabricRequirementRead.model_validate(row)

    async def update_fabric_requirement(
        self,
        session: AsyncSession,
        *,
        requirement_id: int,
        expected_version: int,
        payload: CrmGarmentFabricRequirementWrite,
    ) -> CrmGarmentFabricRequirementRead:
        row = await self.repository.get_fabric_requirement_for_update(session, requirement_id)
        if row is None:
            raise CrmAssortmentNotFoundError("Fabric requirement was not found")
        self._version(row.version, expected_version)
        await self._validate_fabric_requirement(session, payload, exclude_id=row.id)
        self._apply_fabric_requirement(row, payload)
        row.version += 1
        await session.flush()
        return CrmGarmentFabricRequirementRead.model_validate(row)

    async def list_categories(
        self, session: AsyncSession, *, active: bool | None
    ) -> list[CrmAccessoryCategoryRead]:
        rows = await self.repository.list_categories(session, active=active)
        return [CrmAccessoryCategoryRead.model_validate(row) for row in rows]

    async def create_category(
        self, session: AsyncSession, payload: CrmAccessoryCategoryWrite
    ) -> CrmAccessoryCategoryRead:
        row = CrmAccessoryCategory(version=1)
        self._apply_category(row, payload)
        await self.repository.add(session, row)
        return CrmAccessoryCategoryRead.model_validate(row)

    async def update_category(
        self,
        session: AsyncSession,
        *,
        category_id: int,
        expected_version: int,
        payload: CrmAccessoryCategoryWrite,
    ) -> CrmAccessoryCategoryRead:
        row = await self.repository.get_category(session, category_id, lock=True)
        if row is None:
            raise CrmAssortmentNotFoundError("Accessory category was not found")
        self._version(row.version, expected_version)
        self._apply_category(row, payload)
        row.version += 1
        await session.flush()
        return CrmAccessoryCategoryRead.model_validate(row)

    async def list_accessories(
        self,
        session: AsyncSession,
        *,
        category_id: int | None,
        model_id: int | None,
        active: bool | None,
    ) -> list[CrmAccessoryRead]:
        rows = await self.repository.list_accessories(
            session,
            category_id=category_id,
            model_id=model_id,
            active=active,
        )
        return [self._accessory_read(row) for row in rows]

    async def create_accessory(
        self, session: AsyncSession, payload: CrmAccessoryWrite
    ) -> CrmAccessoryRead:
        await self._validate_accessory(session, payload)
        row = CrmAccessory(version=1)
        self._apply_accessory(row, payload)
        await self.repository.add(session, row)
        return self._accessory_read(row, model_ids=[])

    async def update_accessory(
        self,
        session: AsyncSession,
        *,
        accessory_id: int,
        expected_version: int,
        payload: CrmAccessoryWrite,
    ) -> CrmAccessoryRead:
        row = await self.repository.get_accessory(session, accessory_id, lock=True)
        if row is None:
            raise CrmAssortmentNotFoundError("Accessory was not found")
        self._version(row.version, expected_version)
        await self._validate_accessory(session, payload)
        self._apply_accessory(row, payload)
        row.version += 1
        await session.flush()
        return self._accessory_read(row)

    async def list_accessory_requirements(
        self, session: AsyncSession, *, model_id: int | None
    ) -> list[CrmGarmentAccessoryRequirementRead]:
        rows = await self.repository.list_accessory_requirements(session, model_id=model_id)
        return [CrmGarmentAccessoryRequirementRead.model_validate(row) for row in rows]

    async def create_accessory_requirement(
        self, session: AsyncSession, payload: CrmGarmentAccessoryRequirementWrite
    ) -> CrmGarmentAccessoryRequirementRead:
        await self._validate_accessory_requirement(session, payload)
        row = CrmGarmentAccessoryRequirement(version=1)
        self._apply_accessory_requirement(row, payload)
        await self.repository.add(session, row)
        return CrmGarmentAccessoryRequirementRead.model_validate(row)

    async def update_accessory_requirement(
        self,
        session: AsyncSession,
        *,
        requirement_id: int,
        expected_version: int,
        payload: CrmGarmentAccessoryRequirementWrite,
    ) -> CrmGarmentAccessoryRequirementRead:
        row = await self.repository.get_accessory_requirement_for_update(session, requirement_id)
        if row is None:
            raise CrmAssortmentNotFoundError("Accessory requirement was not found")
        self._version(row.version, expected_version)
        await self._validate_accessory_requirement(session, payload)
        self._apply_accessory_requirement(row, payload)
        row.version += 1
        await session.flush()
        return CrmGarmentAccessoryRequirementRead.model_validate(row)

    async def list_boxes(
        self, session: AsyncSession, *, active: bool | None
    ) -> list[CrmPackagingBoxRead]:
        rows = await self.repository.list_boxes(session, active=active)
        return [CrmPackagingBoxRead.model_validate(row) for row in rows]

    async def list_packaging_rules(
        self, session: AsyncSession, *, model_id: int | None
    ) -> list[CrmGarmentPackagingRuleRead]:
        rows = await self.repository.list_packaging_rules(session, model_id=model_id)
        return [CrmGarmentPackagingRuleRead.model_validate(row) for row in rows]

    async def create_box(
        self, session: AsyncSession, payload: CrmPackagingBoxWrite
    ) -> CrmPackagingBoxRead:
        await self._validate_media(session, payload.photo_media_object_id)
        row = CrmPackagingBox(version=1)
        self._apply_box(row, payload)
        await self.repository.add(session, row)
        return CrmPackagingBoxRead.model_validate(row)

    async def update_box(
        self,
        session: AsyncSession,
        *,
        box_id: int,
        expected_version: int,
        payload: CrmPackagingBoxWrite,
    ) -> CrmPackagingBoxRead:
        row = await self.repository.get_box(session, box_id, lock=True)
        if row is None:
            raise CrmAssortmentNotFoundError("Packaging box was not found")
        self._version(row.version, expected_version)
        await self._validate_media(session, payload.photo_media_object_id)
        self._apply_box(row, payload)
        row.version += 1
        await session.flush()
        return CrmPackagingBoxRead.model_validate(row)

    async def create_packaging_rule(
        self, session: AsyncSession, payload: CrmGarmentPackagingRuleWrite
    ) -> CrmGarmentPackagingRuleRead:
        await self._validate_packaging_rule(session, payload)
        row = CrmGarmentPackagingRule(version=1)
        self._apply_packaging_rule(row, payload)
        await self.repository.add(session, row)
        return CrmGarmentPackagingRuleRead.model_validate(row)

    async def update_packaging_rule(
        self,
        session: AsyncSession,
        *,
        rule_id: int,
        expected_version: int,
        payload: CrmGarmentPackagingRuleWrite,
    ) -> CrmGarmentPackagingRuleRead:
        row = await self.repository.get_packaging_rule_for_update(session, rule_id)
        if row is None:
            raise CrmAssortmentNotFoundError("Packaging rule was not found")
        self._version(row.version, expected_version)
        await self._validate_packaging_rule(session, payload)
        self._apply_packaging_rule(row, payload)
        row.version += 1
        await session.flush()
        return CrmGarmentPackagingRuleRead.model_validate(row)

    async def _validate_pattern(
        self, session: AsyncSession, payload: CrmGarmentPatternWrite
    ) -> CrmGarmentSize:
        model = await self.repository.get_model(session, payload.garment_model_id)
        size = await self.repository.get_size(session, payload.garment_size_id)
        if model is None or not model.is_active:
            raise CrmAssortmentNotFoundError("Active garment model was not found")
        if size is None or size.garment_model_id != model.id or not size.is_active:
            raise CrmAssortmentConflictError("Pattern size must belong to the active model")
        if await self.repository.get_ready_media(session, payload.media_object_id) is None:
            raise CrmAssortmentConflictError("Pattern file must reference ready media")
        self._grid(payload.width_cm, size.min_width_cm, size.max_width_cm, "width")
        self._grid(payload.length_cm, size.min_length_cm, size.max_length_cm, "length")
        if payload.sleeve_length_cm is not None:
            self._grid(
                payload.sleeve_length_cm,
                size.min_sleeve_length_cm,
                size.max_sleeve_length_cm,
                "sleeve length",
            )
        if payload.height_cm is not None:
            self._grid(payload.height_cm, size.min_height_cm, size.max_height_cm, "height")
        return size

    async def _validate_fabric_requirement(
        self,
        session: AsyncSession,
        payload: CrmGarmentFabricRequirementWrite,
        *,
        exclude_id: int | None = None,
    ) -> None:
        model = await self.repository.get_model(session, payload.garment_model_id)
        fabric = await self.repository.get_fabric(session, payload.fabric_id)
        if model is None or not model.is_active:
            raise CrmAssortmentNotFoundError("Active garment model was not found")
        if fabric is None or not fabric.is_active:
            raise CrmAssortmentNotFoundError("Active fabric was not found")
        if payload.is_primary and await self.repository.get_primary_fabric_requirement(
            session,
            model_id=payload.garment_model_id,
            exclude_id=exclude_id,
        ):
            raise CrmAssortmentConflictError("Garment model already has a primary fabric")

    async def _validate_accessory(self, session: AsyncSession, payload: CrmAccessoryWrite) -> None:
        category = await self.repository.get_category(session, payload.category_id)
        if category is None or not category.is_active:
            raise CrmAssortmentNotFoundError("Active accessory category was not found")
        await self._validate_media(session, payload.photo_media_object_id)

    async def _validate_accessory_requirement(
        self, session: AsyncSession, payload: CrmGarmentAccessoryRequirementWrite
    ) -> None:
        model = await self.repository.get_model(session, payload.garment_model_id)
        accessory = await self.repository.get_accessory(session, payload.accessory_id)
        if model is None or not model.is_active:
            raise CrmAssortmentNotFoundError("Active garment model was not found")
        if accessory is None or not accessory.is_active:
            raise CrmAssortmentNotFoundError("Active accessory was not found")

    async def _validate_media(self, session: AsyncSession, media_id: int | None) -> None:
        if (
            media_id is not None
            and await self.repository.get_ready_media(session, media_id) is None
        ):
            raise CrmAssortmentConflictError("Photo must reference ready media")

    async def _validate_packaging_rule(
        self,
        session: AsyncSession,
        payload: CrmGarmentPackagingRuleWrite,
    ) -> None:
        model = await self.repository.get_model(session, payload.garment_model_id)
        box = await self.repository.get_box(session, payload.box_id)
        if model is None or not model.is_active:
            raise CrmAssortmentNotFoundError("Active garment model was not found")
        if box is None or not box.is_active:
            raise CrmAssortmentNotFoundError("Active packaging box was not found")
        if payload.max_items > box.max_items:
            raise CrmAssortmentConflictError(
                "Model packaging capacity cannot exceed the box capacity"
            )

    @staticmethod
    def _grid(
        value: Decimal,
        minimum: Decimal | None,
        maximum: Decimal | None,
        label: str,
    ) -> None:
        if minimum is None or maximum is None:
            raise CrmAssortmentConflictError(
                f"Garment size must define a {label} range before patterns can be added"
            )
        if value < minimum or value > maximum:
            raise CrmAssortmentConflictError(f"Pattern {label} is outside the size range")
        if (value - minimum) % GRID_STEP_CM != 0:
            raise CrmAssortmentConflictError(
                f"Pattern {label} must follow the 2 cm grid from the size minimum"
            )

    @staticmethod
    def _apply_pattern(
        row: CrmGarmentPattern,
        payload: CrmGarmentPatternWrite,
        size: CrmGarmentSize,
    ) -> None:
        row.garment_model_id = payload.garment_model_id
        row.code = payload.code
        row.garment_size_id = payload.garment_size_id
        row.media_object_id = payload.media_object_id
        row.name = payload.name
        row.width_cm = payload.width_cm
        row.length_cm = payload.length_cm
        row.sleeve_length_cm = payload.sleeve_length_cm
        row.height_cm = payload.height_cm
        row.grid_key = CrmAssortmentService._grid_key(payload, size)
        row.is_active = payload.is_active

    @staticmethod
    def _grid_key(payload: CrmGarmentPatternWrite, size: CrmGarmentSize) -> str:
        def part(value: Decimal | None) -> str:
            return "-" if value is None else format(value, ".2f")

        return ":".join(
            (
                size.code,
                part(payload.width_cm),
                part(payload.length_cm),
                part(payload.sleeve_length_cm),
                part(payload.height_cm),
            )
        )

    @staticmethod
    def _apply_fabric_requirement(
        row: CrmGarmentFabricRequirement,
        payload: CrmGarmentFabricRequirementWrite,
    ) -> None:
        row.garment_model_id = payload.garment_model_id
        row.fabric_id = payload.fabric_id
        row.meters_per_unit = payload.meters_per_unit
        row.waste_percent = payload.waste_percent
        row.is_primary = payload.is_primary

    @staticmethod
    def _apply_category(row: CrmAccessoryCategory, payload: CrmAccessoryCategoryWrite) -> None:
        row.code = payload.code
        row.name = payload.name
        row.description = payload.description
        row.is_active = payload.is_active

    @staticmethod
    def _apply_accessory(row: CrmAccessory, payload: CrmAccessoryWrite) -> None:
        row.category_id = payload.category_id
        row.code = payload.code
        row.name = payload.name
        row.unit_cost = payload.unit_cost
        row.currency = payload.currency
        row.stock_quantity = payload.stock_quantity
        row.minimum_stock_quantity = payload.minimum_stock_quantity
        row.photo_media_object_id = payload.photo_media_object_id
        row.is_active = payload.is_active

    @staticmethod
    def _accessory_read(
        row: CrmAccessory,
        *,
        model_ids: list[int] | None = None,
    ) -> CrmAccessoryRead:
        return CrmAccessoryRead(
            id=row.id,
            category_id=row.category_id,
            code=row.code,
            name=row.name,
            unit_cost=row.unit_cost,
            currency=row.currency,
            stock_quantity=row.stock_quantity,
            minimum_stock_quantity=row.minimum_stock_quantity,
            photo_media_object_id=row.photo_media_object_id,
            is_active=row.is_active,
            version=row.version,
            model_ids=(
                sorted(item.garment_model_id for item in row.model_requirements)
                if model_ids is None
                else model_ids
            ),
        )

    @staticmethod
    def _apply_accessory_requirement(
        row: CrmGarmentAccessoryRequirement,
        payload: CrmGarmentAccessoryRequirementWrite,
    ) -> None:
        row.garment_model_id = payload.garment_model_id
        row.accessory_id = payload.accessory_id
        row.quantity_per_unit = payload.quantity_per_unit
        row.is_optional = payload.is_optional
        row.notes = payload.notes

    @staticmethod
    def _apply_box(row: CrmPackagingBox, payload: CrmPackagingBoxWrite) -> None:
        row.code = payload.code
        row.name = payload.name
        row.inner_length_cm = payload.inner_length_cm
        row.inner_width_cm = payload.inner_width_cm
        row.inner_height_cm = payload.inner_height_cm
        row.max_items = payload.max_items
        row.unit_cost = payload.unit_cost
        row.currency = payload.currency
        row.stock_quantity = payload.stock_quantity
        row.minimum_stock_quantity = payload.minimum_stock_quantity
        row.photo_media_object_id = payload.photo_media_object_id
        row.is_active = payload.is_active

    @staticmethod
    def _apply_packaging_rule(
        row: CrmGarmentPackagingRule,
        payload: CrmGarmentPackagingRuleWrite,
    ) -> None:
        row.garment_model_id = payload.garment_model_id
        row.box_id = payload.box_id
        row.max_items = payload.max_items
        row.priority = payload.priority

    @staticmethod
    def _version(actual: int, expected: int) -> None:
        if actual != expected:
            raise CrmAssortmentVersionConflictError("Assortment record version has changed")
