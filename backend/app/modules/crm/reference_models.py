from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin, TimestampMixin

CRM_REFERENCE_DETAILS_TYPE = JSON().with_variant(JSONB, "postgresql")


class CrmTechCardRevisionStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    DISCARDED = "discarded"


class CrmReferenceEntityType(str, Enum):
    FABRIC = "fabric"
    GARMENT_MODEL = "garment_model"
    CATALOG_PRODUCT_LINK = "catalog_product_link"
    TECH_CARD = "tech_card"
    TECH_CARD_REVISION = "tech_card_revision"


class CrmReferenceAction(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    LINKED = "linked"
    REVISION_CREATED = "revision_created"
    PUBLISHED = "published"
    DISCARDED = "discarded"


class CrmFabric(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "crm_fabrics"
    __table_args__ = (
        CheckConstraint("length(trim(code)) > 0", name="crm_fabric_code_nonempty"),
        CheckConstraint("length(trim(name)) > 0", name="crm_fabric_name_nonempty"),
        CheckConstraint("length(trim(color_name)) > 0", name="crm_fabric_color_nonempty"),
        CheckConstraint(
            "density_gsm IS NULL OR density_gsm > 0",
            name="crm_fabric_density_positive",
        ),
        CheckConstraint("width_cm > 0", name="crm_fabric_width_positive"),
        CheckConstraint(
            "cost_per_meter IS NULL OR cost_per_meter >= 0",
            name="crm_fabric_cost_nonnegative",
        ),
        CheckConstraint("currency = 'RUB'", name="crm_fabric_currency_rub"),
        CheckConstraint("version > 0", name="crm_fabric_version_positive"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    material_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    color_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    color_hex: Mapped[str | None] = mapped_column(String(7), nullable=True)
    density_gsm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    width_cm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    cost_per_meter: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="RUB",
        server_default="RUB",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class CrmGarmentModel(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "crm_garment_models"
    __table_args__ = (
        CheckConstraint("length(trim(code)) > 0", name="crm_garment_model_code_nonempty"),
        CheckConstraint("length(trim(name)) > 0", name="crm_garment_model_name_nonempty"),
        CheckConstraint(
            "base_height_cm IS NULL OR base_height_cm > 0",
            name="crm_garment_model_height_positive",
        ),
        CheckConstraint(
            "base_length_cm IS NULL OR base_length_cm > 0",
            name="crm_garment_model_length_positive",
        ),
        CheckConstraint(
            "base_width_cm IS NULL OR base_width_cm > 0",
            name="crm_garment_model_width_positive",
        ),
        CheckConstraint(
            "base_weight_g IS NULL OR base_weight_g > 0",
            name="crm_garment_model_weight_positive",
        ),
        CheckConstraint("version > 0", name="crm_garment_model_version_positive"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_height_cm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    base_length_cm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    base_width_cm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    base_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    sizes: Mapped[list[CrmGarmentSize]] = relationship(
        back_populates="garment_model",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="(CrmGarmentSize.sort_order, CrmGarmentSize.id)",
    )
    catalog_links: Mapped[list[CrmCatalogProductModelLink]] = relationship(
        back_populates="garment_model",
        passive_deletes=True,
        order_by="CrmCatalogProductModelLink.id",
    )
    tech_card: Mapped[CrmTechCard | None] = relationship(
        back_populates="garment_model",
        uselist=False,
        passive_deletes=True,
    )


class CrmGarmentSize(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "crm_garment_sizes"
    __table_args__ = (
        UniqueConstraint("garment_model_id", "code", name="uq_crm_garment_size_code"),
        CheckConstraint("length(trim(code)) > 0", name="crm_garment_size_code_nonempty"),
        CheckConstraint("sort_order >= 0", name="crm_garment_size_sort_nonnegative"),
        CheckConstraint("base_price >= 0", name="crm_garment_size_price_nonnegative"),
        CheckConstraint(
            "min_height_cm IS NULL OR min_height_cm > 0",
            name="crm_garment_size_min_height_positive",
        ),
        CheckConstraint(
            "max_height_cm IS NULL OR max_height_cm > 0",
            name="crm_garment_size_max_height_positive",
        ),
        CheckConstraint(
            "min_height_cm IS NULL OR max_height_cm IS NULL OR min_height_cm <= max_height_cm",
            name="crm_garment_size_height_range_valid",
        ),
        CheckConstraint(
            "min_length_cm IS NULL OR min_length_cm > 0",
            name="crm_garment_size_min_length_positive",
        ),
        CheckConstraint(
            "max_length_cm IS NULL OR max_length_cm > 0",
            name="crm_garment_size_max_length_positive",
        ),
        CheckConstraint(
            "min_length_cm IS NULL OR max_length_cm IS NULL OR min_length_cm <= max_length_cm",
            name="crm_garment_size_length_range_valid",
        ),
        CheckConstraint(
            "min_width_cm IS NULL OR min_width_cm > 0",
            name="crm_garment_size_min_width_positive",
        ),
        CheckConstraint(
            "max_width_cm IS NULL OR max_width_cm > 0",
            name="crm_garment_size_max_width_positive",
        ),
        CheckConstraint(
            "min_width_cm IS NULL OR max_width_cm IS NULL OR min_width_cm <= max_width_cm",
            name="crm_garment_size_width_range_valid",
        ),
        CheckConstraint(
            "extra_width_price_per_cm IS NULL OR extra_width_price_per_cm >= 0",
            name="crm_garment_size_extra_width_price_nonnegative",
        ),
        CheckConstraint("currency = 'RUB'", name="crm_garment_size_currency_rub"),
        CheckConstraint("version > 0", name="crm_garment_size_version_positive"),
        Index(
            "ix_crm_garment_sizes_model_active_sort", "garment_model_id", "is_active", "sort_order"
        ),
    )

    garment_model_id: Mapped[int] = mapped_column(
        ForeignKey("crm_garment_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    base_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
        server_default="0",
    )
    min_height_cm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    max_height_cm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    min_length_cm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    max_length_cm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    min_width_cm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    max_width_cm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    extra_width_price_per_cm: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="RUB",
        server_default="RUB",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    garment_model: Mapped[CrmGarmentModel] = relationship(back_populates="sizes")


class CrmCatalogProductModelLink(Base, IntegerIdMixin):
    __tablename__ = "crm_catalog_product_model_links"
    __table_args__ = (
        UniqueConstraint(
            "catalog_product_id",
            name="uq_crm_catalog_product_model_link_product",
        ),
    )

    garment_model_id: Mapped[int] = mapped_column(
        ForeignKey("crm_garment_models.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    catalog_product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    garment_model: Mapped[CrmGarmentModel] = relationship(back_populates="catalog_links")


class CrmTechCard(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "crm_tech_cards"
    __table_args__ = (
        CheckConstraint("length(trim(code)) > 0", name="crm_tech_card_code_nonempty"),
        CheckConstraint(
            "latest_revision_number > 0",
            name="crm_tech_card_latest_revision_positive",
        ),
    )

    garment_model_id: Mapped[int] = mapped_column(
        ForeignKey("crm_garment_models.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    latest_revision_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    garment_model: Mapped[CrmGarmentModel] = relationship(back_populates="tech_card")
    revisions: Mapped[list[CrmTechCardRevision]] = relationship(
        back_populates="tech_card",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CrmTechCardRevision.revision_number",
        foreign_keys="CrmTechCardRevision.tech_card_id",
    )


class CrmTechCardRevision(Base, IntegerIdMixin):
    __tablename__ = "crm_tech_card_revisions"
    __table_args__ = (
        UniqueConstraint(
            "tech_card_id",
            "revision_number",
            name="uq_crm_tech_card_revision_number",
        ),
        UniqueConstraint(
            "tech_card_id",
            "id",
            name="uq_crm_tech_card_revision_card_identity",
        ),
        ForeignKeyConstraint(
            ["tech_card_id", "based_on_revision_id"],
            ["crm_tech_card_revisions.tech_card_id", "crm_tech_card_revisions.id"],
            name="fk_crm_tech_card_revision_same_card_base",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "revision_number > 0",
            name="crm_tech_card_revision_number_positive",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'archived', 'discarded')",
            name="crm_tech_card_revision_status_valid",
        ),
        CheckConstraint(
            "length(trim(name_snapshot)) > 0",
            name="crm_tech_card_revision_name_nonempty",
        ),
        CheckConstraint(
            "(status IN ('draft', 'discarded') AND published_at IS NULL "
            "AND published_by_user_id IS NULL) OR "
            "(status IN ('published', 'archived') AND published_at IS NOT NULL "
            "AND published_by_user_id IS NOT NULL)",
            name="crm_tech_card_revision_publication_consistent",
        ),
        Index(
            "uq_crm_tech_card_revision_draft",
            "tech_card_id",
            unique=True,
            postgresql_where=text("status = 'draft'"),
            sqlite_where=text("status = 'draft'"),
        ),
        Index(
            "uq_crm_tech_card_revision_published",
            "tech_card_id",
            unique=True,
            postgresql_where=text("status = 'published'"),
            sqlite_where=text("status = 'published'"),
        ),
    )

    tech_card_id: Mapped[int] = mapped_column(
        ForeignKey("crm_tech_cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    based_on_revision_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CrmTechCardRevisionStatus.DRAFT.value,
        server_default=CrmTechCardRevisionStatus.DRAFT.value,
        index=True,
    )
    name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    description_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    published_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tech_card: Mapped[CrmTechCard] = relationship(
        back_populates="revisions",
        foreign_keys=[tech_card_id],
    )
    checkpoints: Mapped[list[CrmTechCardCheckpoint]] = relationship(
        back_populates="revision",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CrmTechCardCheckpoint.position",
    )


class CrmTechCardCheckpoint(Base, IntegerIdMixin):
    __tablename__ = "crm_tech_card_checkpoints"
    __table_args__ = (
        UniqueConstraint(
            "tech_card_revision_id",
            "position",
            name="uq_crm_tech_card_checkpoint_position",
        ),
        CheckConstraint("position > 0", name="crm_tech_card_checkpoint_position_positive"),
        CheckConstraint(
            "length(trim(stage_code)) > 0",
            name="crm_tech_card_checkpoint_stage_nonempty",
        ),
        CheckConstraint(
            "length(trim(name)) > 0",
            name="crm_tech_card_checkpoint_name_nonempty",
        ),
        CheckConstraint(
            "standard_minutes IS NULL OR standard_minutes > 0",
            name="crm_tech_card_checkpoint_minutes_positive",
        ),
        CheckConstraint(
            "labor_cost >= 0",
            name="crm_tech_card_checkpoint_labor_cost_nonnegative",
        ),
        CheckConstraint("currency = 'RUB'", name="crm_tech_card_checkpoint_currency_rub"),
    )

    tech_card_revision_id: Mapped[int] = mapped_column(
        ForeignKey("crm_tech_card_revisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    standard_minutes: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    labor_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
        server_default="0",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="RUB",
        server_default="RUB",
    )

    revision: Mapped[CrmTechCardRevision] = relationship(back_populates="checkpoints")


class CrmReferenceEvent(Base, IntegerIdMixin):
    __tablename__ = "crm_reference_events"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "entity_version",
            "action",
            name="uq_crm_reference_event_identity",
        ),
        CheckConstraint(
            "entity_type IN ('fabric', 'garment_model', 'catalog_product_link', "
            "'tech_card', 'tech_card_revision')",
            name="crm_reference_event_entity_type_valid",
        ),
        CheckConstraint(
            "action IN ('created', 'updated', 'linked', 'revision_created', 'published', "
            "'discarded')",
            name="crm_reference_event_action_valid",
        ),
        CheckConstraint("entity_id > 0", name="crm_reference_event_entity_positive"),
        CheckConstraint(
            "entity_version > 0",
            name="crm_reference_event_version_positive",
        ),
        CheckConstraint(
            "length(snapshot_sha256) = 64",
            name="crm_reference_event_snapshot_digest_length",
        ),
    )

    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    entity_version: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(
        CRM_REFERENCE_DETAILS_TYPE,
        nullable=False,
        default=dict,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
