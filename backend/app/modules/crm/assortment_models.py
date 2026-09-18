from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class CrmGarmentPattern(Base, IntegerIdMixin, TimestampMixin):
    """A production-ready pattern file for one exact point of a model size grid."""

    __tablename__ = "crm_garment_patterns"
    __table_args__ = (
        UniqueConstraint(
            "garment_model_id",
            "grid_key",
            name="uq_crm_garment_pattern_model_grid",
        ),
        CheckConstraint("length(trim(grid_key)) > 0", name="crm_pattern_grid_key_nonempty"),
        CheckConstraint("length(trim(name)) > 0", name="crm_pattern_name_nonempty"),
        CheckConstraint("width_cm > 0", name="crm_pattern_width_positive"),
        CheckConstraint("length_cm > 0", name="crm_pattern_length_positive"),
        CheckConstraint(
            "sleeve_length_cm IS NULL OR sleeve_length_cm > 0",
            name="crm_pattern_sleeve_positive",
        ),
        CheckConstraint(
            "height_cm IS NULL OR height_cm > 0",
            name="crm_pattern_height_positive",
        ),
        CheckConstraint("version > 0", name="crm_pattern_version_positive"),
    )

    garment_model_id: Mapped[int] = mapped_column(
        ForeignKey("crm_garment_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    garment_size_id: Mapped[int] = mapped_column(
        ForeignKey("crm_garment_sizes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    media_object_id: Mapped[int] = mapped_column(
        ForeignKey("media_objects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    grid_key: Mapped[str] = mapped_column(String(160), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    width_cm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    length_cm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    sleeve_length_cm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    garment_model = relationship("CrmGarmentModel", back_populates="patterns")
    garment_size = relationship("CrmGarmentSize")
    media = relationship("MediaObject")


class CrmGarmentFabricRequirement(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "crm_garment_fabric_requirements"
    __table_args__ = (
        UniqueConstraint(
            "garment_model_id",
            "fabric_id",
            name="uq_crm_garment_fabric_requirement",
        ),
        CheckConstraint(
            "meters_per_unit > 0",
            name="crm_garment_fabric_meters_positive",
        ),
        CheckConstraint(
            "waste_percent >= 0 AND waste_percent <= 100",
            name="crm_garment_fabric_waste_valid",
        ),
        CheckConstraint("version > 0", name="crm_garment_fabric_version_positive"),
    )

    garment_model_id: Mapped[int] = mapped_column(
        ForeignKey("crm_garment_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fabric_id: Mapped[int] = mapped_column(
        ForeignKey("crm_fabrics.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    meters_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    waste_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=0,
        server_default="0",
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    garment_model = relationship("CrmGarmentModel", back_populates="fabric_requirements")
    fabric = relationship("CrmFabric")


class CrmAccessoryCategory(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "crm_accessory_categories"
    __table_args__ = (
        CheckConstraint("length(trim(code)) > 0", name="crm_accessory_category_code_nonempty"),
        CheckConstraint("length(trim(name)) > 0", name="crm_accessory_category_name_nonempty"),
        CheckConstraint("version > 0", name="crm_accessory_category_version_positive"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    accessories = relationship("CrmAccessory", back_populates="category")


class CrmAccessory(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "crm_accessories"
    __table_args__ = (
        CheckConstraint("length(trim(code)) > 0", name="crm_accessory_code_nonempty"),
        CheckConstraint("length(trim(name)) > 0", name="crm_accessory_name_nonempty"),
        CheckConstraint("unit_cost >= 0", name="crm_accessory_cost_nonnegative"),
        CheckConstraint("currency = 'RUB'", name="crm_accessory_currency_rub"),
        CheckConstraint("stock_quantity >= 0", name="crm_accessory_stock_nonnegative"),
        CheckConstraint(
            "minimum_stock_quantity >= 0",
            name="crm_accessory_minimum_stock_nonnegative",
        ),
        CheckConstraint("version > 0", name="crm_accessory_version_positive"),
    )

    category_id: Mapped[int] = mapped_column(
        ForeignKey("crm_accessory_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, server_default="0"
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="RUB", server_default="RUB"
    )
    stock_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    minimum_stock_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    photo_media_object_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_objects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    category = relationship("CrmAccessoryCategory", back_populates="accessories")
    photo = relationship("MediaObject")
    model_requirements = relationship(
        "CrmGarmentAccessoryRequirement",
        back_populates="accessory",
        cascade="all, delete-orphan",
    )


class CrmGarmentAccessoryRequirement(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "crm_garment_accessory_requirements"
    __table_args__ = (
        UniqueConstraint(
            "garment_model_id",
            "accessory_id",
            name="uq_crm_garment_accessory_requirement",
        ),
        CheckConstraint(
            "quantity_per_unit > 0",
            name="crm_garment_accessory_quantity_positive",
        ),
        CheckConstraint("version > 0", name="crm_garment_accessory_version_positive"),
    )

    garment_model_id: Mapped[int] = mapped_column(
        ForeignKey("crm_garment_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    accessory_id: Mapped[int] = mapped_column(
        ForeignKey("crm_accessories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    is_optional: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    garment_model = relationship("CrmGarmentModel", back_populates="accessory_requirements")
    accessory = relationship("CrmAccessory", back_populates="model_requirements")


class CrmPackagingBox(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "crm_packaging_boxes"
    __table_args__ = (
        CheckConstraint("length(trim(code)) > 0", name="crm_box_code_nonempty"),
        CheckConstraint("length(trim(name)) > 0", name="crm_box_name_nonempty"),
        CheckConstraint("inner_length_cm > 0", name="crm_box_length_positive"),
        CheckConstraint("inner_width_cm > 0", name="crm_box_width_positive"),
        CheckConstraint("inner_height_cm > 0", name="crm_box_height_positive"),
        CheckConstraint("max_items > 0", name="crm_box_max_items_positive"),
        CheckConstraint("unit_cost >= 0", name="crm_box_cost_nonnegative"),
        CheckConstraint("currency = 'RUB'", name="crm_box_currency_rub"),
        CheckConstraint("stock_quantity >= 0", name="crm_box_stock_nonnegative"),
        CheckConstraint(
            "minimum_stock_quantity >= 0",
            name="crm_box_minimum_stock_nonnegative",
        ),
        CheckConstraint("version > 0", name="crm_box_version_positive"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    inner_length_cm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    inner_width_cm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    inner_height_cm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    max_items: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, server_default="0"
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="RUB", server_default="RUB"
    )
    stock_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    minimum_stock_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    photo_media_object_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_objects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    photo = relationship("MediaObject")
    model_rules = relationship(
        "CrmGarmentPackagingRule",
        back_populates="box",
        cascade="all, delete-orphan",
    )


class CrmGarmentPackagingRule(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "crm_garment_packaging_rules"
    __table_args__ = (
        UniqueConstraint(
            "garment_model_id",
            "box_id",
            name="uq_crm_garment_packaging_rule",
        ),
        CheckConstraint("max_items > 0", name="crm_garment_packaging_max_items_positive"),
        CheckConstraint("priority >= 0", name="crm_garment_packaging_priority_nonnegative"),
        CheckConstraint("version > 0", name="crm_garment_packaging_version_positive"),
    )

    garment_model_id: Mapped[int] = mapped_column(
        ForeignKey("crm_garment_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    box_id: Mapped[int] = mapped_column(
        ForeignKey("crm_packaging_boxes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    max_items: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    garment_model = relationship("CrmGarmentModel", back_populates="packaging_rules")
    box = relationship("CrmPackagingBox", back_populates="model_rules")
