from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.modules.catalog.models import Product, ProductVariant


class MediaStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class ProductMediaRole(str, Enum):
    VIDEO_SRC = "video_src"
    IMAGE_LEFT = "image_left"
    IMAGE_RIGHT = "image_right"
    GALLERY_IMAGES = "gallery_images"
    SIZE_CHART_IMG_1 = "size_chart_img_1"
    SIZE_CHART_IMG_2 = "size_chart_img_2"
    DESKTOP_VIDEO = "desktop_video"
    DESKTOP_VIDEO_POSTER = "desktop_video_poster"
    DESKTOP_CARD_IMAGES = "desktop_card_images"
    DESKTOP_SLIDER_IMAGES = "desktop_slider_images"
    MOBILE_CARD_IMAGE = "mobile_card_image"
    MOBILE_VIDEO_POSTER = "mobile_video_poster"
    MOBILE_SLIDER_IMAGES = "mobile_slider_images"
    MOBILE_PRODUCT_SLIDER_IMAGES = "mobile_product_slider_images"
    MOBILE_SIZE_CHART_FIRST = "mobile_size_chart_first"


class ProductVariantMediaRole(str, Enum):
    PREVIEW_IMAGE = "preview_image"
    IMAGES = "images"


class MediaObject(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "media_objects"
    __table_args__ = (
        UniqueConstraint(
            "bucket_name",
            "object_key",
            name="uq_media_object_bucket_key",
        ),
        CheckConstraint("size_bytes > 0", name="media_object_size_positive"),
        CheckConstraint(
            "length(checksum_sha256) = 64",
            name="media_object_checksum_length",
        ),
        CheckConstraint(
            "status IN ('pending', 'ready', 'failed', 'deleted')",
            name="media_object_status_valid",
        ),
    )

    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="minio",
        server_default="minio",
    )
    uploaded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    bucket_name: Mapped[str] = mapped_column(String(63), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    etag: Mapped[str | None] = mapped_column(String(128), nullable=True)
    version_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=MediaStatus.PENDING.value,
        server_default=MediaStatus.PENDING.value,
        index=True,
    )

    product_links: Mapped[list[ProductMedia]] = relationship(back_populates="media")
    variant_links: Mapped[list[ProductVariantMedia]] = relationship(back_populates="media")


class ProductMedia(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "product_media"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "role",
            "sort_order",
            name="uq_product_media_role_order",
        ),
        CheckConstraint("sort_order >= 0", name="product_media_sort_order_nonnegative"),
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_object_id: Mapped[int] = mapped_column(
        ForeignKey("media_objects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)

    product: Mapped[Product] = relationship(back_populates="media_links")
    media: Mapped[MediaObject] = relationship(back_populates="product_links")


class ProductVariantMedia(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "product_variant_media"
    __table_args__ = (
        UniqueConstraint(
            "product_variant_id",
            "role",
            "sort_order",
            name="uq_product_variant_media_role_order",
        ),
        CheckConstraint(
            "sort_order >= 0",
            name="product_variant_media_sort_order_nonnegative",
        ),
    )

    product_variant_id: Mapped[int] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_object_id: Mapped[int] = mapped_column(
        ForeignKey("media_objects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)

    variant: Mapped[ProductVariant] = relationship(back_populates="media_links")
    media: Mapped[MediaObject] = relationship(back_populates="variant_links")
