"""The card-image result must not require ranking every image in its owners."""

import asyncio
import json
import os

import pytest
from sqlalchemy import literal, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.modules.catalog.storefront_repository import (
    CARD_IMAGE_ROLES,
    COLLECTION_IMAGE_ROLES,
    StorefrontRepository,
)
from tests.integration.test_crm_directory_plans import RecordingSession, plan_nodes
from tests.postgres_schema import migrate

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


def test_storefront_card_images_seek_first_eligible_link_per_owner(postgres_url, tmp_path):
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
                                    "SELECT 'Image plan '||i,1,'[]','[]' FROM generate_series(1,200) i "
                                    "RETURNING id"
                                )
                            )
                        ).scalars()
                    )
                    first_media = await connection.scalar(
                        text(
                            "WITH created AS ("
                            "INSERT INTO media_objects(bucket_name,object_key,content_type,size_bytes,checksum_sha256,status,is_public) "
                            "SELECT 'catalog','uploads/card-plan-'||i||'.webp','image/webp',10,repeat('a',64),'ready',true "
                            "FROM generate_series(1,20000) i RETURNING id) SELECT max(id)-199 FROM created"
                        )
                    )
                    roles = list(dict.fromkeys([*CARD_IMAGE_ROLES, *COLLECTION_IMAGE_ROLES]))
                    for offset, product in enumerate(products):
                        for role in roles:
                            await connection.execute(
                                text(
                                    "INSERT INTO product_media(product_id,media_object_id,role,sort_order,alt_text) "
                                    "SELECT :product,:media,:role,i,:role FROM generate_series(0,99) i"
                                ),
                                {"product": product, "media": first_media + offset, "role": role},
                            )
                    for table in ["product_media", "media_objects"]:
                        await connection.execute(text("ANALYZE " + table))
                    for name, role_order in [
                        ("catalog", CARD_IMAGE_ROLES),
                        ("collection", COLLECTION_IMAGE_ROLES),
                        ("single", ("gallery_images",)),
                    ]:
                        for count in [4, 24, 100]:
                            recording = RecordingSession(connection)
                            images = await StorefrontRepository().card_images(
                                recording, products[:count], roles=role_order
                            )
                            assert len(recording.statements) == 1
                            assert len(images) == count
                            assert all(row["alt_text"] == role_order[0] for row in images.values())
                            statement = recording.statements[0]
                            for mode in ["custom", "generic"]:
                                await connection.execute(
                                    text("SET LOCAL plan_cache_mode=force_" + mode + "_plan")
                                )
                                if mode == "custom":
                                    sql = str(
                                        statement.compile(
                                            dialect=connection.dialect,
                                            compile_kwargs={"literal_binds": True},
                                        )
                                    )
                                    raw = await connection.scalar(
                                        text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql)
                                    )
                                else:
                                    compiled = statement.compile(
                                        dialect=connection.dialect,
                                        compile_kwargs={"render_postcompile": True},
                                    )
                                    await connection.exec_driver_sql(
                                        "PREPARE storefront_image_probe AS " + str(compiled)
                                    )
                                    try:
                                        args = ", ".join(
                                            str(
                                                literal(compiled.params[key]).compile(
                                                    dialect=connection.dialect,
                                                    compile_kwargs={"literal_binds": True},
                                                )
                                            )
                                            for key in compiled.positiontup
                                        )
                                        raw = (
                                            await connection.exec_driver_sql(
                                                "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) EXECUTE storefront_image_probe("
                                                + args
                                                + ")"
                                            )
                                        ).scalar()
                                    finally:
                                        await connection.exec_driver_sql(
                                            "DEALLOCATE storefront_image_probe"
                                        )
                                plan = raw[0] if isinstance(raw, list) else json.loads(raw)[0]
                                plans[f"{name}:{count}:{mode}"] = plan
                                (tmp_path / "storefront-image-plans.json").write_text(
                                    json.dumps(plans, indent=2)
                                )
                                nodes = list(plan_nodes(plan["Plan"]))
                                for table in ["product_media", "media_objects"]:
                                    scans = [n for n in nodes if n.get("Relation Name") == table]
                                    assert not any(n["Node Type"] == "Seq Scan" for n in scans)
                                    assert (
                                        sum(n["Actual Rows"] * n["Actual Loops"] for n in scans)
                                        <= count * 2
                                    )
                                    assert all(
                                        n.get("Rows Removed by Filter", 0) == 0 for n in scans
                                    )
                                assert not any(n["Node Type"] == "WindowAgg" for n in nodes)
                                for node in nodes:
                                    if node["Node Type"] in {"Sort", "Incremental Sort"}:
                                        assert (
                                            max(
                                                child["Actual Rows"] * child["Actual Loops"]
                                                for child in node["Plans"]
                                            )
                                            <= count
                                        )
                finally:
                    await transaction.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())
