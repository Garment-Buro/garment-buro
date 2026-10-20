from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import event, insert

from app.modules.catalog.admin_schemas import CatalogAdminQuery
from app.modules.catalog.models import Product, ProductVariant
from app.modules.identity.models import User
from app.modules.partners.admin_directory_schemas import AdminLandingQuery
from app.modules.partners.admin_directory_service import (
    AdminLandingService,
    InvalidAdminLandingCursor,
)
from app.modules.partners.models import PartnerLanding, PartnerLandingProduct, PartnerProfile
from tests.integration.test_catalog_admin_postgres import catalog, reader

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


def test_admin_landing_pages_and_product_previews_are_bounded_and_skip_orm_collections(
    postgres_url,
):
    async def scenario():
        async with catalog(postgres_url) as (database, engine, _):
            async with database.session() as session:
                owner = User(internal_identity=uuid4().hex)
                product = Product(title="Large product", price=80, stock_quantity=7)
                other = Product(title="No membership", price=80)
                session.add_all([owner, product, other])
                await session.flush()
                partner = PartnerProfile(
                    user_id=owner.id, code=uuid4().hex, display_name="ВЛАДЕЛЕЦ", commission_bps=1000
                )
                session.add(partner)
                await session.flush()
                await session.execute(
                    insert(ProductVariant),
                    [
                        {
                            "product_id": product.id,
                            "size": str(i),
                            "sku": None if i == 0 else "" if i == 1 else f"SKU-{i}",
                        }
                        for i in range(1000)
                    ],
                )
                landings = [
                    PartnerLanding(
                        partner_id=partner.id,
                        title=f"ЛЕНДИНГ {i:03d}" + ("_%\\" if i == 129 else ""),
                        slug=f"directory-{i}",
                        headline="Headline",
                        description="Description",
                        cta_label="Open",
                        cta_href="/",
                        content={"large": "x" * 10000},
                        status=["draft", "published", "archived"][i % 3],
                    )
                    for i in range(130)
                ]
                session.add_all(landings)
                await session.flush()
                session.add_all(
                    [
                        PartnerLandingProduct(landing_id=row.id, product_id=product.id, position=0)
                        for row in landings
                    ]
                )
                await session.commit()
                pid, other_id = product.id, other.id
                expected = sorted([row.id for row in landings], reverse=True)
            statements = []

            def observe(_conn, _cursor, statement, _params, _context, _many):
                statements.append(statement)

            event.listen(engine.sync_engine, "before_cursor_execute", observe)
            try:
                async with database.session() as session:
                    cursor, ids = None, []
                    while True:
                        statements.clear()
                        page = await AdminLandingService.list_page(
                            session, AdminLandingQuery(limit=24, cursor=cursor)
                        )
                        assert len(statements) == 1 and "content" not in statements[0]
                        assert len(page.items) <= 24
                        assert all(item.product_count == 1 for item in page.items)
                        assert all("product_ids" not in item.model_dump() for item in page.items)
                        ids.extend(row.id for row in page.items)
                        cursor = page.next_cursor
                        if cursor is None:
                            break
                    assert ids == expected
                    assert not any(
                        isinstance(row, (PartnerLanding, PartnerLandingProduct))
                        for row in session.identity_map.values()
                    )
                    for text in ["лендинг 129", "_%\\"]:
                        page = await AdminLandingService.list_page(
                            session, AdminLandingQuery(query=text)
                        )
                        assert [row.id for row in page.items] == [expected[0]]
                    page = await AdminLandingService.list_page(
                        session, AdminLandingQuery(query="владелец", status="archived")
                    )
                    assert page.items and all(row.status == "archived" for row in page.items)
                    first = await AdminLandingService.list_page(session, AdminLandingQuery(limit=1))
                    for query in [
                        AdminLandingQuery(cursor="invalid!"),
                        AdminLandingQuery(cursor=first.next_cursor, query="changed"),
                        AdminLandingQuery(cursor=first.next_cursor, status="draft"),
                    ]:
                        with pytest.raises(InvalidAdminLandingCursor):
                            await AdminLandingService.list_page(session, query)
                    changed_limit = await AdminLandingService.list_page(
                        session, AdminLandingQuery(limit=2, cursor=first.next_cursor)
                    )
                    assert [row.id for row in changed_limit.items] == expected[1:3]
                async with database.session() as session:
                    statements.clear()
                    page = await reader().list_page(
                        session, CatalogAdminQuery(limit=24), include_communities=True
                    )
                    assert len(statements) <= 4
                    assert not any(
                        isinstance(row, (ProductVariant, PartnerLanding, PartnerLandingProduct))
                        for row in session.identity_map.values()
                    )
                    item = next(row for row in page.items if row.id == pid)
                    assert (
                        item.variant_count == 1000
                        and item.sku == "SKU-2"
                        and item.stock_quantity == 7
                    )
                    assert (
                        item.community_count == 130
                        and [row.id for row in item.communities] == expected[:3]
                    )
                    assert (
                        len(item.model_dump_json()) < 2000 and "variants" not in item.model_dump()
                    )
                    other = next(row for row in page.items if row.id == other_id)
                    assert (
                        other.community_count == 0
                        and other.communities == []
                        and other.variant_count == 0
                    )
                async with database.session() as session:
                    statements.clear()
                    page = await reader().list_page(session, CatalogAdminQuery(limit=24))
                    assert all(
                        item.community_count is None and item.communities == []
                        for item in page.items
                    )
                    counts = await reader().counts(session)
                    assert counts.communities is None
                    assert not any(
                        "partner_landings" in statement or "partner_landing_products" in statement
                        for statement in statements
                    )
            finally:
                event.remove(engine.sync_engine, "before_cursor_execute", observe)

    asyncio.run(scenario())
