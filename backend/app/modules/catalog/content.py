from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConfigurationError
from app.db.session import DatabaseManager
from app.modules.catalog.models import (
    CatalogContentMigrationRun,
    CatalogDocument,
    CatalogDocumentRevision,
)

DocumentKey = Literal["settings", "options"]


class LandingLink(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str = Field(max_length=255)
    url: str = Field(max_length=2048)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Landing link label must not be blank")
        return normalized

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return _validate_public_url(value)


class LandingSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    logo_video_url: str = Field(default="/logo_anim.mp4", max_length=4096)
    hero_products: list[int] = Field(default_factory=lambda: [1, 2, 3, 4], max_length=100)
    showroom1_products: list[int] = Field(default_factory=lambda: [2, 3, 4], max_length=100)
    showroom2_products: list[int] = Field(default_factory=lambda: [1, 2, 3, 4], max_length=100)
    links: dict[str, LandingLink] = Field(default_factory=dict)

    @field_validator("logo_video_url")
    @classmethod
    def validate_logo_url(cls, value: str) -> str:
        return _validate_public_url(value)

    @field_validator("links")
    @classmethod
    def validate_links(cls, values: dict[str, LandingLink]) -> dict[str, LandingLink]:
        if len(values) > 100 or any(not key or len(key) > 128 for key in values):
            raise ValueError("Landing links must have 1-128 character keys and at most 100 items")
        return values

    @field_validator("hero_products", "showroom1_products", "showroom2_products")
    @classmethod
    def validate_product_ids(cls, values: list[int]) -> list[int]:
        if any(value <= 0 for value in values):
            raise ValueError("Catalog section product IDs must be positive")
        return values


class ColorOption(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str = Field(min_length=1, max_length=255)
    hex: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")


class VariantOptions(BaseModel):
    model_config = ConfigDict(extra="ignore")

    colors: list[ColorOption] = Field(max_length=100)
    sizes: list[str] = Field(max_length=100)

    @field_validator("sizes")
    @classmethod
    def validate_sizes(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 32 for value in normalized):
            raise ValueError("Variant sizes must contain 1-32 characters")
        return normalized


DEFAULT_SETTINGS = LandingSettings()
DEFAULT_OPTIONS = VariantOptions(
    colors=[
        ColorOption(label="Черный", hex="#1A1A1A"),
        ColorOption(label="Белый", hex="#FFFFFF"),
    ],
    sizes=["XS", "S", "M", "L", "XL", "XXL"],
)


class CatalogContentError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CatalogContentPlan:
    settings: dict[str, object]
    options: dict[str, object]
    fingerprint: str
    settings_source: str
    options_source: str

    @property
    def documents(self) -> dict[DocumentKey, dict[str, object]]:
        return {"settings": self.settings, "options": self.options}

    def report(self) -> dict[str, object]:
        return {
            "valid": True,
            "fingerprint_sha256": self.fingerprint,
            "documents_count": 2,
            "sources": {
                "settings": self.settings_source,
                "options": self.options_source,
            },
            "counts": {
                "links": len(self.settings["links"]),
                "colors": len(self.options["colors"]),
                "sizes": len(self.options["sizes"]),
            },
        }


class LegacyCatalogContentPlanner:
    def build(self, uploads_path: Path) -> CatalogContentPlan:
        uploads_path = uploads_path.expanduser().resolve()
        settings, settings_source = self._read_document(
            uploads_path / "settings.json",
            LandingSettings,
            DEFAULT_SETTINGS,
        )
        options, options_source = self._read_document(
            uploads_path / "variant_options.json",
            VariantOptions,
            DEFAULT_OPTIONS,
        )
        documents = {"settings": settings, "options": options}
        fingerprint = hashlib.sha256(self._canonical(documents)).hexdigest()
        return CatalogContentPlan(
            settings=settings,
            options=options,
            fingerprint=fingerprint,
            settings_source=settings_source,
            options_source=options_source,
        )

    @staticmethod
    def _read_document(
        path: Path,
        schema: type[BaseModel],
        default: BaseModel,
    ) -> tuple[dict[str, object], str]:
        if not path.exists():
            return default.model_dump(mode="json"), "default"
        if not path.is_file():
            raise CatalogContentError(f"Catalog content source is not a file: {path.name}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            validated = schema.model_validate(raw)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            raise CatalogContentError(f"Invalid catalog content document: {path.name}") from error
        return validated.model_dump(mode="json"), "file"

    @staticmethod
    def _canonical(payload: dict[str, object]) -> bytes:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class CatalogContentMigrationResult:
    fingerprint_sha256: str
    documents: int


class CatalogContentMigrationService:
    async def apply(
        self,
        session: AsyncSession,
        plan: CatalogContentPlan,
    ) -> CatalogContentMigrationResult:
        existing_run = await session.scalar(
            select(CatalogContentMigrationRun).where(
                CatalogContentMigrationRun.fingerprint_sha256 == plan.fingerprint
            )
        )
        if existing_run is not None:
            await self._verify_documents(session, plan)
            return CatalogContentMigrationResult(plan.fingerprint, existing_run.documents_count)
        existing_documents = await session.scalar(select(func.count(CatalogDocument.document_key)))
        if existing_documents:
            raise CatalogContentError(
                "Target catalog documents already exist with no matching migration run"
            )
        for document_key, payload in plan.documents.items():
            session.add(
                CatalogDocument(
                    document_key=document_key,
                    payload=payload,
                    version=1,
                )
            )
            session.add(
                CatalogDocumentRevision(
                    document_key=document_key,
                    version=1,
                    payload=payload,
                    actor_user_id=None,
                )
            )
        session.add(
            CatalogContentMigrationRun(
                fingerprint_sha256=plan.fingerprint,
                documents_count=2,
            )
        )
        await session.flush()
        return CatalogContentMigrationResult(plan.fingerprint, 2)

    @staticmethod
    async def _verify_documents(
        session: AsyncSession,
        plan: CatalogContentPlan,
    ) -> None:
        for document_key, payload in plan.documents.items():
            document = await session.get(CatalogDocument, document_key)
            revision = await session.scalar(
                select(CatalogDocumentRevision).where(
                    CatalogDocumentRevision.document_key == document_key,
                    CatalogDocumentRevision.version == 1,
                )
            )
            if document is None or revision is None or revision.payload != payload:
                raise CatalogContentError(
                    "Existing catalog content migration does not match target documents"
                )


class CatalogContentService:
    async def get_settings(self, session: AsyncSession) -> LandingSettings:
        return LandingSettings.model_validate(await self._get_payload(session, "settings"))

    async def get_options(self, session: AsyncSession) -> VariantOptions:
        return VariantOptions.model_validate(await self._get_payload(session, "options"))

    async def update_settings(
        self,
        session: AsyncSession,
        *,
        payload: LandingSettings,
        actor_user_id: int,
    ) -> LandingSettings:
        await self._update(session, "settings", payload.model_dump(mode="json"), actor_user_id)
        return payload

    async def update_options(
        self,
        session: AsyncSession,
        *,
        payload: VariantOptions,
        actor_user_id: int,
    ) -> VariantOptions:
        await self._update(session, "options", payload.model_dump(mode="json"), actor_user_id)
        return payload

    @staticmethod
    async def _get_payload(
        session: AsyncSession,
        document_key: DocumentKey,
    ) -> dict[str, object]:
        document = await session.get(CatalogDocument, document_key)
        if document is None:
            raise ConfigurationError(f"Catalog document is missing: {document_key}")
        return document.payload

    @staticmethod
    async def _update(
        session: AsyncSession,
        document_key: DocumentKey,
        payload: dict[str, object],
        actor_user_id: int,
    ) -> None:
        document = await session.scalar(
            select(CatalogDocument)
            .where(CatalogDocument.document_key == document_key)
            .with_for_update()
        )
        if document is None:
            raise ConfigurationError(f"Catalog document is missing: {document_key}")
        document.version += 1
        document.payload = payload
        document.updated_by_user_id = actor_user_id
        session.add(
            CatalogDocumentRevision(
                document_key=document_key,
                version=document.version,
                payload=payload,
                actor_user_id=actor_user_id,
            )
        )
        await session.flush()


async def verify_catalog_content_cutover(
    database: DatabaseManager,
    expected_fingerprint: str,
) -> None:
    async with database.session() as session:
        migration_run = await session.scalar(
            select(CatalogContentMigrationRun).where(
                CatalogContentMigrationRun.fingerprint_sha256 == expected_fingerprint
            )
        )
        if migration_run is None or migration_run.documents_count != 2:
            raise ConfigurationError("Reviewed catalog content migration is not present")
        documents = list(await session.scalars(select(CatalogDocument)))
        if {document.document_key for document in documents} != {"settings", "options"}:
            raise ConfigurationError("Catalog settings/options documents are incomplete")
        for document in documents:
            revision = await session.scalar(
                select(CatalogDocumentRevision.id).where(
                    CatalogDocumentRevision.document_key == document.document_key,
                    CatalogDocumentRevision.version == document.version,
                )
            )
            if revision is None:
                raise ConfigurationError("Catalog document revision history is incomplete")
        initial_revisions = list(
            await session.scalars(
                select(CatalogDocumentRevision).where(CatalogDocumentRevision.version == 1)
            )
        )
        initial_documents = {
            revision.document_key: revision.payload for revision in initial_revisions
        }
        if set(initial_documents) != {"settings", "options"}:
            raise ConfigurationError("Initial catalog content revisions are incomplete")
        actual_fingerprint = hashlib.sha256(
            LegacyCatalogContentPlanner._canonical(initial_documents)
        ).hexdigest()
        if actual_fingerprint != expected_fingerprint:
            raise ConfigurationError("Catalog content fingerprint does not match initial revisions")


def _validate_public_url(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("/") and not normalized.startswith("//") and "\\" not in normalized:
        return normalized
    parsed = urlsplit(normalized)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return normalized
    raise ValueError("URL must be an absolute HTTP(S) URL or a same-origin path")
