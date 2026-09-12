from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerIdMixin, TimestampMixin


class ProductionCredential(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "production_credentials"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    station: Mapped[str] = mapped_column(String(24))
    code_digest: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ProductionSession(Base):
    __tablename__ = "production_sessions"

    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    credential_id: Mapped[int] = mapped_column(
        ForeignKey("production_credentials.id", ondelete="RESTRICT"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ProductionLoginLimit(Base):
    __tablename__ = "production_login_limits"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ProductionEmployee(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "production_employees"
    __table_args__ = (
        CheckConstraint(
            "availability IN ('available','sick','vacation','absent')",
            name="production_availability_valid",
        ),
        CheckConstraint(
            "primary_station IN ('tech','kit','cut','dtf','workshop','application','sewing','press','qc','packing','shipping')",
            name="production_employee_station_valid",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, unique=True, index=True
    )
    primary_station: Mapped[str] = mapped_column(String(24), nullable=False)
    availability: Mapped[str] = mapped_column(
        String(24), default="available", server_default="available"
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
