"""Explain actual editor repository statements against long sparse histories."""

import asyncio
import json
import os
from uuid import uuid4

import pytest
from sqlalchemy import literal, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.modules.catalog.editor_option_repository import EditorOptionRepository
from app.modules.catalog.editor_option_schemas import EditorOptionsQuery, EditorSizeQuery
from app.modules.crm.directory_repository import ReferenceDirectoryRepository
from app.modules.crm.reference_repository import CrmReferenceRepository
from tests.integration.test_crm_directory_plans import RecordingSession, plan_nodes
from tests.postgres_schema import migrate

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


class RecordingSizeSession(RecordingSession):
    async def scalars(self, statement):
        self.statements.append(statement)
        return await self.connection.scalars(statement)


def test_editor_options_seek_sparse_active_rows_and_bounded_model_source(postgres_url, tmp_path):
    migrate(postgres_url, "upgrade", "head")

    async def scenario():
        engine = create_async_engine(postgres_url)
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                try:
                    prefix = uuid4().hex
                    await connection.execute(
                        text(
                            "INSERT INTO crm_garment_models(code,name,is_active) SELECT :prefix||'-'||i,'Model '||i,i%20=0 FROM generate_series(1,20000) i"
                        ),
                        {"prefix": prefix},
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO crm_fabrics(code,name,color_name,width_cm,is_active) SELECT :prefix||'-'||i,'Fabric '||i,'White',150,i%20=0 FROM generate_series(1,20000) i"
                        ),
                        {"prefix": prefix},
                    )
                    model = await connection.scalar(
                        text("SELECT id FROM crm_garment_models WHERE code=:code"),
                        {"code": prefix + "-20000"},
                    )
                    model_cursor = await connection.scalar(
                        text("SELECT id FROM crm_garment_models WHERE code=:code"),
                        {"code": prefix + "-19000"},
                    )
                    fabric_cursor = await connection.scalar(
                        text("SELECT id FROM crm_fabrics WHERE code=:code"),
                        {"code": prefix + "-19000"},
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO crm_garment_sizes(garment_model_id,code,base_price,sort_order,is_active) SELECT :model,'SIZE-'||i,80,i/20,i%20=0 FROM generate_series(1,20000) i"
                        ),
                        {"model": model},
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO crm_garment_sizes(garment_model_id,code,base_price,sort_order,is_active) "
                            "SELECT m.id,'COMMON-'||i,80,i,false FROM "
                            "(SELECT id FROM crm_garment_models WHERE code LIKE :prefix ORDER BY id LIMIT 100) m "
                            "CROSS JOIN generate_series(1,100) i"
                        ),
                        {"prefix": prefix + "-%"},
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO crm_garment_sizes(garment_model_id,code,base_price,sort_order,is_active) "
                            "SELECT :model,'COMMON-'||i,80,i,false FROM generate_series(1,100) i"
                        ),
                        {"model": model},
                    )
                    size_cursor = await connection.scalar(
                        text(
                            "SELECT id FROM crm_garment_sizes WHERE garment_model_id=:model AND code='SIZE-19000'"
                        ),
                        {"model": model},
                    )
                    for table in ["crm_garment_models", "crm_fabrics", "crm_garment_sizes"]:
                        await connection.execute(text("ANALYZE " + table))
                    probes = [
                        (
                            "models:first",
                            lambda session: EditorOptionRepository.models(
                                session, EditorOptionsQuery()
                            ),
                            "ix_crm_models_editor_active_id",
                            25,
                        ),
                        (
                            "fabrics:first",
                            lambda session: EditorOptionRepository.fabrics(
                                session, EditorOptionsQuery()
                            ),
                            "ix_crm_fabrics_editor_active_id",
                            25,
                        ),
                        (
                            "sizes:first",
                            lambda session: EditorOptionRepository.sizes(
                                session, EditorSizeQuery(model_id=model)
                            ),
                            "ix_crm_sizes_editor_model_active_id",
                            25,
                        ),
                        (
                            "models",
                            lambda session: EditorOptionRepository.models(
                                session, EditorOptionsQuery(cursor=model_cursor)
                            ),
                            "ix_crm_models_editor_active_id",
                            25,
                        ),
                        (
                            "fabrics",
                            lambda session: EditorOptionRepository.fabrics(
                                session, EditorOptionsQuery(cursor=fabric_cursor)
                            ),
                            "ix_crm_fabrics_editor_active_id",
                            25,
                        ),
                        (
                            "sizes",
                            lambda session: EditorOptionRepository.sizes(
                                session, EditorSizeQuery(model_id=model, cursor=size_cursor)
                            ),
                            "ix_crm_sizes_editor_model_active_id",
                            25,
                        ),
                        (
                            "source",
                            lambda session: ReferenceDirectoryRepository.model_detail(
                                session, model
                            ),
                            "ix_crm_garment_sizes_model_active_sort",
                            101,
                        ),
                        (
                            "command:active",
                            lambda session: CrmReferenceRepository.active_garment_sizes(
                                session, garment_model_id=model
                            ),
                            "ix_crm_garment_sizes_model_active_sort",
                            101,
                        ),
                        (
                            "command:codes-two",
                            lambda session: CrmReferenceRepository.garment_sizes_by_codes(
                                session,
                                garment_model_id=model,
                                codes={"SIZE-19999", "SIZE-20000"},
                            ),
                            {"uq_crm_garment_size_code", "ix_crm_garment_sizes_code"},
                            2,
                        ),
                        (
                            "command:codes-hundred",
                            lambda session: CrmReferenceRepository.garment_sizes_by_codes(
                                session,
                                garment_model_id=model,
                                codes={f"SIZE-{i}" for i in range(19901, 20001)},
                            ),
                            {"uq_crm_garment_size_code", "ix_crm_garment_sizes_code"},
                            100,
                        ),
                        (
                            "command:codes-common",
                            lambda session: CrmReferenceRepository.garment_sizes_by_codes(
                                session,
                                garment_model_id=model,
                                codes={f"COMMON-{i}" for i in range(1, 101)},
                            ),
                            {"uq_crm_garment_size_code", "ix_crm_garment_sizes_code"},
                            100,
                        ),
                    ]
                    plans = {}
                    for name, call, expected_index, max_rows in probes:
                        recording = RecordingSizeSession(connection)
                        value = await call(recording)
                        assert len(value["sizes"] if name == "source" else value) == max_rows
                        for mode in ["custom", "generic"]:
                            explained = []
                            await connection.execute(
                                text(
                                    "SET LOCAL plan_cache_mode="
                                    + ("force_generic_plan" if mode == "generic" else "auto")
                                )
                            )
                            try:
                                for statement in recording.statements:
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
                                            "PREPARE editor_plan_probe AS " + str(compiled)
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
                                                    "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) EXECUTE editor_plan_probe("
                                                    + args
                                                    + ")"
                                                )
                                            ).scalar()
                                        finally:
                                            await connection.exec_driver_sql(
                                                "DEALLOCATE editor_plan_probe"
                                            )
                                    explained.append(
                                        raw[0] if isinstance(raw, list) else json.loads(raw)[0]
                                    )
                            finally:
                                await connection.execute(text("SET LOCAL plan_cache_mode=auto"))
                            plans[name + ":" + mode] = explained
                            (tmp_path / "editor-option-plans.json").write_text(
                                json.dumps(plans, indent=2)
                            )
                            nodes = [
                                node for result in explained for node in plan_nodes(result["Plan"])
                            ]
                            scan = next(
                                (
                                    node
                                    for node in nodes
                                    if node.get("Index Name")
                                    in (
                                        expected_index
                                        if isinstance(expected_index, set)
                                        else {expected_index}
                                    )
                                ),
                                None,
                            )
                            assert scan is not None, (
                                name,
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
                            assert scan["Actual Rows"] * scan["Actual Loops"] <= max_rows, (
                                name,
                                mode,
                                scan,
                            )
                            assert scan.get("Rows Removed by Filter", 0) == 0
                            assert not any(node["Node Type"] == "Seq Scan" for node in nodes)
                            for node in nodes:
                                if node["Node Type"] in {"Sort", "Incremental Sort"}:
                                    # A tiny requested-ID set may be sorted to deduplicate it;
                                    # directory pages must keep their index order without sorting.
                                    assert name.startswith("command:codes-")
                                    assert node["Actual Rows"] <= max_rows
                                    assert all(
                                        child["Actual Rows"] <= max_rows
                                        for child in node.get("Plans", [])
                                    )
                            assert all(node.get("Rows Removed by Filter", 0) == 0 for node in nodes)
                            if mode == "generic":
                                if name.startswith("command:codes-"):
                                    assert "$" in json.dumps(explained)
                                else:
                                    assert "$" in scan["Index Cond"]
                    (tmp_path / "editor-option-plans.json").write_text(json.dumps(plans, indent=2))
                finally:
                    await transaction.rollback()
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_model_commands_serialize_on_parent_and_reject_concurrent_stale_write(postgres_url):
    from sqlalchemy import delete, select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.modules.crm.reference_models import CrmGarmentModel, CrmGarmentSize, CrmReferenceEvent
    from app.modules.crm.reference_schemas import CrmGarmentModelWrite
    from app.modules.crm.reference_service import (
        CrmReferenceService,
        CrmReferenceVersionConflictError,
    )

    migrate(postgres_url, "upgrade", "head")

    async def scenario():
        engine = create_async_engine(postgres_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        identity = None
        pending = None
        code = "LOCK-" + uuid4().hex.upper()
        payload = CrmGarmentModelWrite.model_validate(
            {
                "code": code,
                "name": "Original",
                "sizes": [{"code": "M"}],
            }
        )
        service = CrmReferenceService()
        try:
            async with sessions() as seed:
                model = await service.create_garment_model(
                    seed, payload=payload, actor_user_id=None
                )
                identity = model.id
                await seed.commit()
            async with sessions() as first, sessions() as second:
                result = await service.update_garment_model(
                    first,
                    garment_model_id=identity,
                    expected_version=1,
                    payload=payload.model_copy(update={"name": "Winner"}),
                    actor_user_id=None,
                )
                assert result.version == 2
                second_pid = await second.scalar(text("SELECT pg_backend_pid()"))
                pending = asyncio.create_task(
                    service.update_garment_model(
                        second,
                        garment_model_id=identity,
                        expected_version=1,
                        payload=payload.model_copy(update={"name": "Stale loser"}),
                        actor_user_id=None,
                    )
                )

                async def wait_for_real_lock():
                    async with engine.connect() as observer:
                        for _ in range(300):
                            waiting = await observer.scalar(
                                text(
                                    "SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=:pid"
                                ),
                                {"pid": second_pid},
                            )
                            if waiting:
                                return
                            assert not pending.done(), (
                                "Concurrent command must wait on the parent lock"
                            )
                            await asyncio.sleep(0.01)
                    raise AssertionError("PostgreSQL did not report the expected lock wait")

                await asyncio.wait_for(wait_for_real_lock(), timeout=5)
                await first.commit()
                with pytest.raises(CrmReferenceVersionConflictError):
                    await asyncio.wait_for(pending, timeout=5)
                await second.rollback()
            async with sessions() as check:
                persisted = await check.get(CrmGarmentModel, identity)
                assert persisted.name == "Winner" and persisted.version == 2
                size = await check.scalar(
                    select(CrmGarmentSize).where(
                        CrmGarmentSize.garment_model_id == identity,
                    )
                )
                assert size.code == "M" and size.version == 2
                actions = list(
                    await check.scalars(
                        select(CrmReferenceEvent.action)
                        .where(
                            CrmReferenceEvent.entity_type == "garment_model",
                            CrmReferenceEvent.entity_id == identity,
                        )
                        .order_by(CrmReferenceEvent.entity_version)
                    )
                )
                assert actions == ["created", "updated"]
        finally:
            if pending is not None and not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            if identity is not None:
                async with sessions() as cleanup:
                    await cleanup.execute(
                        delete(CrmReferenceEvent).where(
                            CrmReferenceEvent.entity_type == "garment_model",
                            CrmReferenceEvent.entity_id == identity,
                        )
                    )
                    await cleanup.execute(
                        delete(CrmGarmentModel).where(CrmGarmentModel.id == identity)
                    )
                    await cleanup.commit()
            await engine.dispose()

    asyncio.run(scenario())
