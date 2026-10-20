"""Editor-source budgets come from the existing write fields, not a photo quota."""

from annotated_types import MaxLen

from app.core.config import Settings
from app.modules.catalog.schemas import ProductVariantWriteRequest, ProductWriteRequest
from app.modules.media.models import MediaStatus, ProductMediaRole, ProductVariantMediaRole
from app.modules.media.read_models import CatalogMediaLinkView
from app.modules.media.urls import public_media_url


def field_limits(schema, roles) -> dict[str, int]:
    return {
        role.value: next(
            constraint.max_length
            for constraint in schema.model_fields[role.value].metadata
            if isinstance(constraint, MaxLen)
        )
        for role in roles
    }


PRODUCT_MEDIA_FIELD_LIMITS = field_limits(ProductWriteRequest, ProductMediaRole)
VARIANT_MEDIA_FIELD_LIMITS = field_limits(ProductVariantWriteRequest, ProductVariantMediaRole)


class CatalogEditorMediaLimitError(ValueError):
    pass


def catalog_editor_media_limit_detail() -> dict[str, str]:
    return {
        "code": "catalog_editor_media_limit",
        "message": (
            "Состав медиа пресета превышает допустимый объём формы. "
            "Данные не изменены. Нужна проверка изображений перед редактированием."
        ),
    }


class CatalogEditorMediaBudget:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.used: dict[tuple[bool, int, str], int] = {}
        self.totals: dict[tuple[bool, int], int] = {}

    def accept(self, link: CatalogMediaLinkView, *, variant: bool) -> None:
        limits = VARIANT_MEDIA_FIELD_LIMITS if variant else PRODUCT_MEDIA_FIELD_LIMITS
        media = link.media
        if media.is_public and media.status == MediaStatus.READY.value:
            size = len(public_media_url(self.settings, media))
        else:
            # Hidden rows still consume source memory. Do not map/expose their URLs or
            # require a public origin just to account for their stored object keys.
            size = max(1, len(media.object_key) + 1)
        key = (variant, link.owner_id, link.role)
        if link.role in limits:
            # Count CSV separators too; duplicate/hidden/single-role rows are retained
            # in the snapshot and therefore consume its conservative field budget.
            used = self.used.get(key, -1) + size + 1
            if used > limits[link.role]:
                raise CatalogEditorMediaLimitError
            self.used[key] = used
        owner = (variant, link.owner_id)
        total = self.totals.get(owner, 0) + size + 1
        # Unknown legacy roles cannot create an unbounded side channel in media_assets.
        if total > sum(limit + 1 for limit in limits.values()):
            raise CatalogEditorMediaLimitError
        self.totals[owner] = total
