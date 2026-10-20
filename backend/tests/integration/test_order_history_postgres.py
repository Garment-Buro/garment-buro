"""Indexed owner pages stay bounded in large direct and historical histories."""

import asyncio
import json
import os
from uuid import uuid4

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.modules.identity.models import User
from app.modules.orders.models import LegacyOrderClaim, Order
from app.modules.orders.repository import TargetOrderReadRepository
from tests.postgres_schema import migrate

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


def test_history_indexes_migrate_and_bound_both_owner_branches(postgres_url):
    migrate(postgres_url, "upgrade", "head")

    async def scenario():
        engine = create_async_engine(postgres_url)
        try:
            async with engine.begin() as connection:
                owners = [
                    await connection.scalar(
                        insert(User).values(internal_identity=uuid4().hex).returning(User.id)
                    )
                    for _ in range(2)
                ]
                # This test rolls its entire dataset back, preserving other fixtures.
                for user_id in owners:
                    await connection.execute(
                        text(
                            "INSERT INTO orders (user_id,items_subtotal,delivery_price,total_price,request_fingerprint_sha256) "
                            "SELECT :user_id,100,0,100,repeat('a',64) FROM generate_series(1,20000)"
                        ),
                        {"user_id": user_id},
                    )
                direct = list(
                    await connection.scalars(
                        select(Order.id).where(Order.user_id == owners[1]).order_by(Order.id.desc())
                    )
                )
                foreign = list(
                    await connection.scalars(
                        select(Order.id).where(Order.user_id == owners[0]).order_by(Order.id.desc())
                    )
                )
                await connection.execute(
                    text(
                        "INSERT INTO legacy_order_claims (user_id,legacy_order_id,source,identifier_digest) "
                        "SELECT :owner,id,'verified_email',repeat('b',64) FROM orders WHERE user_id=:foreign"
                    ),
                    {"owner": owners[1], "foreign": owners[0]},
                )
                # A directly owned order also claimed by the same account appears once.
                await connection.execute(
                    insert(LegacyOrderClaim).values(
                        user_id=owners[1],
                        legacy_order_id=direct[0],
                        source="verified_email",
                        identifier_digest="b" * 64,
                    )
                )
                await connection.execute(text("ANALYZE orders"))
                await connection.execute(text("ANALYZE legacy_order_claims"))
                repository = TargetOrderReadRepository()
                for cursor, expected in [
                    (None, direct[:25]),
                    (direct[-1], foreign[:25]),
                    (foreign[23], foreign[24:49]),
                ]:
                    statement = repository.history_statement(
                        user_id=owners[1], limit=25, before_id=cursor
                    )
                    rows = (await connection.execute(statement)).mappings().all()
                    assert [row["id"] for row in rows] == expected
                    sql = str(
                        statement.compile(
                            dialect=engine.dialect, compile_kwargs={"literal_binds": True}
                        )
                    )
                    plan = await connection.scalar(
                        text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql)
                    )
                    if isinstance(plan, str):
                        plan = json.loads(plan)

                    def walk(node):
                        yield node
                        for child in node.get("Plans", []):
                            yield from walk(child)

                    nodes = list(walk(plan[0]["Plan"]))
                    for node in nodes:
                        if node.get("Relation Name") in {"orders", "legacy_order_claims"}:
                            assert node["Node Type"] != "Seq Scan", node
                            inspected = node["Actual Rows"] + node.get("Rows Removed by Filter", 0)
                            assert inspected * node["Actual Loops"] <= 100, node
                await connection.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())

    async def indexes():
        engine = create_async_engine(postgres_url)
        try:
            async with engine.connect() as connection:
                return set(
                    await connection.scalars(
                        text(
                            "SELECT indexname FROM pg_indexes WHERE tablename IN ('orders','legacy_order_claims')"
                        )
                    )
                )
        finally:
            await engine.dispose()

    assert {"ix_orders_owner_recent", "ix_legacy_order_claims_owner_recent"} <= asyncio.run(
        indexes()
    )
    migrate(postgres_url, "downgrade", "20261016_0065")
    old = asyncio.run(indexes())
    assert {"ix_orders_user_id", "ix_legacy_order_claims_user_id"} <= old
    assert not {"ix_orders_owner_recent", "ix_legacy_order_claims_owner_recent"} & old
    migrate(postgres_url, "upgrade", "head")
    assert {"ix_orders_owner_recent", "ix_legacy_order_claims_owner_recent"} <= asyncio.run(
        indexes()
    )
