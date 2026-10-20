"""Global filter choices must not expand the same palette for every product."""

import asyncio
import json
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.modules.catalog.storefront_repository import StorefrontRepository
from tests.integration.test_crm_directory_plans import RecordingSession, plan_nodes
from tests.integration.test_storefront_page_plans import explain
from tests.postgres_schema import migrate

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


class OptionsSession(RecordingSession):
    async def scalars(self, statement):
        self.statements.append(statement)
        return await self.connection.scalars(statement)


@pytest.mark.parametrize("unique_palettes", [False, True], ids=["shared", "unique"])
def test_storefront_options_expand_distinct_public_palettes(
    postgres_url, tmp_path, unique_palettes
):
    migrate(postgres_url, "upgrade", "head")

    async def scenario():
        engine = create_async_engine(postgres_url)
        plans, failures = {}, []
        count = 2048 if unique_palettes else 20000
        palettes = count if unique_palettes else 8
        try:
            # Rollback fixtures leave dead index entries. Keep this measurement
            # independent of when autovacuum happens to clean previous cases.
            async with engine.connect() as maintenance:
                maintenance = await maintenance.execution_options(isolation_level="AUTOCOMMIT")
                await maintenance.execute(
                    text("VACUUM (ANALYZE, INDEX_CLEANUP ON) products, product_categories")
                )
            async with engine.connect() as connection:
                transaction = await connection.begin()
                try:
                    category = await connection.scalar(
                        text(
                            "INSERT INTO product_categories(slug,name) "
                            "VALUES ('options-plan-visible','Visible') RETURNING id"
                        )
                    )
                    hidden = await connection.scalar(
                        text(
                            "INSERT INTO product_categories(slug,name,is_active) "
                            "VALUES ('options-plan-hidden','Hidden',false) RETURNING id"
                        )
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO product_categories(slug,name) "
                            "VALUES ('options-plan-empty','Empty')"
                        )
                    )
                    # Four colors per palette. Only public products may contribute.
                    await connection.execute(
                        text(
                            "INSERT INTO products(title,price,sizes,colors,category_id) "
                            "SELECT 'Options '||i,100,'[]', "
                            "jsonb_build_array('common','color-'||(i % :palettes),"
                            "'dup','dup'), CASE WHEN i % 2=0 THEN CAST(:category AS integer) ELSE NULL END "
                            "FROM generate_series(1,:count) i"
                        ),
                        {"count": count, "palettes": palettes, "category": category},
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO products(title,price,sizes,colors,category_id,is_active,is_demo) "
                            "SELECT 'Unavailable '||i,100,'[]','[\"private-color\"]', "
                            "CASE WHEN i % 3=0 THEN CAST(:hidden AS integer) "
                            "ELSE CAST(:category AS integer) END, "
                            "i % 3!=1,i % 3=2 FROM generate_series(1,6000) i"
                        ),
                        {"hidden": hidden, "category": category},
                    )
                    await connection.execute(text("ANALYZE products"))
                    await connection.execute(text("ANALYZE product_categories"))
                    recording = OptionsSession(connection)
                    categories, colors = await StorefrontRepository().options(recording)
                    assert [row["id"] for row in categories] == [category]
                    assert colors == sorted(
                        ["common", "dup", *["color-" + str(i) for i in range(palettes)]]
                    )
                    assert len(recording.statements) == 2
                    for mode in ("custom", "generic"):
                        for name, statement in zip(
                            ("categories", "colors"), recording.statements, strict=True
                        ):
                            plan = await explain(connection, statement, mode)
                            plans[name + ":" + mode] = plan
                            if name == "colors":
                                nodes = list(plan_nodes(plan["Plan"]))
                                # Count rows flowing out of the lateral expansion,
                                # even if PostgreSQL memoizes the function itself.
                                expansions = [
                                    node
                                    for node in nodes
                                    if node["Node Type"] == "Nested Loop"
                                    and any(
                                        child.get("Alias") == "option_colors"
                                        for child in plan_nodes(node)
                                    )
                                ]
                                assert expansions, "The measured color expansion is missing"
                                fanout = max(
                                    node["Actual Rows"] * node["Actual Loops"]
                                    for node in expansions
                                )
                                if fanout > palettes * 4:
                                    failures.append({"mode": mode, "expandedRows": fanout})
                finally:
                    await transaction.rollback()
        finally:
            await engine.dispose()
            (tmp_path / "storefront-options-plans.json").write_text(json.dumps(plans, indent=2))
        assert not failures, failures

    asyncio.run(scenario())
