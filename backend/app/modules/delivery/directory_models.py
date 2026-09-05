from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PickupPoint(Base):
    __tablename__ = "delivery_pickup_points"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class PickupDirectoryState(Base):
    __tablename__ = "delivery_directory_state"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
