from __future__ import annotations

import base64
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.core.config import Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.catalog.models import Product, ProductCategory
from app.modules.identity.factory import build_identity_service
from app.modules.identity.repository import IdentityRepository


def favorite_settings(database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_enabled=True,
        database_url=database_url,
        identity_api_enabled=True,
        # Isolate account/catalog scenarios from inherited provider configuration;
        # these tests must never start external workers.
        cdek_client_id=None,
        cdek_client_secret=None,
        payment_reconciliation_enabled=False,
        minio_enabled=False,
        jwt_secret="j" * 32,
        identity_otp_pepper="p" * 32,
        notification_encryption_key=base64.urlsafe_b64encode(b"n" * 32).decode(),
    )


async def seed_favorites(settings: Settings, *, create_schema: bool = True):
    database = DatabaseManager(settings)
    await database.startup()
    try:
        if create_schema:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        service = build_identity_service(settings)
        async with database.session() as session:
            await IdentityRepository().ensure_system_authorization(session)
            suffix = uuid4().hex
            category = ProductCategory(
                slug=f"unpublished-{suffix}", name="Unpublished", is_active=False
            )
            session.add(category)
            await session.flush()
            products = [
                Product(title="First", price=Decimal("1000")),
                Product(title="Second", price=Decimal("2000")),
                Product(title="Third", price=Decimal("3000")),
                Product(title="Inactive", price=Decimal("4000"), is_active=False),
                Product(title="Demo", price=Decimal("5000"), is_demo=True),
                Product(title="Hidden category", price=Decimal("6000"), category_id=category.id),
            ]
            session.add_all(products)
            tokens = []
            users = []
            for email in (f"one-{suffix}@example.test", f"two-{suffix}@example.test"):
                now = datetime.now(timezone.utc)
                issued = await service.request_login_otp(session, email=email, now=now)
                auth = await service.verify_login_otp(
                    session, email=email, code=issued.code, now=now
                )
                tokens.append({"Authorization": f"Bearer {auth.access_token}"})
                users.append(auth.user.id)
            await session.commit()
            return [product.id for product in products], tokens, users
    finally:
        await database.shutdown()
