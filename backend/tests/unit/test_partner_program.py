from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.identity.models import RoleName, User, UserRole
from app.modules.identity.repository import IdentityRepository
from app.modules.orders.models import Order
from app.modules.partners.models import PartnerVisit
from app.modules.partners.schemas import (
    PartnerCreateRequest,
    PartnerLandingCreateRequest,
)
from app.modules.partners.security import (
    InvalidPartnerAttributionTokenError,
    PartnerAttributionSecurity,
)
from app.modules.partners.service import PartnerPayoutBalanceError, PartnerProgramService

SECRET = "partner-attribution-secret-that-is-long-enough"


def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'partners.db'}",
        identity_api_enabled=True,
        identity_migration_fingerprint="1" * 64,
        jwt_secret="identity-jwt-secret-that-is-long-enough",
        identity_otp_pepper="identity-otp-pepper-that-is-long-enough",
        notification_encryption_key=(
            "bm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm5ubm4="
        ),
        partner_program_enabled=True,
        partner_attribution_secret=SECRET,
        partner_commission_hold_days=0,
    )


def test_partner_attribution_security_rejects_tampering() -> None:
    now = datetime(2026, 9, 4, tzinfo=timezone.utc)
    security = PartnerAttributionSecurity(SECRET, lifetime=timedelta(days=30))
    token, _ = security.create_token(partner_id=7, landing_id=11, now=now)

    claims = security.decode_token(token)
    assert claims.partner_id == 7
    assert claims.landing_id == 11
    assert len(security.digest_visitor("browser-id")) == 64
    with pytest.raises(InvalidPartnerAttributionTokenError):
        security.decode_token(f"{token}broken")


def test_partner_lifecycle_tracks_paid_order_and_reserves_payout(tmp_path) -> None:
    async def scenario() -> None:
        runtime = settings(tmp_path)
        database = DatabaseManager(runtime)
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        service = PartnerProgramService(runtime)
        observed_at = datetime.now(timezone.utc)
        async with database.session() as session:
            await IdentityRepository().ensure_system_authorization(session)
            admin = User(email="admin@example.test", email_normalized="admin@example.test")
            session.add(admin)
            await session.flush()
            admin_role = await IdentityRepository().get_role(session, RoleName.ADMIN)
            assert admin_role is not None
            session.add(UserRole(user_id=admin.id, role_id=admin_role.id))
            await session.flush()

            partner = await service.create_partner(
                session,
                payload=PartnerCreateRequest(
                    email="partner@example.test",
                    code="blogger_one",
                    display_name="Блогер Один",
                    commission_bps=1_500,
                    status="active",
                ),
                actor_user_id=admin.id,
            )
            partner_user = await IdentityRepository().get_user_by_email(
                session,
                "partner@example.test",
            )
            assert partner_user is not None
            landing = await service.create_landing(
                session,
                partner_id=partner.id,
                payload=PartnerLandingCreateRequest(
                    slug="blogger-one",
                    title="Подборка GARMENT BURO",
                    eyebrow="Выбор автора",
                    headline="Вещи, которые можно сделать своими",
                    description="Персональная подборка изделий.",
                    cta_label="Смотреть изделия",
                    cta_href="/",
                    product_ids=[1, 2],
                    status="published",
                ),
                now=observed_at,
            )
            token, _ = await service.register_visit(
                session,
                slug=landing.slug,
                visitor_value="same-browser",
                now=observed_at,
            )
            await service.register_visit(
                session,
                slug=landing.slug,
                visitor_value="same-browser",
                now=observed_at,
            )
            order = Order(
                user_id=None,
                email="customer@example.test",
                email_normalized="customer@example.test",
                phone="+79990000000",
                first_name="Клиент",
                delivery_city="Москва",
                delivery_method="courier",
                delivery_address="Адрес",
                payment_method="card",
                items_subtotal=Decimal("1000.00"),
                delivery_price=Decimal("200.00"),
                total_price=Decimal("1200.00"),
                currency="RUB",
                request_fingerprint_sha256="a" * 64,
            )
            session.add(order)
            await session.flush()

            claims = service.security.decode_token(token)
            stored_landing = await service.repository.get_landing(
                session,
                landing_id=claims.landing_id,
            )
            assert stored_landing is not None
            assert stored_landing.partner.status == "active"
            attribution = await service.attribute_order(
                session,
                order_id=order.id,
                token=token,
                now=observed_at,
            )
            assert attribution is not None
            commission = await service.accrue_commission(
                session,
                order_id=order.id,
                now=observed_at,
            )
            assert commission is not None
            assert commission.amount == Decimal("150.00")

            dashboard = await service.dashboard(
                session,
                user_id=partner_user.id,
                now=observed_at,
            )
            assert dashboard.visits == 1
            assert dashboard.orders == 1
            assert dashboard.conversion_percent == Decimal("100.00")
            assert dashboard.available == Decimal("150.00")

            payout = await service.request_payout(
                session,
                user_id=partner_user.id,
                amount=Decimal("100.00"),
                now=observed_at,
            )
            assert payout.amount == Decimal("100.00")
            with pytest.raises(PartnerPayoutBalanceError):
                await service.request_payout(
                    session,
                    user_id=partner_user.id,
                    amount=Decimal("51.00"),
                    now=observed_at,
                )

            visit_count = await session.scalar(select(func.count()).select_from(PartnerVisit))
            assert visit_count == 1
            await session.commit()

        await database.shutdown()

    asyncio.run(scenario())
