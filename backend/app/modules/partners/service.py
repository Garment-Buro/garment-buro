from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.security import ensure_utc, normalize_email
from app.modules.partners.models import (
    PartnerCommission,
    PartnerCommissionStatus,
    PartnerLanding,
    PartnerLandingStatus,
    PartnerOrderAttribution,
    PartnerPayoutRequest,
    PartnerPayoutStatus,
    PartnerProfile,
    PartnerStatus,
    PartnerVisit,
)
from app.modules.partners.repository import PartnerRepository
from app.modules.partners.schemas import (
    PartnerCreateRequest,
    PartnerDashboardResponse,
    PartnerLandingCreateRequest,
    PartnerProfileResponse,
    PartnerUpdateRequest,
    PublicPartnerLandingResponse,
)
from app.modules.partners.security import (
    InvalidPartnerAttributionTokenError,
    PartnerAttributionSecurity,
)


class PartnerProgramDisabledError(RuntimeError):
    pass


class PartnerNotFoundError(LookupError):
    pass


class PartnerLandingNotFoundError(LookupError):
    pass


class PartnerConflictError(ValueError):
    pass


class PartnerPayoutBalanceError(ValueError):
    pass


class PartnerPayoutStateError(ValueError):
    pass


class PartnerProgramService:
    def __init__(
        self,
        settings: Settings | None = None,
        repository: PartnerRepository | None = None,
        security: PartnerAttributionSecurity | None = None,
        identity_repository: IdentityRepository | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repository = repository or PartnerRepository()
        self.identity_repository = identity_repository or IdentityRepository()
        secret = self.settings.secret_value(self.settings.partner_attribution_secret)
        self.security = security
        if self.security is None and secret:
            self.security = PartnerAttributionSecurity(
                secret,
                lifetime=timedelta(days=self.settings.partner_attribution_days),
            )

    def require_enabled(self) -> None:
        if not self.settings.partner_program_enabled or self.security is None:
            raise PartnerProgramDisabledError("Partner program is disabled")

    async def public_landing(
        self,
        session: AsyncSession,
        *,
        slug: str,
    ) -> PublicPartnerLandingResponse:
        self.require_enabled()
        landing = await self.repository.get_published_landing_by_slug(
            session,
            slug=slug.strip().casefold(),
        )
        if landing is None:
            raise PartnerLandingNotFoundError("Published partner landing was not found")
        return PublicPartnerLandingResponse(
            slug=landing.slug,
            partner_name=landing.partner.display_name,
            title=landing.title,
            eyebrow=landing.eyebrow,
            headline=landing.headline,
            description=landing.description,
            cta_label=landing.cta_label,
            cta_href=landing.cta_href,
            image_url=landing.image_url,
            product_ids=list(landing.product_ids),
        )

    async def register_visit(
        self,
        session: AsyncSession,
        *,
        slug: str,
        visitor_value: str,
        now: datetime | None = None,
    ) -> tuple[str, datetime]:
        self.require_enabled()
        observed_at = ensure_utc(now or datetime.now(timezone.utc))
        landing = await self.repository.get_published_landing_by_slug(
            session,
            slug=slug.strip().casefold(),
        )
        if landing is None:
            raise PartnerLandingNotFoundError("Published partner landing was not found")
        await self.repository.add_visit_once_per_day(
            session,
            PartnerVisit(
                landing_id=landing.id,
                visitor_digest=self.security.digest_visitor(visitor_value),
                visited_on=observed_at.date(),
                created_at=observed_at,
            ),
        )
        token, expires_at = self.security.create_token(
            partner_id=landing.partner_id,
            landing_id=landing.id,
            now=observed_at,
        )
        await session.flush()
        return token, expires_at

    async def attribute_order(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        token: str | None,
        now: datetime | None = None,
    ) -> PartnerOrderAttribution | None:
        if not token or not self.settings.partner_program_enabled or self.security is None:
            return None
        try:
            claims = self.security.decode_token(token)
        except InvalidPartnerAttributionTokenError:
            return None
        existing = await self.repository.get_attribution_by_order(session, order_id=order_id)
        if existing is not None:
            return existing
        landing = await self.repository.get_landing(session, landing_id=claims.landing_id)
        if (
            landing is None
            or landing.partner_id != claims.partner_id
            or landing.status != PartnerLandingStatus.PUBLISHED.value
            or landing.partner.status != PartnerStatus.ACTIVE.value
        ):
            return None
        order = await self.repository.get_order_for_update(session, order_id=order_id)
        if order is None:
            raise PartnerConflictError("Order was not found for partner attribution")
        attribution = PartnerOrderAttribution(
            order_id=order.id,
            partner_id=landing.partner_id,
            landing_id=landing.id,
            commission_bps_snapshot=landing.partner.commission_bps,
            order_amount_snapshot=order.total_price,
            commission_base_snapshot=order.items_subtotal,
            currency=order.currency,
            attributed_at=ensure_utc(now or datetime.now(timezone.utc)),
        )
        await self.repository.add_attribution(session, attribution)
        return attribution

    async def accrue_commission(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        now: datetime | None = None,
    ) -> PartnerCommission | None:
        if not self.settings.partner_program_enabled:
            return None
        existing = await self.repository.get_commission_by_order(session, order_id=order_id)
        if existing is not None:
            return existing
        attribution = await self.repository.get_attribution_by_order(session, order_id=order_id)
        if attribution is None:
            return None
        observed_at = ensure_utc(now or datetime.now(timezone.utc))
        amount = (
            attribution.commission_base_snapshot
            * Decimal(attribution.commission_bps_snapshot)
            / Decimal(10_000)
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        commission = PartnerCommission(
            attribution_id=attribution.id,
            partner_id=attribution.partner_id,
            order_id=order_id,
            amount=amount,
            currency=attribution.currency,
            status=PartnerCommissionStatus.PENDING.value,
            available_at=observed_at + timedelta(days=self.settings.partner_commission_hold_days),
        )
        await self.repository.add_commission(session, commission)
        return commission

    async def get_partner_for_user(
        self,
        session: AsyncSession,
        *,
        user_id: int,
    ) -> PartnerProfile:
        self.require_enabled()
        profile = await self.repository.get_profile_by_user(session, user_id=user_id)
        if profile is None or profile.status == PartnerStatus.SUSPENDED.value:
            raise PartnerNotFoundError("Active partner profile was not found")
        return profile

    async def dashboard(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        now: datetime | None = None,
    ) -> PartnerDashboardResponse:
        profile = await self.get_partner_for_user(session, user_id=user_id)
        totals = await self.repository.dashboard_totals(
            session,
            partner_id=profile.id,
            now=ensure_utc(now or datetime.now(timezone.utc)),
        )
        visits = int(totals["visits"])
        orders = int(totals["orders"])
        conversion = (
            (Decimal(orders) * Decimal(100) / Decimal(visits)).quantize(Decimal("0.01"))
            if visits
            else Decimal("0.00")
        )
        return PartnerDashboardResponse(
            partner=PartnerProfileResponse.model_validate(profile),
            visits=visits,
            orders=orders,
            conversion_percent=conversion,
            earned=Decimal(totals["earned"]),
            available=Decimal(totals["available"]),
            paid=Decimal(totals["paid"]),
        )

    async def create_partner(
        self,
        session: AsyncSession,
        *,
        payload: PartnerCreateRequest,
        actor_user_id: int,
    ) -> PartnerProfile:
        self.require_enabled()
        display_email, normalized_email = normalize_email(payload.email)
        target_user = await self.identity_repository.get_or_create_customer(
            session,
            email=display_email,
            email_normalized=normalized_email,
        )
        if target_user.status != "active":
            raise PartnerConflictError("Partner user is not active")
        if await self.repository.get_profile_by_user(session, user_id=target_user.id):
            raise PartnerConflictError("User already has a partner profile")
        if await self.repository.get_profile_by_code(session, code=payload.code):
            raise PartnerConflictError("Partner code is already used")
        profile = PartnerProfile(
            user_id=target_user.id,
            code=payload.code,
            display_name=payload.display_name,
            commission_bps=payload.commission_bps,
            status=payload.status,
        )
        await self.repository.add_profile(session, profile)
        await self.repository.assign_partner_role(
            session,
            user_id=target_user.id,
            assigned_by_user_id=actor_user_id,
        )
        return profile

    async def update_partner(
        self,
        session: AsyncSession,
        *,
        partner_id: int,
        payload: PartnerUpdateRequest,
    ) -> PartnerProfile:
        self.require_enabled()
        profile = await self.repository.get_profile(
            session,
            partner_id=partner_id,
            for_update=True,
        )
        if profile is None:
            raise PartnerNotFoundError("Partner profile was not found")
        for field in payload.model_fields_set:
            value = getattr(payload, field)
            if value is not None:
                setattr(profile, field, value)
        await session.flush()
        return profile

    async def create_landing(
        self,
        session: AsyncSession,
        *,
        partner_id: int,
        payload: PartnerLandingCreateRequest,
        now: datetime | None = None,
    ) -> PartnerLanding:
        self.require_enabled()
        profile = await self.repository.get_profile(session, partner_id=partner_id)
        if profile is None:
            raise PartnerNotFoundError("Partner profile was not found")
        if await self.repository.get_landing_by_slug(session, slug=payload.slug):
            raise PartnerConflictError("Landing slug is already used")
        published_at = (
            ensure_utc(now or datetime.now(timezone.utc))
            if payload.status == PartnerLandingStatus.PUBLISHED.value
            else None
        )
        landing = PartnerLanding(
            partner_id=partner_id,
            **payload.model_dump(),
            published_at=published_at,
        )
        await self.repository.add_landing(session, landing)
        return landing

    async def request_payout(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        amount: Decimal,
        now: datetime | None = None,
    ) -> PartnerPayoutRequest:
        self.require_enabled()
        profile = await self.repository.get_profile_by_user(
            session,
            user_id=user_id,
            for_update=True,
        )
        if profile is None or profile.status != PartnerStatus.ACTIVE.value:
            raise PartnerNotFoundError("Active partner profile was not found")
        normalized_amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        totals = await self.repository.dashboard_totals(
            session,
            partner_id=profile.id,
            now=ensure_utc(now or datetime.now(timezone.utc)),
        )
        if normalized_amount <= 0 or normalized_amount > Decimal(totals["available"]):
            raise PartnerPayoutBalanceError("Payout amount exceeds available balance")
        payout = PartnerPayoutRequest(
            partner_id=profile.id,
            amount=normalized_amount,
            currency="RUB",
            status=PartnerPayoutStatus.REQUESTED.value,
        )
        await self.repository.add_payout(session, payout)
        return payout

    async def review_payout(
        self,
        session: AsyncSession,
        *,
        payout_id: int,
        status: str,
        note: str | None,
        actor_user_id: int,
        now: datetime | None = None,
    ) -> PartnerPayoutRequest:
        self.require_enabled()
        payout = await self.repository.get_payout_for_update(session, payout_id=payout_id)
        if payout is None:
            raise PartnerNotFoundError("Payout request was not found")
        allowed = {
            PartnerPayoutStatus.REQUESTED.value: {
                PartnerPayoutStatus.APPROVED.value,
                PartnerPayoutStatus.REJECTED.value,
                PartnerPayoutStatus.CANCELED.value,
            },
            PartnerPayoutStatus.APPROVED.value: {
                PartnerPayoutStatus.PAID.value,
                PartnerPayoutStatus.REJECTED.value,
                PartnerPayoutStatus.CANCELED.value,
            },
        }
        if status not in allowed.get(payout.status, set()):
            raise PartnerPayoutStateError("Payout status transition is not allowed")
        observed_at = ensure_utc(now or datetime.now(timezone.utc))
        payout.status = status
        payout.note = note
        payout.reviewed_by_user_id = actor_user_id
        payout.reviewed_at = observed_at
        payout.paid_at = observed_at if status == PartnerPayoutStatus.PAID.value else None
        await session.flush()
        return payout
