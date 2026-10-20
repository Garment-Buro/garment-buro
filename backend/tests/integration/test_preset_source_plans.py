"""The editor SKU bound also bounds PostgreSQL work, including generic plans."""

import asyncio
import importlib.util
import json
import os
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import literal, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.modules.catalog.editor_repository import CatalogEditorRepository
from tests.integration.test_crm_directory_plans import plan_nodes
from tests.postgres_schema import migrate

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


def test_preset_source_seeks_201_rows_and_index_rollback_preserves_skus(postgres_url, tmp_path):
    migrate(postgres_url, "upgrade", "head")

    async def scenario():
        engine = create_async_engine(postgres_url)
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                try:
                    other = await connection.scalar(
                        text(
                            "INSERT INTO products(title,price,sizes,colors) VALUES ('Other preset',1,'[]','[]') RETURNING id"
                        )
                    )
                    target = await connection.scalar(
                        text(
                            "INSERT INTO products(title,price,sizes,colors) VALUES ('Editor preset',1,'[]','[]') RETURNING id"
                        )
                    )
                    for product in [other, target]:
                        await connection.execute(
                            text(
                                "INSERT INTO product_variants(product_id,sku,size,stock_quantity,reserved_quantity,width_cm,height_cm) "
                                "SELECT :product,:sku_prefix||i,'M',7,2,64.25,72.35 FROM generate_series(1,20000) i"
                            ),
                            {"product": product, "sku_prefix": f"source-{product}-"},
                        )
                    # Execute the real repository statement, not a hand-written equivalent.
                    statement = CatalogEditorRepository.variant_statement(target)
                    rows = list(await connection.execute(statement))
                    assert len(rows) == 201
                    await connection.execute(text("ANALYZE product_variants"))
                    plans = {}
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
                                "PREPARE preset_source_probe AS " + str(compiled)
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
                                        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) EXECUTE preset_source_probe("
                                        + args
                                        + ")"
                                    )
                                ).scalar()
                            finally:
                                await connection.exec_driver_sql("DEALLOCATE preset_source_probe")
                        plan = raw[0] if isinstance(raw, list) else json.loads(raw)[0]
                        plans[mode] = plan
                        (tmp_path / "preset-source-plans.json").write_text(
                            json.dumps(plans, indent=2)
                        )
                        nodes = list(plan_nodes(plan["Plan"]))
                        scan = next(
                            node
                            for node in nodes
                            if node.get("Index Name") == "ix_product_variants_editor"
                        )
                        assert scan["Actual Rows"] * scan["Actual Loops"] == 201
                        assert scan.get("Rows Removed by Filter", 0) == 0
                        candidate = next(
                            node
                            for node in nodes
                            if node.get("Subplan Name") == "CTE editor_variant_ids"
                        )
                        assert candidate["Actual Rows"] == 201
                        assert not any(
                            node["Node Type"] in {"Seq Scan", "Sort", "Incremental Sort"}
                            for node in plan_nodes(candidate)
                        )
                        assert (
                            sum(
                                node["Actual Rows"] * node["Actual Loops"]
                                for node in nodes
                                if node.get("Relation Name") == "product_variants"
                            )
                            <= 402
                        )
                        assert not any(node["Node Type"] == "Seq Scan" for node in nodes)
                        for node in nodes:
                            if node["Node Type"] in {"Sort", "Incremental Sort"}:
                                assert (
                                    max(
                                        child["Actual Rows"] * child["Actual Loops"]
                                        for child in node.get("Plans", [])
                                    )
                                    <= 201
                                )
                        if mode == "generic":
                            assert "$" in scan["Index Cond"]
                    (tmp_path / "preset-source-plans.json").write_text(json.dumps(plans, indent=2))
                    await connection.execute(text("SET LOCAL plan_cache_mode=auto"))
                    path = (
                        Path(__file__).resolve().parents[2]
                        / "migrations/versions/20261019_0077_preset_editor_source.py"
                    )
                    spec = importlib.util.spec_from_file_location("preset_source_migration", path)
                    migration = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(migration)
                    snapshot_sql = text(
                        "SELECT id,product_id,sku,size,garment_size_id,fabric_id,stock_quantity,reserved_quantity,width_cm,height_cm FROM product_variants WHERE product_id=:product ORDER BY id"
                    )
                    before = list(await connection.execute(snapshot_sql, {"product": target}))

                    def change(sync_connection, operation):
                        with Operations.context(MigrationContext.configure(sync_connection)):
                            operation()

                    for _ in range(2):
                        await connection.run_sync(change, migration.downgrade)
                        assert await connection.scalar(
                            text("SELECT to_regclass('ix_product_variants_product_id')")
                        )
                        assert (
                            await connection.scalar(
                                text("SELECT to_regclass('ix_product_variants_editor')")
                            )
                            is None
                        )
                        await connection.run_sync(change, migration.upgrade)
                        assert await connection.scalar(
                            text("SELECT to_regclass('ix_product_variants_editor')")
                        )
                        assert (
                            await connection.scalar(
                                text("SELECT to_regclass('ix_product_variants_product_id')")
                            )
                            is None
                        )
                        assert (
                            list(await connection.execute(snapshot_sql, {"product": target}))
                            == before
                        )
                finally:
                    await transaction.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())
