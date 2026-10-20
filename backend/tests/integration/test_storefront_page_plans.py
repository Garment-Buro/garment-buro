"""Deep public pages must seek their cursor rather than rescan earlier cards."""

import asyncio
import json
import os
from decimal import Decimal

import pytest
from sqlalchemy import literal, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.modules.catalog.storefront_repository import StorefrontRepository
from app.modules.catalog.storefront_schemas import StorefrontQuery
from tests.integration.test_crm_directory_plans import RecordingSession, plan_nodes
from tests.postgres_schema import migrate

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


async def explain(connection, statement, mode):
    await connection.execute(text("SET LOCAL plan_cache_mode=force_" + mode + "_plan"))
    if mode == "custom":
        sql = str(
            statement.compile(dialect=connection.dialect, compile_kwargs={"literal_binds": True})
        )
        raw = await connection.scalar(text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql))
    else:
        compiled = statement.compile(
            dialect=connection.dialect, compile_kwargs={"render_postcompile": True}
        )
        await connection.exec_driver_sql("PREPARE storefront_page_probe AS " + str(compiled))
        try:
            args = ", ".join(
                str(
                    literal(compiled.params[key]).compile(
                        dialect=connection.dialect, compile_kwargs={"literal_binds": True}
                    )
                )
                for key in compiled.positiontup
            )
            raw = (
                await connection.exec_driver_sql(
                    "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) EXECUTE storefront_page_probe("
                    + args
                    + ")"
                    if compiled.positiontup
                    else "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) EXECUTE storefront_page_probe"
                )
            ).scalar()
        finally:
            await connection.exec_driver_sql("DEALLOCATE storefront_page_probe")
    return raw[0] if isinstance(raw, list) else json.loads(raw)[0]


@pytest.mark.parametrize("grouped_dates", [False, True], ids=["distinct-dates", "date-ties"])
def test_storefront_pages_seek_deep_date_price_and_price_tie_cursors(
    postgres_url, tmp_path, grouped_dates
):
    migrate(postgres_url, "upgrade", "head")

    async def scenario():
        engine = create_async_engine(postgres_url)
        plans, failures = {}, []
        try:
            # Previous rollback fixtures leave dead index entries. Measure the
            # seek itself, not how far autovacuum has progressed between cases.
            async with engine.connect() as maintenance:
                maintenance = await maintenance.execution_options(isolation_level="AUTOCOMMIT")
                await maintenance.execute(text("VACUUM (ANALYZE, INDEX_CLEANUP ON) products"))
            async with engine.connect() as connection:
                transaction = await connection.begin()
                try:
                    minutes = "((i-1)/10000)" if grouped_dates else "i"
                    inserted = list(
                        (
                            await connection.execute(
                                text(
                                    "INSERT INTO products(title,price,created_at,sizes,colors) "
                                    "SELECT 'Page plan '||i,1+(i-1)/10000,"
                                    f"TIMESTAMPTZ '2026-01-01 00:00:00+00' + {minutes}*INTERVAL '1 minute',"
                                    "'[]','[]' FROM generate_series(1,30000) i RETURNING id,created_at"
                                )
                            )
                        ).mappings()
                    )
                    await connection.execute(text("ANALYZE products"))
                    repository = StorefrontRepository()
                    positions = [
                        ("newest", None),
                        ("oldest", None),
                        ("cheap", None),
                        ("expensive", None),
                        ("newest", 7499),
                        ("oldest", 22499),
                        ("expensive", 7499),
                        ("cheap", 17499),
                        ("cheap", 10000),
                        ("cheap", 27499),
                        ("cheap", 20000),
                    ]
                    for sort, position in positions:
                        for limit in [24, 100]:
                            after = inserted[position] if position is not None else None
                            recording = RecordingSession(connection)
                            rows = await repository.list_page(
                                recording,
                                query=StorefrontQuery(sort=sort, limit=limit),
                                after_id=after["id"] if after else None,
                                after_price=Decimal(1 + position // 10000) if after else None,
                                after_created_at=after["created_at"] if after else None,
                            )
                            expected = list(range(len(inserted)))
                            if sort == "newest":
                                expected.reverse()
                            elif sort in {"cheap", "expensive"}:
                                expected.sort(
                                    key=lambda i: (
                                        i // 10000 if sort == "cheap" else -(i // 10000),
                                        -inserted[i]["id"],
                                    )
                                )
                            if position is not None:
                                expected = expected[expected.index(position) + 1 :]
                            expected = [inserted[i]["id"] for i in expected[: limit + 1]]
                            assert [row["id"] for row in rows] == expected
                            assert len(recording.statements) == 1
                            for mode in ["custom", "generic"]:
                                name = f"{sort}:{position}:{limit}:{mode}"
                                plan = await explain(connection, recording.statements[0], mode)
                                plans[name] = plan
                                scans = [
                                    node
                                    for node in plan_nodes(plan["Plan"])
                                    if node.get("Relation Name") == "products"
                                ]
                                visited = sum(
                                    (
                                        node["Actual Rows"]
                                        + node.get("Rows Removed by Filter", 0)
                                        + node.get("Rows Removed by Index Recheck", 0)
                                    )
                                    * node["Actual Loops"]
                                    for node in scans
                                )
                                if visited > 2 * (limit + 1):
                                    failures.append({"case": name, "visited": visited})
                                # Index filters can skip entries without counting them
                                # as removed heap rows. Include buffer work as evidence.
                                buffers = sum(
                                    node.get("Shared Hit Blocks", 0)
                                    + node.get("Shared Read Blocks", 0)
                                    for node in scans
                                )
                                if buffers > 2 * (limit + 1) + 10:
                                    failures.append({"case": name, "buffers": buffers})
                    (tmp_path / "storefront-page-plans.json").write_text(
                        json.dumps(plans, indent=2)
                    )
                    assert not failures, failures
                finally:
                    await transaction.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())
