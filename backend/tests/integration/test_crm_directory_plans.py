"""Real PostgreSQL plans: a bounded API must also seek bounded rows in the DB."""

import asyncio
import json
import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, insert, literal, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db import models as database_models  # noqa: F401
from app.modules.catalog.models import ProductCategory
from app.modules.crm.category_directory_repository import CategoryDirectoryRepository
from app.modules.crm.category_directory_schemas import CategoryDirectoryQuery
from app.modules.crm.directory_repository import ReferenceDirectoryRepository
from app.modules.crm.directory_schemas import ModelDirectoryQuery
from app.modules.crm.pattern_directory_repository import PatternDirectoryRepository
from app.modules.crm.pattern_directory_schemas import (
    PatternFileQuery,
    PatternGridQuery,
    PatternModelQuery,
    PatternSize,
)
from app.modules.crm.pattern_directory_service import PatternDirectoryService
from app.modules.crm.reference_models import (
    CrmGarmentModel,
    CrmGarmentModelCategory,
    CrmGarmentSize,
)
from tests.postgres_schema import migrate

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


class RecordingSession:
    """Run the real repository statement; then explain that exact statement."""

    def __init__(self, connection):
        self.connection = connection
        self.statements = []

    def get_bind(self):
        return self.connection

    async def execute(self, statement):
        self.statements.append(statement)
        return await self.connection.execute(statement)

    async def scalar(self, statement):
        self.statements.append(statement)
        return await self.connection.scalar(statement)


def plan_nodes(plan):
    yield plan
    for child in plan.get("Plans", []):
        yield from plan_nodes(child)


def test_crm_directories_seek_large_tables_and_keep_exact_geometry(postgres_url, tmp_path):
    migrate(postgres_url, "upgrade", "head")

    async def action():
        engine = create_async_engine(postgres_url)
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                try:
                    # Removing the redundant outer C collation must preserve old cursor order.
                    unicode_values = ["Ёлка", "ЕЛКА", "ß", "ẞ", "İ", "é", "é", "😀", "_%\\"]
                    unicode_values += [
                        chr(i) for i in range(1, 0x10FFFF, 997) if not 0xD800 <= i <= 0xDFFF
                    ]
                    old_order, new_order = (
                        await connection.execute(
                            text(
                                'SELECT array_agg(value ORDER BY lower(value COLLATE "pg_c_utf8") COLLATE "C",ord), '
                                'array_agg(value ORDER BY lower(value COLLATE "pg_c_utf8"),ord) '
                                "FROM unnest(CAST(:values AS text[])) WITH ORDINALITY AS t(value,ord)"
                            ),
                            {"values": unicode_values},
                        )
                    ).one()
                    assert old_order == new_order
                    # Everything, including statistics changes, belongs to this rollback.
                    prefix = uuid4().hex
                    await connection.execute(
                        text(
                            "INSERT INTO crm_garment_models(code,name) "
                            "SELECT :prefix||'-'||i, :prefix||' Модель '||lpad((20001-i)::text,5,'0') "
                            "FROM generate_series(1,20000) i"
                        ),
                        {"prefix": prefix},
                    )
                    model = await connection.scalar(
                        text("SELECT id FROM crm_garment_models WHERE code=:code"),
                        {"code": prefix + "-1"},
                    )
                    deep_model = await connection.scalar(
                        text("SELECT id FROM crm_garment_models WHERE code=:code"),
                        {"code": prefix + "-1001"},
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO crm_garment_sizes(garment_model_id,code,base_price,"
                            "min_width_cm,max_width_cm,min_length_cm,max_length_cm,"
                            "allow_standard_sleeve,allow_height_sleeve) "
                            "SELECT id,'M',80,50.25,1048.25,60.35,458.35,true,false "
                            "FROM crm_garment_models WHERE code LIKE :prefix"
                        ),
                        {"prefix": prefix + "-%"},
                    )
                    size = await connection.scalar(
                        text("SELECT id FROM crm_garment_sizes WHERE garment_model_id=:model"),
                        {"model": model},
                    )
                    media = await connection.scalar(
                        text(
                            "INSERT INTO media_objects(provider,bucket_name,object_key,"
                            "original_filename,content_type,size_bytes,checksum_sha256,is_public,status) "
                            "VALUES ('minio','private',:key,'plan.pdf','application/pdf',1024,"
                            ":hash,false,'ready') RETURNING id"
                        ),
                        {"key": prefix + ".pdf", "hash": "a" * 64},
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO crm_garment_patterns(garment_model_id,garment_size_id,"
                            "media_object_id,grid_key,code,name,width_cm,length_cm) "
                            "SELECT :model,:size,:media,'probe-'||i,"
                            ":prefix||'-FILE-'||lpad((100001-i)::text,6,'0'),'Лекало '||i,"
                            "50.25+2*((i-1)%500),60.35+2*((i-1)/500) FROM generate_series(1,100000) i"
                        ),
                        {"model": model, "size": size, "media": media, "prefix": prefix},
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO crm_garment_patterns(garment_model_id,garment_size_id,"
                            "media_object_id,grid_key,code,name,width_cm,length_cm) "
                            "SELECT s.garment_model_id,s.id,:media,'base-'||i,"
                            ":prefix||'-BASE-'||s.id||'-'||i,'Файл',50.25+2*i,60.35 "
                            "FROM crm_garment_sizes s JOIN crm_garment_models m ON m.id=s.garment_model_id "
                            "CROSS JOIN generate_series(1,5) i WHERE m.code LIKE :match "
                            "AND s.garment_model_id<>:model"
                        ),
                        {"model": model, "media": media, "prefix": prefix, "match": prefix + "-%"},
                    )
                    for table in [
                        "crm_garment_models",
                        "crm_garment_sizes",
                        "crm_garment_patterns",
                    ]:
                        await connection.execute(text("ANALYZE " + table))
                    plans = {}

                    async def probe(name, call):
                        session = RecordingSession(connection)
                        rows = await call(session)
                        result = []
                        for statement in session.statements:
                            sql = str(
                                statement.compile(
                                    dialect=connection.dialect,
                                    compile_kwargs={"literal_binds": True},
                                )
                            )
                            plan = await connection.scalar(
                                text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql)
                            )
                            result.append(
                                plan[0] if isinstance(plan, list) else json.loads(plan)[0]
                            )
                        plans[name] = result
                        # EXPLAIN SELECT with bound values still produces a custom plan.
                        # PREPARE + EXPLAIN EXECUTE is needed to test a real generic plan.
                        generic = []
                        await connection.execute(
                            text("SET LOCAL plan_cache_mode=force_generic_plan")
                        )
                        try:
                            for statement in session.statements:
                                compiled = statement.compile(
                                    dialect=connection.dialect,
                                    compile_kwargs={"render_postcompile": True},
                                )
                                await connection.exec_driver_sql(
                                    "PREPARE crm_plan_probe AS " + str(compiled)
                                )
                                try:
                                    parameters = ", ".join(
                                        str(
                                            literal(compiled.params[key]).compile(
                                                dialect=connection.dialect,
                                                compile_kwargs={"literal_binds": True},
                                            )
                                        )
                                        for key in compiled.positiontup
                                    )
                                    plan = (
                                        await connection.exec_driver_sql(
                                            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) EXECUTE crm_plan_probe("
                                            + parameters
                                            + ")"
                                        )
                                    ).scalar()
                                    generic.append(
                                        plan[0] if isinstance(plan, list) else json.loads(plan)[0]
                                    )
                                finally:
                                    await connection.exec_driver_sql("DEALLOCATE crm_plan_probe")
                        finally:
                            await connection.execute(text("SET LOCAL plan_cache_mode=auto"))
                        plans[name + ":generic"] = generic
                        return rows, result

                    for sort, after_id, after_value, expected_index in [
                        ("name:asc", None, None, "ix_crm_models_directory_name"),
                        ("name:desc", None, None, "ix_crm_models_directory_name"),
                        ("code:asc", None, None, "ix_crm_models_directory_code"),
                        (
                            "name:asc",
                            deep_model,
                            prefix + " модель 19000",
                            "ix_crm_models_directory_name",
                        ),
                    ]:
                        rows, result = await probe(
                            f"models:{sort}:{after_id}",
                            lambda session, sort=sort, after_id=after_id, after_value=after_value: (
                                ReferenceDirectoryRepository.models(
                                    session,
                                    ModelDirectoryQuery(sort=sort),
                                    after_id=after_id,
                                    after_value=after_value,
                                )
                            ),
                        )
                        assert len(rows) == 25
                        nodes = list(plan_nodes(result[0]["Plan"]))
                        scans = [node for node in nodes if node.get("Index Name") == expected_index]
                        assert len(scans) == 1
                        assert scans[0]["Actual Rows"] == 25
                        assert scans[0].get("Rows Removed by Filter", 0) <= 25
                        if after_id:
                            assert "ROW(" in scans[0]["Index Cond"]
                            assert all(row["order_value"] > after_value for row in rows)
                        generic_nodes = list(
                            plan_nodes(plans[f"models:{sort}:{after_id}:generic"][0]["Plan"])
                        )
                        generic_scan = next(
                            node
                            for node in generic_nodes
                            if node.get("Index Name") == expected_index
                        )
                        assert generic_scan["Actual Rows"] == 25
                        assert generic_scan.get("Rows Removed by Filter", 0) <= 25
                        if after_id:
                            assert "$" in generic_scan["Index Cond"]
                    for kind, table, code_field, index_name in [
                        (
                            "model-categories",
                            "crm_garment_model_categories",
                            "code",
                            "ix_crm_model_categories_directory_name",
                        ),
                        (
                            "product-categories",
                            "product_categories",
                            "slug",
                            "ix_product_categories_directory_name",
                        ),
                    ]:
                        await connection.execute(
                            text(
                                f"INSERT INTO {table}({code_field},name) SELECT :prefix||'-'||i,"
                                ":prefix||' Категория '||lpad((20001-i)::text,5,'0') FROM generate_series(1,20000) i"
                            ),
                            {"prefix": prefix},
                        )
                        await connection.execute(text("ANALYZE " + table))
                        deep = await connection.scalar(
                            text(f"SELECT id FROM {table} WHERE {code_field}=:code"),
                            {"code": prefix + "-1001"},
                        )
                        _, result = await probe(
                            kind,
                            lambda session, kind=kind, deep=deep: (
                                CategoryDirectoryRepository().page(
                                    session,
                                    kind,
                                    CategoryDirectoryQuery(),
                                    after_id=deep,
                                    after_value=prefix + " категория 19000",
                                )
                            ),
                        )
                        for plan in [result[0], plans[kind + ":generic"][0]]:
                            node = next(
                                node
                                for node in plan_nodes(plan["Plan"])
                                if node.get("Index Name") == index_name
                            )
                            assert (
                                node["Actual Rows"] == 25
                                and node.get("Rows Removed by Filter", 0) <= 25
                            )
                            assert "ROW(" in node["Index Cond"]
                    _, result = await probe(
                        "pattern-models",
                        lambda session: PatternDirectoryRepository.models(
                            session, PatternModelQuery(), after_id=None, after_value=None
                        ),
                    )
                    assert any(
                        node.get("Index Name") == "ix_crm_models_directory_name"
                        for node in plan_nodes(result[0]["Plan"])
                    )
                    _, result = await probe(
                        "pattern-files",
                        lambda session: PatternDirectoryRepository.files(
                            session,
                            PatternFileQuery(sort="code:asc"),
                            after_id=None,
                            after_value=None,
                        ),
                    )
                    assert any(
                        node.get("Index Name") == "ix_crm_patterns_directory_code"
                        for node in plan_nodes(result[0]["Plan"])
                    )
                    size_context = PatternSize(
                        id=size,
                        code="M",
                        version=1,
                        is_active=True,
                        min_width_cm="50.25",
                        max_width_cm="1048.25",
                        min_length_cm="60.35",
                        max_length_cm="458.35",
                        allow_standard_sleeve=True,
                        allow_height_sleeve=False,
                    )
                    (rows, count), result = await probe(
                        "last-window",
                        lambda session: PatternDirectoryRepository.window(
                            session,
                            model,
                            size_context,
                            [Decimal("1038.25") + 2 * i for i in range(6)],
                            [Decimal("448.35") + 2 * i for i in range(6)],
                        ),
                    )
                    assert count == 100000 and len(rows) == 36
                    assert min(row["width_cm"] for row in rows) == Decimal("1038.25")
                    assert max(row["length_cm"] for row in rows) == Decimal("458.35")
                    window_nodes = list(plan_nodes(result[1]["Plan"]))
                    scans = [
                        node
                        for node in window_nodes
                        if node.get("Index Name") == "ix_crm_patterns_size_window"
                    ]
                    assert (
                        len(scans) == 1 and scans[0]["Actual Rows"] * scans[0]["Actual Loops"] == 36
                    )
                    assert scans[0].get("Rows Removed by Filter", 0) == 0
                    assert not any(
                        node.get("Relation Name") == "crm_garment_sizes" for node in window_nodes
                    )
                    generic_nodes = list(plan_nodes(plans["last-window:generic"][1]["Plan"]))
                    generic_scan = next(
                        node
                        for node in generic_nodes
                        if node.get("Index Name") == "ix_crm_patterns_size_window"
                    )
                    assert generic_scan["Actual Rows"] * generic_scan["Actual Loops"] == 36
                    assert generic_scan.get("Rows Removed by Filter", 0) == 0
                    assert "$" in generic_scan["Index Cond"]
                    # Corrupt duplicate slot keys must not be silently truncated to two sleeves.
                    await connection.execute(
                        text(
                            "INSERT INTO crm_garment_patterns(garment_model_id,garment_size_id,media_object_id,"
                            "grid_key,code,name,width_cm,length_cm) SELECT :model,:size,:media,"
                            "'duplicate-'||i,:prefix||'-DUP-'||i,'Duplicate',1048.25,458.35 "
                            "FROM generate_series(1,5) i"
                        ),
                        {"model": model, "size": size, "media": media, "prefix": prefix},
                    )
                    with pytest.raises(ValueError, match="duplicate"):
                        await PatternDirectoryService().coverage(
                            RecordingSession(connection),
                            model,
                            PatternGridQuery(size_id=size, width_page=83, length_page=33),
                        )
                    (tmp_path / "crm-query-plans.json").write_text(json.dumps(plans, indent=2))
                finally:
                    await transaction.rollback()
        finally:
            await engine.dispose()

    asyncio.run(action())


def test_crm_directory_index_upgrade_and_rollback_preserve_models(postgres_url):
    migrate(postgres_url, "upgrade", "head")
    owned = {}
    indexes = {
        "ix_crm_models_directory_name",
        "ix_crm_models_directory_code",
        "ix_crm_patterns_directory_code",
        "ix_crm_patterns_size_window",
        "ix_crm_model_categories_directory_name",
        "ix_product_categories_directory_name",
        "ix_crm_models_editor_active_id",
        "ix_crm_fabrics_editor_active_id",
        "ix_crm_sizes_editor_model_active_id",
    }

    async def action(name):
        engine = create_async_engine(postgres_url)
        try:
            async with engine.begin() as connection:
                if name == "seed":
                    owned["id"] = await connection.scalar(
                        insert(CrmGarmentModel)
                        .values(code=uuid4().hex, name="Ёлка_%\\", version=7)
                        .returning(CrmGarmentModel.id)
                    )
                    owned["row"] = tuple(
                        (
                            await connection.execute(
                                select(CrmGarmentModel.__table__).where(
                                    CrmGarmentModel.id == owned["id"]
                                )
                            )
                        ).one()
                    )
                    owned["size_id"] = await connection.scalar(
                        insert(CrmGarmentSize)
                        .values(
                            garment_model_id=owned["id"],
                            code="M",
                            version=9,
                            base_width_cm=64.25,
                            base_price=80,
                            is_active=False,
                        )
                        .returning(CrmGarmentSize.id)
                    )
                    owned["size_row"] = tuple(
                        (
                            await connection.execute(
                                select(CrmGarmentSize.__table__).where(
                                    CrmGarmentSize.id == owned["size_id"]
                                )
                            )
                        ).one()
                    )
                    for table in [CrmGarmentModelCategory, ProductCategory]:
                        fields = {"name": "Историческая категория " + uuid4().hex, "version": 7}
                        fields.update(
                            {"code": uuid4().hex}
                            if table is CrmGarmentModelCategory
                            else {
                                "slug": uuid4().hex,
                                "description": "Полное описание\nс переносом",
                            }
                        )
                        identity = await connection.scalar(
                            insert(table).values(**fields).returning(table.id)
                        )
                        snapshot = tuple(
                            (
                                await connection.execute(
                                    select(table.__table__).where(table.id == identity)
                                )
                            ).one()
                        )
                        owned[table.__tablename__] = (identity, snapshot)
                elif name == "cleanup":
                    await connection.execute(
                        delete(CrmGarmentModel).where(CrmGarmentModel.id == owned.get("id"))
                    )
                    for table in [CrmGarmentModelCategory, ProductCategory]:
                        if table.__tablename__ in owned:
                            await connection.execute(
                                delete(table).where(table.id == owned[table.__tablename__][0])
                            )
                else:
                    row = (
                        await connection.execute(
                            select(CrmGarmentModel.__table__).where(
                                CrmGarmentModel.id == owned["id"]
                            )
                        )
                    ).one()
                    assert tuple(row) == owned["row"]
                    size_row = (
                        await connection.execute(
                            select(CrmGarmentSize.__table__).where(
                                CrmGarmentSize.id == owned["size_id"]
                            )
                        )
                    ).one()
                    assert tuple(size_row) == owned["size_row"]
                    for table in [CrmGarmentModelCategory, ProductCategory]:
                        identity, snapshot = owned[table.__tablename__]
                        assert (
                            tuple(
                                (
                                    await connection.execute(
                                        select(table.__table__).where(table.id == identity)
                                    )
                                ).one()
                            )
                            == snapshot
                        )
                    names = set(
                        (
                            await connection.execute(
                                text("SELECT indexname FROM pg_indexes WHERE schemaname='public'")
                            )
                        ).scalars()
                    )
                    assert (indexes <= names) if name == "up" else not indexes.intersection(names)
                    assert ("ix_crm_garment_sizes_code" not in names) == (name == "up")
                    definition = await connection.scalar(
                        text(
                            "SELECT indexdef FROM pg_indexes WHERE schemaname='public' AND indexname='ix_crm_garment_sizes_model_active_sort'"
                        )
                    )
                    assert (
                        "(garment_model_id, is_active, sort_order, id)"
                        if name == "up"
                        else "(garment_model_id, is_active, sort_order)"
                    ) in definition
                    unique_definition = await connection.scalar(
                        text(
                            "SELECT indexdef FROM pg_indexes WHERE schemaname='public' "
                            "AND indexname='uq_crm_garment_size_code'"
                        )
                    )
                    assert ("INCLUDE (id)" in unique_definition) == (name == "up")
        finally:
            await engine.dispose()

    try:
        asyncio.run(action("seed"))
        for _ in range(2):
            migrate(postgres_url, "downgrade", "20261018_0072")
            asyncio.run(action("down"))
            migrate(postgres_url, "upgrade", "head")
            asyncio.run(action("up"))
    finally:
        migrate(postgres_url, "upgrade", "head")
        asyncio.run(action("cleanup"))
