from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
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

PARTNER_PRODUCT_IDS_TYPE = JSON().with_variant(JSONB, "postgresql")
PARTNER_LANDING_CONTENT_TYPE = JSON().with_variant(JSONB, "postgresql")


class PartnerStatus(str, Enum):
    INVITED = "invited"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class PartnerLandingStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class PartnerCommissionStatus(str, Enum):
    PENDING = "pending"
    CANCELED = "canceled"


class PartnerPayoutStatus(str, Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"
    CANCELED = "canceled"


class PartnerProfile(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "partner_profiles"
    __table_args__ = (
        CheckConstraint(
            "status IN ('invited', 'active', 'suspended')",
            name="partner_profile_status_valid",
        ),
        CheckConstraint(
            "commission_bps >= 0 AND commission_bps <= 10000",
            name="partner_profile_commission_bps_valid",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=PartnerStatus.INVITED.value,
        server_default=PartnerStatus.INVITED.value,
        index=True,
    )
    commission_bps: Mapped[int] = mapped_column(Integer, nullable=False)

    landings: Mapped[list[PartnerLanding]] = relationship(back_populates="partner")
    attributions: Mapped[list[PartnerOrderAttribution]] = relationship(back_populates="partner")
    payouts: Mapped[list[PartnerPayoutRequest]] = relationship(back_populates="partner")
    requisites: Mapped[PartnerRequisites | None] = relationship(
        back_populates="partner",
        uselist=False,
    )


class PartnerLanding(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "partner_landings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="partner_landing_status_valid",
        ),
    )

    partner_id: Mapped[int] = mapped_column(
        ForeignKey("partner_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    slug: Mapped[str] = mapped_column(String(96), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    eyebrow: Mapped[str | None] = mapped_column(String(120), nullable=True)
    headline: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    cta_label: Mapped[str] = mapped_column(String(80), nullable=False)
    cta_href: Mapped[str] = mapped_column(String(2048), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    template_key: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="light-running",
        server_default="light-running",
    )
    content: Mapped[dict[str, object]] = mapped_column(
        PARTNER_LANDING_CONTENT_TYPE,
        nullable=False,
        default=dict,
    )
    product_ids: Mapped[list[int]] = mapped_column(
        PARTNER_PRODUCT_IDS_TYPE,
        nullable=False,
        default=list,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=PartnerLandingStatus.DRAFT.value,
        server_default=PartnerLandingStatus.DRAFT.value,
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    partner: Mapped[PartnerProfile] = relationship(back_populates="landings")
    visits: Mapped[list[PartnerVisit]] = relationship(back_populates="landing")
    attributions: Mapped[list[PartnerOrderAttribution]] = relationship(back_populates="landing")


class PartnerVisit(Base, IntegerIdMixin):
    __tablename__ = "partner_visits"
    __table_args__ = (
        UniqueConstraint(
            "landing_id",
            "visitor_digest",
            "visited_on",
            name="uq_partner_visit_daily_visitor",
        ),
        CheckConstraint(
            "length(visitor_digest) = 64",
            name="partner_visit_digest_length",
        ),
        Index("ix_partner_visits_landing_created", "landing_id", "created_at"),
    )

    landing_id: Mapped[int] = mapped_column(
        ForeignKey("partner_landings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visitor_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    visited_on: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    landing: Mapped[PartnerLanding] = relationship(back_populates="visits")


class PartnerOrderAttribution(Base, IntegerIdMixin):
    __tablename__ = "partner_order_attributions"
    __table_args__ = (
        CheckConstraint(
            "commission_bps_snapshot >= 0 AND commission_bps_snapshot <= 10000",
            name="partner_attribution_commission_bps_valid",
        ),
        CheckConstraint(
            "order_amount_snapshot >= 0",
            name="partner_attribution_order_amount_nonnegative",
        ),
        CheckConstraint(
            "commission_base_snapshot >= 0",
            name="partner_attribution_commission_base_nonnegative",
        ),
        CheckConstraint("currency = 'RUB'", name="partner_attribution_currency_rub"),
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    partner_id: Mapped[int] = mapped_column(
        ForeignKey("partner_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    landing_id: Mapped[int] = mapped_column(
        ForeignKey("partner_landings.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    commission_bps_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    order_amount_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    commission_base_snapshot: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="RUB",
        server_default="RUB",
    )
    attributed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    partner: Mapped[PartnerProfile] = relationship(back_populates="attributions")
    landing: Mapped[PartnerLanding] = relationship(back_populates="attributions")
    commission: Mapped[PartnerCommission | None] = relationship(
        back_populates="attribution",
        uselist=False,
    )


class PartnerCommission(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "partner_commissions"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="partner_commission_amount_nonnegative"),
        CheckConstraint("currency = 'RUB'", name="partner_commission_currency_rub"),
        CheckConstraint(
            "status IN ('pending', 'canceled')",
            name="partner_commission_status_valid",
        ),
    )

    attribution_id: Mapped[int] = mapped_column(
        ForeignKey("partner_order_attributions.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    partner_id: Mapped[int] = mapped_column(
        ForeignKey("partner_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="RUB",
        server_default="RUB",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=PartnerCommissionStatus.PENDING.value,
        server_default=PartnerCommissionStatus.PENDING.value,
        index=True,
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    canceled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancel_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)

    attribution: Mapped[PartnerOrderAttribution] = relationship(back_populates="commission")


class PartnerPayoutRequest(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "partner_payout_requests"
    __table_args__ = (
        CheckConstraint("amount > 0", name="partner_payout_amount_positive"),
        CheckConstraint("currency = 'RUB'", name="partner_payout_currency_rub"),
        CheckConstraint(
            "status IN ('requested', 'approved', 'paid', 'rejected', 'canceled')",
            name="partner_payout_status_valid",
        ),
    )

    partner_id: Mapped[int] = mapped_column(
        ForeignKey("partner_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="RUB",
        server_default="RUB",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=PartnerPayoutStatus.REQUESTED.value,
        server_default=PartnerPayoutStatus.REQUESTED.value,
        index=True,
    )
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    partner: Mapped[PartnerProfile] = relationship(back_populates="payouts")


class PartnerRequisites(Base, IntegerIdMixin, TimestampMixin):
    __tablename__ = "partner_requisites"
    __table_args__ = (
        CheckConstraint("key_version > 0", name="partner_requisites_key_version_positive"),
        CheckConstraint(
            "schema_version > 0",
            name="partner_requisites_schema_version_positive",
        ),
        CheckConstraint(
            "length(payload_sha256) = 64",
            name="partner_requisites_payload_sha256_length",
        ),
    )

    partner_id: Mapped[int] = mapped_column(
        ForeignKey("partner_profiles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    tag: Mapped[str] = mapped_column(String(64), nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    partner: Mapped[PartnerProfile] = relationship(back_populates="requisites")
