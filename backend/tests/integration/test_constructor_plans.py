"""Constructor media reads belong to one product, including its SKU images."""

import asyncio
import json
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.modules.catalog.constructor_repository import ConstructorRepository
from tests.integration.test_crm_directory_plans import RecordingSession, plan_nodes
from tests.integration.test_storefront_page_plans import explain
from tests.postgres_schema import migrate

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


def test_constructor_images_do_not_scan_other_products_or_the_media_registry(
    postgres_url, tmp_path
):
    migrate(postgres_url, "upgrade", "head")

    async def scenario():
        engine = create_async_engine(postgres_url)
        plans = {}
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                try:
                    products = list(
                        (
                            await connection.execute(
                                text(
                                    "INSERT INTO products(title,price,sizes,colors) "
                                    "SELECT 'Constructor plan '||i,1,'[]','[]' "
                                    "FROM generate_series(1,200) i RETURNING id"
                                )
                            )
                        ).scalars()
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO media_objects(bucket_name,object_key,content_type,size_bytes,"
                            "checksum_sha256,status,is_public) SELECT 'catalog','constructor-plan-'||i,"
                            "'image/webp',10,repeat('a',64),'ready',true "
                            "FROM generate_series(1,20000) i"
                        )
                    )
                    media = await connection.scalar(text("SELECT max(id) FROM media_objects"))
                    for product in products:
                        await connection.execute(
                            text(
                                "INSERT INTO product_media(product_id,media_object_id,role,sort_order) "
                                "SELECT :product,:media,'gallery_images',i FROM generate_series(0,99) i"
                            ),
                            {"product": product, "media": media},
                        )
                        await connection.execute(
                            text(
                                "WITH variants AS (INSERT INTO product_variants(product_id,size,color) "
                                "SELECT :product,'M','Color '||i FROM generate_series(1,100) i RETURNING id) "
                                "INSERT INTO product_variant_media(product_variant_id,media_object_id,role,sort_order) "
                                "SELECT variants.id,:media,'images',i FROM variants,generate_series(0,3) i"
                            ),
                            {"product": product, "media": media},
                        )
                    for table in (
                        "products",
                        "product_variants",
                        "product_media",
                        "product_variant_media",
                        "media_objects",
                    ):
                        await connection.execute(text("ANALYZE " + table))
                    for variants in (False, True):
                        recording = RecordingSession(connection)
                        rows = list(
                            await ConstructorRepository().images(
                                recording, products[-1], variants=variants
                            )
                        )
                        expected = 400 if variants else 100
                        assert len(rows) == expected
                        assert len(recording.statements) == 1
                        for mode in ("custom", "generic"):
                            name = f"{'variants' if variants else 'product'}:{mode}"
                            plan = await explain(connection, recording.statements[0], mode)
                            plans[name] = plan
                            (tmp_path / "constructor-plans.json").write_text(
                                json.dumps(plans, indent=2)
                            )
                            for table, maximum in (
                                ("product_variants", 100),
                                ("product_media", 100),
                                ("product_variant_media", 400),
                                ("media_objects", expected),
                            ):
                                scans = [
                                    node
                                    for node in plan_nodes(plan["Plan"])
                                    if node.get("Relation Name") == table
                                ]
                                assert not any(node["Node Type"] == "Seq Scan" for node in scans), (
                                    name
                                )
                                visited = sum(
                                    (node["Actual Rows"] + node.get("Rows Removed by Filter", 0))
                                    * node["Actual Loops"]
                                    for node in scans
                                )
                                assert visited <= maximum, (name, table, visited)
                finally:
                    await transaction.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())
