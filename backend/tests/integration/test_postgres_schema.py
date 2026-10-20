"""Opt-in checks against a disposable PostgreSQL test database, never production."""

from __future__ import annotations

import asyncio
import base64
import os
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings
from app.core.exceptions import ConfigurationError
from app.db import models as database_models  # noqa: F401
from app.db.base import Base
from app.db.schema import comparison_metadata
from app.factory import create_app
from app.modules.identity.models import User
from app.modules.partners.community_favorite_models import UserCommunityFavorite
from app.modules.partners.models import PartnerLanding, PartnerProfile
from tests.postgres_schema import migrate, seed_historical_landing

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"),
    reason="Requires a disposable PostgreSQL test database",
)


def test_alembic_upgrade_matches_current_models(postgres_url):
    migrate(postgres_url, "upgrade", "head")

    async def differences():
        engine = create_async_engine(postgres_url)
        try:
            async with engine.connect() as connection:
                return await connection.run_sync(
                    lambda sync: compare_metadata(
                        MigrationContext.configure(sync, opts={"compare_type": True}),
                        comparison_metadata(sync.dialect, Base.metadata),
                    )
                )
        finally:
            await engine.dispose()

    changes = asyncio.run(differences())
    assert changes == [], changes


def test_community_favorite_migration_preserves_landings_and_enforces_ownership(postgres_url):
    migrate(postgres_url, "upgrade", "head")
    migrate(postgres_url, "downgrade", "20261014_0061")
    identities = {}

    async def snapshot(action):
        engine = create_async_engine(postgres_url)
        try:
            async with engine.begin() as connection:
                if action == "seed":
                    identities["users"] = [
                        await connection.scalar(
                            insert(User).values(internal_identity=uuid4().hex).returning(User.id)
                        )
                        for _ in range(3)
                    ]
                    identities["partner"] = await connection.scalar(
                        insert(PartnerProfile)
                        .values(
                            user_id=identities["users"][0],
                            code=uuid4().hex,
                            display_name="Migration owner",
                            commission_bps=1000,
                        )
                        .returning(PartnerProfile.id)
                    )
                    identities["landings"] = [
                        await seed_historical_landing(
                            connection,
                            partner_id=identities["partner"],
                            slug=uuid4().hex,
                            description="Preserve this landing",
                        )
                        for _ in range(2)
                    ]
                elif action == "verify":
                    _, buyer, other = identities["users"]
                    first, second = identities["landings"]
                    await connection.execute(
                        insert(UserCommunityFavorite),
                        [
                            {"user_id": buyer, "landing_id": first},
                            {"user_id": other, "landing_id": first},
                            {"user_id": other, "landing_id": second},
                        ],
                    )
                    with pytest.raises(IntegrityError):
                        async with connection.begin_nested():
                            await connection.execute(
                                insert(UserCommunityFavorite).values(
                                    user_id=buyer,
                                    landing_id=first,
                                )
                            )
                    await connection.execute(delete(User).where(User.id == buyer))
                    assert (
                        await connection.scalar(
                            select(func.count())
                            .select_from(UserCommunityFavorite)
                            .where(UserCommunityFavorite.user_id == buyer)
                        )
                        == 0
                    )
                    await connection.execute(
                        delete(PartnerLanding).where(PartnerLanding.id == first)
                    )
                    assert (
                        await connection.execute(
                            select(
                                UserCommunityFavorite.user_id, UserCommunityFavorite.landing_id
                            ).where(UserCommunityFavorite.user_id == other)
                        )
                    ).all() == [(other, second)]
                elif action == "downgraded":
                    assert (
                        await connection.scalar(
                            text("SELECT to_regclass('public.user_community_favorites')")
                        )
                        is None
                    )
                    assert (
                        await connection.scalar(
                            select(PartnerLanding.description).where(
                                PartnerLanding.id == identities["landings"][1]
                            )
                        )
                        == "Preserve this landing"
                    )
                    assert (
                        await connection.scalar(
                            select(PartnerProfile.display_name).where(
                                PartnerProfile.id == identities["partner"]
                            )
                        )
                        == "Migration owner"
                    )
                elif action == "cleanup":
                    await connection.execute(
                        delete(PartnerLanding).where(
                            PartnerLanding.id.in_(identities.get("landings", []))
                        )
                    )
                    await connection.execute(
                        delete(PartnerProfile).where(PartnerProfile.id == identities.get("partner"))
                    )
                    await connection.execute(
                        delete(User).where(User.id.in_(identities.get("users", [])))
                    )
        finally:
            await engine.dispose()

    try:
        asyncio.run(snapshot("seed"))
        migrate(postgres_url, "upgrade", "head")
        asyncio.run(snapshot("verify"))
        migrate(postgres_url, "downgrade", "20261014_0061")
        asyncio.run(snapshot("downgraded"))
    finally:
        migrate(postgres_url, "upgrade", "head")
        asyncio.run(snapshot("cleanup"))


def test_contact_snapshot_migration_preserves_historical_rows_and_rejects_partial_contacts(
    postgres_url,
):
    migrate(postgres_url, "upgrade", "head")
    migrate(postgres_url, "downgrade", "20261014_0060")
    fingerprint = uuid4().hex * 2

    async def snapshot(action):
        engine = create_async_engine(postgres_url)
        try:
            async with engine.begin() as conn:
                if action == "seed":
                    await conn.execute(
                        text(
                            "INSERT INTO orders (email, phone, first_name, items_subtotal, delivery_price, "
                            "total_price, request_fingerprint_sha256) VALUES "
                            "('historical@example.test', '+79990000000', 'Историческое имя', 100, 50, 150, :fingerprint)"
                        ),
                        {"fingerprint": fingerprint},
                    )
                elif action == "verify":
                    columns = (
                        (
                            await conn.execute(
                                text(
                                    "SELECT column_name FROM information_schema.columns WHERE table_schema='public' "
                                    "AND table_name='orders' AND column_name IN ('buyer_name','buyer_phone','recipient_email')"
                                )
                            )
                        )
                        .scalars()
                        .all()
                    )
                    assert set(columns) == {"buyer_name", "buyer_phone", "recipient_email"}
                    row = (
                        await conn.execute(
                            text(
                                "SELECT email, phone, first_name, buyer_name, buyer_phone, recipient_email FROM orders "
                                "WHERE request_fingerprint_sha256=:fingerprint"
                            ),
                            {"fingerprint": fingerprint},
                        )
                    ).one()
                    assert tuple(row) == (
                        "historical@example.test",
                        "+79990000000",
                        "Историческое имя",
                        None,
                        None,
                        None,
                    )
                    with pytest.raises(IntegrityError):
                        async with conn.begin_nested():
                            await conn.execute(
                                text(
                                    "UPDATE orders SET buyer_name='Partial' WHERE request_fingerprint_sha256=:fingerprint"
                                ),
                                {"fingerprint": fingerprint},
                            )
                    await conn.execute(
                        text(
                            "UPDATE orders SET buyer_name='Buyer', buyer_phone='+79991112233', "
                            "recipient_email='recipient@example.test' WHERE request_fingerprint_sha256=:fingerprint"
                        ),
                        {"fingerprint": fingerprint},
                    )
                elif action == "downgraded":
                    row = (
                        await conn.execute(
                            text(
                                "SELECT email, phone, first_name, total_price FROM orders WHERE request_fingerprint_sha256=:fingerprint"
                            ),
                            {"fingerprint": fingerprint},
                        )
                    ).one()
                    assert tuple(row[:3]) == (
                        "historical@example.test",
                        "+79990000000",
                        "Историческое имя",
                    )
                    assert row.total_price == 150
                elif action == "cleanup":
                    await conn.execute(
                        text("DELETE FROM orders WHERE request_fingerprint_sha256=:fingerprint"),
                        {"fingerprint": fingerprint},
                    )
        finally:
            await engine.dispose()

    asyncio.run(snapshot("seed"))
    try:
        migrate(postgres_url, "upgrade", "head")
        asyncio.run(snapshot("verify"))
        migrate(postgres_url, "downgrade", "20261014_0060")
        asyncio.run(snapshot("downgraded"))
    finally:
        migrate(postgres_url, "upgrade", "head")
        asyncio.run(snapshot("cleanup"))


def test_duplicate_index_migration_preserves_rows_and_unique_constraints(postgres_url):
    migrate(postgres_url, "upgrade", "head")
    migrate(postgres_url, "downgrade", "20260929_0055")
    email = f"migration-{uuid4().hex}@example.test"

    async def snapshot(*, seed=False, verify=False, cleanup=False):
        engine = create_async_engine(postgres_url)
        try:
            async with engine.begin() as connection:
                if seed:
                    await connection.execute(
                        text("INSERT INTO users (email, email_normalized) VALUES (:email, :email)"),
                        {"email": email},
                    )
                if verify:
                    assert (
                        await connection.scalar(
                            text("SELECT email FROM users WHERE email_normalized = :email"),
                            {"email": email},
                        )
                        == email
                    )
                    with pytest.raises(IntegrityError):
                        async with connection.begin_nested():
                            await connection.execute(
                                text(
                                    "INSERT INTO users (email, email_normalized) "
                                    "VALUES (:email, :email)"
                                ),
                                {"email": email},
                            )
                constraints = (
                    await connection.execute(
                        text(
                            "SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid) "
                            "FROM pg_constraint WHERE connamespace = 'public'::regnamespace "
                            "ORDER BY conrelid::regclass::text, conname"
                        )
                    )
                ).all()
                indexes = (
                    (
                        await connection.execute(
                            text(
                                "SELECT indexrelid::regclass::text FROM pg_index "
                                "WHERE NOT indisunique AND indrelid IN "
                                "(SELECT oid FROM pg_class WHERE relnamespace = 'public'::regnamespace)"
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                if cleanup:
                    await connection.execute(
                        text("DELETE FROM users WHERE email_normalized = :email"), {"email": email}
                    )
                return constraints, set(indexes)
        finally:
            await engine.dispose()

    original_constraints, original_indexes = asyncio.run(snapshot(seed=True))
    try:
        migrate(postgres_url, "upgrade", "20261013_0056")
        constraints, indexes = asyncio.run(snapshot(verify=True))
        assert constraints == original_constraints
        assert indexes < original_indexes
        assert len(original_indexes - indexes) == 24

        migrate(postgres_url, "downgrade", "20260929_0055")
        assert asyncio.run(snapshot(verify=True)) == (original_constraints, original_indexes)
    finally:
        migrate(postgres_url, "upgrade", "head")
        asyncio.run(snapshot(cleanup=True))


def test_runtime_rejects_outdated_postgres_schema(postgres_url):
    migrate(postgres_url, "upgrade", "head")
    migrate(postgres_url, "downgrade", "20260929_0055")
    settings = Settings(
        _env_file=None, app_env="test", database_enabled=True, database_url=postgres_url
    )
    try:
        with (
            pytest.raises(ConfigurationError, match="schema"),
            TestClient(create_app(settings=settings)),
        ):
            pass
    finally:
        migrate(postgres_url, "upgrade", "head")


@pytest.mark.parametrize("order_reads_enabled", [True, False])
def test_modern_domains_start_without_legacy_import_records(postgres_url, order_reads_enabled):
    migrate(postgres_url, "upgrade", "head")
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_enabled=True,
        database_url=postgres_url,
        minio_enabled=True,
        minio_access_key="test-access",
        minio_secret_key="test-secret",
        minio_public_base_url="http://storage.test",
        catalog_reads_enabled=True,
        catalog_writes_enabled=True,
        carts_v2_enabled=True,
        identity_api_enabled=True,
        order_reads_enabled=order_reads_enabled,
        jwt_secret="j" * 32,
        identity_otp_pepper="p" * 32,
        notification_encryption_key=base64.urlsafe_b64encode(b"n" * 32).decode(),
    )
    with TestClient(create_app(settings=settings)) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/api/products").status_code == 401
        products = client.get("/api/catalog/products")
        assert products.status_code == 200
        assert products.json() == {"items": [], "next_cursor": None}
        assert client.get("/api/auth/me").status_code == 401
        assert client.get("/api/auth/orders").status_code == 401
        assert client.get("/api/orders").status_code == (401 if order_reads_enabled else 404)
        assert client.get("/admin").status_code == 404
