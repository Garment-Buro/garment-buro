from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin


class UserCommunityFavorite(Base, IntegerIdMixin):
    __tablename__ = "user_community_favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "landing_id", name="uq_user_community_favorites_user_landing"),
        Index("ix_user_community_favorites_user_recent", "user_id", "id"),
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    landing_id: Mapped[int] = mapped_column(
        ForeignKey("partner_landings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
