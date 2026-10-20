"""Existing collections survive introduction and rollback of editor versioning."""

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.modules.catalog.models import Product
from app.modules.identity.models import User
from app.modules.partners.models import PartnerLanding, PartnerLandingProduct, PartnerProfile
from tests.postgres_schema import migrate, seed_historical_landing, seed_historical_product

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


def test_landing_version_migration_preserves_content_and_ordered_products(postgres_url):
    migrate(postgres_url, "upgrade", "head")
    migrate(postgres_url, "downgrade", "20261015_0064")
    owned = {}
    slug = "historical-" + uuid4().hex

    async def action(name):
        engine = create_async_engine(postgres_url)
        try:
            async with engine.begin() as connection:
                if name == "seed":
                    owned["user"] = await connection.scalar(
                        insert(User).values(internal_identity=uuid4().hex).returning(User.id)
                    )
                    owned["partner"] = await connection.scalar(
                        insert(PartnerProfile)
                        .values(
                            user_id=owned["user"],
                            code=uuid4().hex,
                            display_name="Existing owner",
                            commission_bps=1000,
                        )
                        .returning(PartnerProfile.id)
                    )
                    owned["products"] = [
                        await seed_historical_product(connection, title=title, price=100)
                        for title in ("First", "Second")
                    ]
                    owned["landing"] = await seed_historical_landing(
                        connection,
                        partner_id=owned["partner"],
                        slug=slug,
                        description="Keep existing collection",
                    )
                    await connection.execute(
                        text(
                            "UPDATE partner_landings SET content=CAST(:content AS jsonb) WHERE id=:id"
                        ),
                        {"id": owned["landing"], "content": '{"story_title":"Keep story"}'},
                    )
                    await connection.execute(
                        insert(PartnerLandingProduct),
                        [
                            {
                                "landing_id": owned["landing"],
                                "product_id": product,
                                "position": index,
                            }
                            for index, product in enumerate(owned["products"][::-1])
                        ],
                    )
                elif name == "verify":
                    row = (
                        await connection.execute(
                            select(
                                PartnerLanding.version,
                                PartnerLanding.description,
                                PartnerLanding.content,
                            ).where(PartnerLanding.id == owned["landing"])
                        )
                    ).one()
                    assert tuple(row) == (
                        1,
                        "Keep existing collection",
                        {"story_title": "Keep story"},
                    )
                    with pytest.raises(IntegrityError):
                        async with connection.begin_nested():
                            await connection.execute(
                                update(PartnerLanding)
                                .where(PartnerLanding.id == owned["landing"])
                                .values(version=0)
                            )
                    await connection.execute(
                        update(PartnerLanding)
                        .where(PartnerLanding.id == owned["landing"])
                        .values(version=3)
                    )
                elif name == "down":
                    row = (
                        await connection.execute(
                            text(
                                "SELECT slug,description,content FROM partner_landings WHERE id=:id"
                            ),
                            {"id": owned["landing"]},
                        )
                    ).one()
                    assert tuple(row) == (
                        slug,
                        "Keep existing collection",
                        {"story_title": "Keep story"},
                    )
                    assert (
                        await connection.scalars(
                            select(PartnerLandingProduct.product_id)
                            .where(PartnerLandingProduct.landing_id == owned["landing"])
                            .order_by(PartnerLandingProduct.position)
                        )
                    ).all() == owned["products"][::-1]
                    assert (
                        await connection.scalar(
                            text(
                                "SELECT count(*) FROM information_schema.columns WHERE table_name='partner_landings' AND column_name='version'"
                            )
                        )
                        == 0
                    )
                elif name == "cleanup":
                    await connection.execute(
                        delete(PartnerLanding).where(PartnerLanding.id == owned.get("landing"))
                    )
                    await connection.execute(
                        delete(PartnerProfile).where(PartnerProfile.id == owned.get("partner"))
                    )
                    await connection.execute(delete(User).where(User.id == owned.get("user")))
                    await connection.execute(
                        delete(Product).where(Product.id.in_(owned.get("products", [])))
                    )
        finally:
            await engine.dispose()

    try:
        asyncio.run(action("seed"))
        migrate(postgres_url, "upgrade", "head")
        asyncio.run(action("verify"))
        migrate(postgres_url, "downgrade", "20261015_0064")
        asyncio.run(action("down"))
    finally:
        migrate(postgres_url, "upgrade", "head")
        asyncio.run(action("cleanup"))
