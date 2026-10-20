"""Real custom/generic plans for bounded media pages, including deep keysets."""

import asyncio
import importlib.util
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import Response
from sqlalchemy import delete, insert, literal, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.modules.catalog.admin_api import read_catalog_admin_detail
from app.modules.catalog.admin_service import CatalogAdminReadService
from app.modules.catalog.editor_repository import CatalogEditorRepository
from app.modules.catalog.mapper import CatalogResponseMapper
from app.modules.catalog.models import CatalogAuditEvent, Product, ProductVariant
from app.modules.catalog.schemas import ProductWriteRequest
from app.modules.catalog.service import CatalogWriteService
from app.modules.media.models import MediaObject, ProductMedia
from tests.integration.test_crm_directory_plans import plan_nodes
from tests.integration.test_preset_command_postgres import lock_wait
from tests.postgres_schema import migrate

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


def test_media_pages_bound_candidates_and_global_metadata_reads(postgres_url, tmp_path):
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
                                    "INSERT INTO products(title,price,sizes,colors) VALUES "
                                    "('Media other',1,'[]','[]'),('Media target',1,'[]','[]') RETURNING id"
                                )
                            )
                        ).scalars()
                    )
                    other, target = products
                    await connection.execute(
                        text(
                            "INSERT INTO product_variants(product_id) SELECT CASE WHEN i%2=0 "
                            "THEN CAST(:target AS integer) ELSE CAST(:other AS integer) END FROM generate_series(1,400) i"
                        ),
                        {"target": target, "other": other},
                    )
                    variants = list(
                        (
                            await connection.execute(
                                text(
                                    "SELECT id FROM product_variants WHERE product_id=:product ORDER BY id"
                                ),
                                {"product": target},
                            )
                        ).scalars()
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO media_objects(bucket_name,object_key,content_type,size_bytes,checksum_sha256,status,is_public) "
                            "SELECT 'catalog','uploads/editor-media-plan-'||i||'.webp','image/webp',10,repeat('a',64),'ready',true "
                            "FROM generate_series(1,20000) i"
                        )
                    )
                    first_media = await connection.scalar(
                        text(
                            "SELECT max(id)-199 FROM media_objects WHERE object_key LIKE 'uploads/editor-media-plan-%'"
                        )
                    )
                    for product in products:
                        await connection.execute(
                            text(
                                "INSERT INTO product_media(product_id,media_object_id,role,sort_order) "
                                "SELECT :product,:media+((i-1)%200),'gallery_images',i FROM generate_series(1,20000) i"
                            ),
                            {"product": product, "media": first_media},
                        )
                    await connection.execute(
                        text(
                            "INSERT INTO product_variant_media(product_variant_id,media_object_id,role,sort_order) "
                            "SELECT v.id,:media+((i-1)%200),'images',i FROM product_variants v "
                            "CROSS JOIN generate_series(1,100) i WHERE v.product_id IN (:target,:other)"
                        ),
                        {"media": first_media, "target": target, "other": other},
                    )
                    for table in ["product_media", "product_variant_media", "media_objects"]:
                        await connection.execute(text("ANALYZE " + table))
                    path = (
                        Path(__file__).resolve().parents[2]
                        / "migrations/versions/20261019_0079_editor_media_owner_indexes.py"
                    )
                    spec = importlib.util.spec_from_file_location("editor_media_indexes", path)
                    migration = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(migration)

                    async def digests():
                        return [
                            tuple(
                                (
                                    await connection.execute(
                                        text(
                                            "SELECT count(*),md5(string_agg(row_to_json(x)::text,',' ORDER BY id)) FROM "
                                            + table
                                            + " x"
                                        )
                                    )
                                ).one()
                            )
                            for table in ["product_media", "product_variant_media"]
                        ]

                    def change(sync_connection, operation):
                        with Operations.context(MigrationContext.configure(sync_connection)):
                            operation()

                    before = await digests()
                    for _ in range(2):
                        await connection.run_sync(change, migration.downgrade)
                        assert await digests() == before
                        await connection.run_sync(change, migration.upgrade)
                        assert await digests() == before
                    assert all(count >= 40000 for count, _ in before)
                    cases = {
                        "product:first": {"product_id": target},
                        "product:deep": {"product_id": target, "after": ("gallery_images", 15000)},
                        "variant:first": {"variant_ids": variants},
                        "variant:deep": {
                            "variant_ids": variants,
                            "after": (variants[150], "images", 50),
                        },
                    }
                    for name, query in cases.items():
                        statement = CatalogEditorRepository.media_page_statement(**query)
                        rows = list(await connection.execute(statement))
                        assert len(rows) == 257
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
                                    "PREPARE editor_media_probe AS " + str(compiled)
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
                                            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) EXECUTE editor_media_probe("
                                            + args
                                            + ")"
                                        )
                                    ).scalar()
                                finally:
                                    await connection.exec_driver_sql(
                                        "DEALLOCATE editor_media_probe"
                                    )
                            plan = raw[0] if isinstance(raw, list) else json.loads(raw)[0]
                            plans[name + ":" + mode] = plan
                            (tmp_path / "editor-media-plans.json").write_text(
                                json.dumps(plans, indent=2)
                            )
                            nodes = list(plan_nodes(plan["Plan"]))
                            candidate = next(
                                node
                                for node in nodes
                                if node.get("Subplan Name") == "CTE editor_media_page"
                            )
                            assert (
                                candidate["Node Type"] == "Limit"
                                and candidate["Actual Rows"] == 257
                            )
                            candidate_nodes = list(plan_nodes(candidate))
                            expected = (
                                "uq_product_variant_media_role_order"
                                if name.startswith("variant")
                                else "uq_product_media_role_order"
                            )
                            scan = next(
                                node
                                for node in candidate_nodes
                                if node.get("Index Name") == expected
                            )
                            assert scan["Actual Rows"] * scan["Actual Loops"] == 257
                            assert scan.get("Rows Removed by Filter", 0) == 0
                            assert not any(
                                node["Node Type"] in {"Seq Scan", "Sort", "Incremental Sort"}
                                for node in candidate_nodes
                            )
                            if mode == "generic":
                                assert "$" in scan["Index Cond"]
                            assert not any(
                                node["Node Type"] == "Seq Scan"
                                and node.get("Relation Name") == "media_objects"
                                for node in nodes
                            )
                            assert (
                                sum(
                                    node["Actual Rows"] * node["Actual Loops"]
                                    for node in nodes
                                    if node.get("Relation Name") == "media_objects"
                                )
                                <= 257
                            )
                            for node in nodes:
                                if node["Node Type"] in {"Sort", "Incremental Sort"}:
                                    assert (
                                        max(
                                            child["Actual Rows"] * child["Actual Loops"]
                                            for child in node.get("Plans", [])
                                        )
                                        <= 257
                                    )
                finally:
                    await transaction.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_paged_source_allows_other_readers_and_blocks_writer_until_snapshot_finishes(
    postgres_url, monkeypatch
):
    migrate(postgres_url, "upgrade", "head")

    async def scenario():
        engine = create_async_engine(postgres_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        settings = Settings(
            _env_file=None,
            app_env="test",
            database_enabled=True,
            database_url=postgres_url,
            minio_enabled=False,
        )
        read = CatalogAdminReadService(CatalogResponseMapper(settings))
        write = CatalogWriteService(settings)
        product_id, media_ids = None, []
        reader_task, writer_task = None, None
        ready, proceed = asyncio.Event(), asyncio.Event()
        prefix = uuid4().hex
        old_url, new_url = f"/uploads/{prefix}-old.webp", f"/uploads/{prefix}-new.webp"
        original = CatalogEditorRepository.media_page
        try:
            async with sessions() as session:
                product = Product(
                    title="Read before replace",
                    price=80,
                    stock_quantity=7,
                    variants=[ProductVariant(size="M", stock_quantity=7)],
                )
                session.add(product)
                media = [
                    MediaObject(
                        bucket_name=settings.minio_media_bucket,
                        object_key=url[1:],
                        content_type="image/webp",
                        size_bytes=10,
                        checksum_sha256="a" * 64,
                        status="ready",
                        is_public=True,
                    )
                    for url in [old_url, new_url]
                ]
                session.add_all(media)
                await session.flush()
                product_id, variant_id, media_ids = (
                    product.id,
                    product.variants[0].id,
                    [row.id for row in media],
                )
                await session.execute(
                    insert(ProductMedia),
                    [
                        {
                            "product_id": product_id,
                            "media_object_id": media_ids[0],
                            "role": "gallery_images",
                            "sort_order": i,
                        }
                        for i in range(300)
                    ],
                )
                await session.commit()
            async with sessions() as first, sessions() as second, sessions() as writer:

                async def pause(cls, session, **query):
                    if session is first and query.get("after") is None:
                        ready.set()
                        await proceed.wait()
                    return await original(session, **query)

                monkeypatch.setattr(CatalogEditorRepository, "media_page", classmethod(pause))
                reader_task = asyncio.create_task(read.detail(first, product_id))
                await asyncio.wait_for(ready.wait(), timeout=5)
                # FOR SHARE permits another complete reader while the first is paused.
                parallel = await asyncio.wait_for(read.detail(second, product_id), timeout=5)
                assert parallel.version == 1 and parallel.gallery_images == ",".join(
                    [old_url] * 300
                )
                await second.commit()
                pid = await writer.scalar(text("SELECT pg_backend_pid()"))
                writer_task = asyncio.create_task(
                    write.update_product(
                        writer,
                        product_id=product_id,
                        expected_version=1,
                        actor_user_id=None,
                        payload=ProductWriteRequest(
                            title="After replace",
                            price=80,
                            stock_quantity=7,
                            gallery_images=new_url,
                            variants=[{"id": variant_id, "size": "M", "stock_quantity": 7}],
                        ),
                    )
                )
                await asyncio.wait_for(lock_wait(engine, pid, writer_task), timeout=5)
                proceed.set()
                snapshot = await asyncio.wait_for(reader_task, timeout=5)
                assert snapshot.version == 1 and snapshot.gallery_images == ",".join(
                    [old_url] * 300
                )
                assert not writer_task.done()  # Read transaction still owns its shared lock.
                await first.commit()
                saved = await asyncio.wait_for(writer_task, timeout=5)
                assert saved.version == 2 and saved.gallery_images == new_url
                await writer.commit()
            async with sessions() as session:
                fresh = await read_catalog_admin_detail(Response(), session, read, product_id)
                assert not session.in_transaction()
                assert fresh.version == 2 and fresh.gallery_images == new_url
                await session.rollback()
        finally:
            proceed.set()
            for task in [reader_task, writer_task]:
                if task is not None and not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
            if product_id is not None:
                async with sessions() as session:
                    await session.execute(
                        delete(CatalogAuditEvent).where(CatalogAuditEvent.product_id == product_id)
                    )
                    await session.execute(delete(Product).where(Product.id == product_id))
                    await session.execute(delete(MediaObject).where(MediaObject.id.in_(media_ids)))
                    await session.commit()
            await engine.dispose()

    asyncio.run(scenario())
