"""Real lock waits, partial-index plans and reversible catalog command schema."""

import asyncio
import importlib.util
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import delete, literal, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.modules.catalog.models import CatalogAuditEvent, Product, ProductVariant
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import ProductWriteRequest
from app.modules.catalog.service import (
    CatalogInventoryReservedError,
    CatalogProductVersionConflictError,
    CatalogWriteService,
)
from tests.integration.test_crm_directory_plans import plan_nodes
from tests.postgres_schema import migrate, seed_historical_product

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


async def lock_wait(engine, pid, pending):
    async with engine.connect() as observer:
        for _ in range(300):
            if await observer.scalar(
                text("SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=:pid"),
                {"pid": pid},
            ):
                return
            assert not pending.done(), "The competing command must wait on the product lock"
            await asyncio.sleep(0.01)
    raise AssertionError("PostgreSQL did not report a lock wait")


@pytest.mark.parametrize("operation", ["stale_update", "delete_after_reserve"])
def test_commands_wait_on_product_then_use_fresh_version_and_reserves(postgres_url, operation):
    migrate(postgres_url, "upgrade", "head")

    async def scenario():
        engine = create_async_engine(postgres_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        product_id = None
        pending = None
        settings = Settings(
            _env_file=None,
            app_env="test",
            database_enabled=True,
            database_url=postgres_url,
            minio_enabled=False,
        )
        service = CatalogWriteService(settings)
        try:
            async with sessions() as session:
                product = Product(
                    title="Original",
                    price=80,
                    stock_quantity=7,
                    variants=[ProductVariant(size="M", stock_quantity=7, sku=uuid4().hex)],
                )
                session.add(product)
                await session.flush()
                product_id, variant_id = product.id, product.variants[0].id
                await session.commit()
            payload = ProductWriteRequest(
                title="Winner",
                price=80,
                stock_quantity=7,
                variants=[{"id": variant_id, "size": "M", "stock_quantity": 7}],
            )
            async with sessions() as first, sessions() as second:
                cached = await second.get(Product, product_id)
                if operation == "stale_update":
                    winner = await service.update_product(
                        first,
                        product_id=product_id,
                        expected_version=1,
                        payload=payload,
                        actor_user_id=None,
                    )
                    assert winner.version == 2 and cached.version == 1
                else:
                    await CatalogRepository().get_product_for_update(first, product_id)
                    variant = await first.get(ProductVariant, variant_id)
                    variant.reserved_quantity = 1
                    await first.flush()
                pid = await second.scalar(text("SELECT pg_backend_pid()"))
                if operation == "stale_update":
                    command = service.update_product(
                        second,
                        product_id=product_id,
                        expected_version=1,
                        payload=payload.model_copy(update={"title": "Loser"}),
                        actor_user_id=None,
                    )
                    error = CatalogProductVersionConflictError
                else:
                    command = service.delete_product(
                        second, product_id=product_id, actor_user_id=None
                    )
                    error = CatalogInventoryReservedError
                pending = asyncio.create_task(command)
                await asyncio.wait_for(lock_wait(engine, pid, pending), timeout=5)
                await first.commit()
                with pytest.raises(error):
                    await asyncio.wait_for(pending, timeout=5)
                await second.rollback()
            async with sessions() as session:
                product = await session.get(Product, product_id)
                variant = await session.get(ProductVariant, variant_id)
                actions = list(
                    await session.scalars(
                        select(CatalogAuditEvent.action).where(
                            CatalogAuditEvent.product_id == product_id
                        )
                    )
                )
                if operation == "stale_update":
                    assert (
                        product.title == "Winner"
                        and product.version == 2
                        and variant.reserved_quantity == 0
                    )
                    assert actions == ["product.updated"]
                else:
                    assert (
                        product.title == "Original"
                        and product.version == 1
                        and variant.reserved_quantity == 1
                    )
                    assert actions == []
        finally:
            if pending is not None and not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            if product_id is not None:
                async with sessions() as session:
                    await session.execute(delete(Product).where(Product.id == product_id))
                    await session.execute(
                        delete(CatalogAuditEvent).where(CatalogAuditEvent.product_id == product_id)
                    )
                    await session.commit()
            await engine.dispose()

    asyncio.run(scenario())


def test_reserved_lookup_uses_partial_index_in_generic_plan_and_migration_keeps_rows(
    postgres_url, tmp_path
):
    migrate(postgres_url, "upgrade", "head")

    async def scenario():
        engine = create_async_engine(postgres_url)
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                try:
                    other = await seed_historical_product(connection, title="Other reserved")
                    target = await seed_historical_product(connection, title="Target unreserved")
                    for product, reserved in [(other, 1), (target, 0)]:
                        await connection.execute(
                            text(
                                "INSERT INTO product_variants(product_id,sku,size,stock_quantity,reserved_quantity,width_cm,height_cm) SELECT :product,:prefix||i,'M',7,:reserved,64.25,72.35 FROM generate_series(1,20000) i"
                            ),
                            {"product": product, "prefix": uuid4().hex, "reserved": reserved},
                        )
                    plans = {}
                    for state in ["empty", "reserved"]:
                        if state == "reserved":
                            await connection.execute(
                                text(
                                    "UPDATE product_variants SET reserved_quantity=1 WHERE id=(SELECT max(id) FROM product_variants WHERE product_id=:target)"
                                ),
                                {"target": target},
                            )
                        await connection.execute(text("ANALYZE product_variants"))
                        statement = CatalogRepository.reserved_variant_statement(target)
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
                                compiled = statement.compile(dialect=connection.dialect)
                                await connection.exec_driver_sql(
                                    "PREPARE reserved_probe AS " + str(compiled)
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
                                            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) EXECUTE reserved_probe("
                                            + args
                                            + ")"
                                        )
                                    ).scalar()
                                finally:
                                    await connection.exec_driver_sql("DEALLOCATE reserved_probe")
                            plan = raw[0] if isinstance(raw, list) else json.loads(raw)[0]
                            plans[state + ":" + mode] = plan
                            nodes = list(plan_nodes(plan["Plan"]))
                            scan = next(
                                (
                                    node
                                    for node in nodes
                                    if node.get("Index Name")
                                    == "ix_product_variants_reserved_product"
                                ),
                                None,
                            )
                            assert scan is not None, (
                                state,
                                mode,
                                [
                                    (
                                        node["Node Type"],
                                        node.get("Index Name"),
                                        node.get("Actual Rows"),
                                        node.get("Rows Removed by Filter"),
                                    )
                                    for node in nodes
                                ],
                            )
                            assert scan["Actual Rows"] * scan["Actual Loops"] == (
                                1 if state == "reserved" else 0
                            )
                            assert not any(
                                node["Node Type"] in {"Seq Scan", "Sort", "Incremental Sort"}
                                for node in nodes
                            )
                            assert all(node.get("Rows Removed by Filter", 0) == 0 for node in nodes)
                            if mode == "generic":
                                assert "$" in scan["Index Cond"]
                    (tmp_path / "preset-command-plans.json").write_text(json.dumps(plans, indent=2))
                    await connection.execute(text("SET LOCAL plan_cache_mode=auto"))
                    path = (
                        Path(__file__).resolve().parents[2]
                        / "migrations/versions/20261019_0078_reserved_variant_lookup.py"
                    )
                    spec = importlib.util.spec_from_file_location(
                        "reserved_variant_migration", path
                    )
                    migration = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(migration)
                    snapshot = text(
                        "SELECT id,product_id,sku,size,garment_size_id,fabric_id,stock_quantity,reserved_quantity,width_cm,height_cm FROM product_variants WHERE product_id=:target ORDER BY id"
                    )
                    before = list(await connection.execute(snapshot, {"target": target}))

                    def change(sync, command):
                        with Operations.context(MigrationContext.configure(sync)):
                            command()

                    for _ in range(2):
                        await connection.run_sync(change, migration.downgrade)
                        assert (
                            await connection.scalar(
                                text("SELECT to_regclass('ix_product_variants_reserved_product')")
                            )
                            is None
                        )
                        await connection.run_sync(change, migration.upgrade)
                        assert await connection.scalar(
                            text("SELECT to_regclass('ix_product_variants_reserved_product')")
                        )
                        assert (
                            list(await connection.execute(snapshot, {"target": target})) == before
                        )
                finally:
                    await transaction.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())
