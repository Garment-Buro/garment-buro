from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, column
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin
from app.db.text import UnicodeLower


class PublicUserProfile(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "public_user_profiles"
    __table_args__ = (
        CheckConstraint("version > 0", name="public_profile_version_positive"),
        CheckConstraint(
            "length(slug) BETWEEN 3 AND 64 AND slug = lower(slug)", name="public_profile_slug_valid"
        ),
        CheckConstraint("length(display_name) BETWEEN 1 AND 120", name="public_profile_name_valid"),
        CheckConstraint("length(bio) <= 2000", name="public_profile_bio_bounded"),
        Index("ix_public_profiles_published_recent", "is_published", "id"),
        Index(
            "ix_public_profiles_published_name",
            "is_published",
            UnicodeLower(column("display_name")),
            "id",
        ),
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    avatar_media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_objects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    bio: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
