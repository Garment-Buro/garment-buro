from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerIdMixin, TimestampMixin

if TYPE_CHECKING:
    from collections.abc import Sequence

SECURITY_DETAILS_TYPE = JSON().with_variant(JSONB, "postgresql")


class UserStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    DELETED = "deleted"


class RoleName(str, Enum):
    CUSTOMER = "customer"
    MANAGER = "manager"
    ADMIN = "admin"


class PermissionCode(str, Enum):
    PROFILE_READ_OWN = "profile.read_own"
    PROFILE_WRITE_OWN = "profile.write_own"
    ORDERS_READ_OWN = "orders.read_own"
    CATALOG_WRITE = "catalog.write"
    ORDERS_READ_ALL = "orders.read_all"
    ORDERS_WRITE = "orders.write"
    CRM_ACCESS = "crm.access"
    USERS_MANAGE = "users.manage"
    ROLES_MANAGE = "roles.manage"
    ADMIN_ACCESS = "admin.access"
    PAYMENTS_MANAGE = "payments.manage"
    PAYOUTS_MANAGE = "payouts.manage"


class OtpPurpose(str, Enum):
    LOGIN = "login"
    EMAIL_CHANGE = "email_change"


class User(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "status = 'deleted' OR email_normalized IS NOT NULL OR telegram_id IS NOT NULL",
            name="user_identifier_present",
        ),
        CheckConstraint(
            "(email IS NULL) = (email_normalized IS NULL)",
            name="user_email_pair_consistent",
        ),
        CheckConstraint(
            "status IN ('active', 'blocked', 'deleted')",
            name="user_status_valid",
        ),
        CheckConstraint(
            "height_cm IS NULL OR height_cm >= 0",
            name="user_height_nonnegative",
        ),
        CheckConstraint(
            "weight_kg IS NULL OR weight_kg >= 0",
            name="user_weight_nonnegative",
        ),
    )

    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    email_normalized: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
        unique=True,
        index=True,
    )
    telegram_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
        index=True,
    )
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=UserStatus.ACTIVE.value,
        server_default=UserStatus.ACTIVE.value,
        index=True,
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    role_links: Mapped[list[UserRole]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserRole.user_id",
    )
    otp_challenges: Mapped[list[OtpChallenge]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    refresh_sessions: Mapped[list[RefreshSession]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="RefreshSession.user_id",
    )


class Role(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    user_links: Mapped[list[UserRole]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )
    permission_links: Mapped[list[RolePermission]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )


class Permission(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    role_links: Mapped[list[RolePermission]] = relationship(
        back_populates="permission",
        cascade="all, delete-orphan",
    )


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assigned_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(
        back_populates="role_links",
        foreign_keys=[user_id],
    )
    role: Mapped[Role] = relationship(back_populates="user_links")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    role: Mapped[Role] = relationship(back_populates="permission_links")
    permission: Mapped[Permission] = relationship(back_populates="role_links")


class OtpChallenge(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "otp_challenges"
    __table_args__ = (
        UniqueConstraint("active_key", name="uq_otp_challenge_active_key"),
        CheckConstraint(
            "purpose IN ('login', 'email_change')",
            name="otp_challenge_purpose_valid",
        ),
        CheckConstraint(
            "length(code_digest) = 64",
            name="otp_challenge_digest_length",
        ),
        CheckConstraint(
            "length(code_salt) = 32",
            name="otp_challenge_salt_length",
        ),
        CheckConstraint(
            "attempts_count >= 0 AND attempts_count <= max_attempts",
            name="otp_challenge_attempts_valid",
        ),
        CheckConstraint(
            "max_attempts > 0 AND max_attempts <= 10",
            name="otp_challenge_max_attempts_valid",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_email: Mapped[str] = mapped_column(String(320), nullable=False)
    target_email_normalized: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        index=True,
    )
    code_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    code_salt: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    attempts_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    active_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    requested_ip_digest: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    user: Mapped[User] = relationship(back_populates="otp_challenges")


class RefreshSession(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "refresh_sessions"
    __table_args__ = (
        CheckConstraint(
            "length(token_digest) = 64",
            name="refresh_session_digest_length",
        ),
        CheckConstraint(
            "generation >= 0",
            name="refresh_session_generation_nonnegative",
        ),
    )

    session_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    family_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    generation: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    replaced_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("refresh_sessions.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ip_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user: Mapped[User] = relationship(
        back_populates="refresh_sessions",
        foreign_keys=[user_id],
    )
    replacement: Mapped[RefreshSession | None] = relationship(
        remote_side="RefreshSession.id",
        foreign_keys=[replaced_by_id],
        post_update=True,
    )


class SecurityAuditEvent(Base, IntegerIdMixin):
    __tablename__ = "security_audit_events"

    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    subject_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    ip_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    details: Mapped[dict[str, object]] = mapped_column(
        SECURITY_DETAILS_TYPE,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


class IdentityMigrationRun(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "identity_migration_runs"
    __table_args__ = (
        CheckConstraint("users_count >= 0", name="identity_run_users_nonnegative"),
        CheckConstraint(
            "length(fingerprint_sha256) = 64",
            name="identity_run_fingerprint_length",
        ),
    )

    fingerprint_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )
    users_count: Mapped[int] = mapped_column(Integer, nullable=False)


SYSTEM_ROLE_PERMISSIONS: dict[RoleName, Sequence[PermissionCode]] = {
    RoleName.CUSTOMER: (
        PermissionCode.PROFILE_READ_OWN,
        PermissionCode.PROFILE_WRITE_OWN,
        PermissionCode.ORDERS_READ_OWN,
    ),
    RoleName.MANAGER: (
        PermissionCode.PROFILE_READ_OWN,
        PermissionCode.PROFILE_WRITE_OWN,
        PermissionCode.ORDERS_READ_OWN,
        PermissionCode.CATALOG_WRITE,
        PermissionCode.ORDERS_READ_ALL,
        PermissionCode.ORDERS_WRITE,
        PermissionCode.CRM_ACCESS,
        PermissionCode.ADMIN_ACCESS,
        PermissionCode.PAYMENTS_MANAGE,
    ),
    RoleName.ADMIN: tuple(PermissionCode),
}
