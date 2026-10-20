import asyncio
import importlib.util
import json
import os
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import event, literal, select, text

from app.modules.crm.production_models import CrmProductionPlanRevision
from app.modules.production.read_service import ProductionReadService
from tests.unit.test_crm_production_workflow import NOW
from tests.unit.test_production_terminal import execute, setup

pytestmark = pytest.mark.skipif(
    not os.getenv("PRODUCTION_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


def nodes(node):
    yield node
    for child in node.get("Plans", []):
        yield from nodes(child)


def test_exact_reader_statements_with_unrelated_history(tmp_path):
    async def scenario():
        async with setup(
            tmp_path, postgres_url=os.environ["PRODUCTION_TEST_POSTGRES_URL"], quantity=2
        ) as (db, commands, specification):
            await execute(db, commands, "plan", unit_id=1, specification=specification)
            async with db.session() as session:
                schema = db.engine.get_execution_options()["schema_translate_map"][None]
                assert schema.startswith("production_test_") and schema.replace("_", "").isalnum()
                await session.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                plan = await session.scalar(select(CrmProductionPlanRevision))
                other = CrmProductionPlanRevision(
                    production_unit_id=2,
                    revision_number=1,
                    garment_model_id=plan.garment_model_id,
                    garment_size_id=plan.garment_size_id,
                    tech_card_revision_id=plan.tech_card_revision_id,
                    status="active",
                    evidence_sha256="a" * 64,
                    planned_at=NOW,
                )
                session.add(other)
                await session.flush()
                parameters = {
                    "target": plan.id,
                    "other": other.id,
                    "model": plan.garment_model_id,
                    "size": plan.garment_size_id,
                }
                await session.execute(
                    text(
                        "INSERT INTO crm_garment_models(code,name) SELECT 'PLAN-MODEL-'||i,'Model '||i FROM generate_series(1,50) i"
                    )
                )
                await session.execute(
                    text(
                        "INSERT INTO crm_garment_sizes(garment_model_id,code) SELECT id,'M' FROM crm_garment_models WHERE code LIKE 'PLAN-MODEL-%'"
                    )
                )
                await session.execute(
                    text(
                        "INSERT INTO crm_fabrics(code,name,color_name,width_cm) SELECT 'PLAN-FABRIC-'||i,'Fabric '||i,'Black',180 FROM generate_series(1,10000) i"
                    )
                )
                await session.execute(
                    text(
                        "INSERT INTO crm_garment_fabric_requirements(garment_model_id,fabric_id,meters_per_unit) SELECT m.id,f.id,1 FROM crm_garment_models m JOIN crm_fabrics f ON f.code LIKE 'PLAN-FABRIC-%' AND (substring(f.code from 13)::int-1)/200=substring(m.code from 12)::int-1 WHERE m.code LIKE 'PLAN-MODEL-%'"
                    )
                )
                await session.execute(
                    text(
                        "INSERT INTO crm_garment_fabric_requirements(garment_model_id,fabric_id,meters_per_unit) SELECT :model,id,1 FROM crm_fabrics WHERE code LIKE 'PLAN-FABRIC-%' ORDER BY id LIMIT 200"
                    ),
                    parameters,
                )
                await session.execute(
                    text(
                        "INSERT INTO crm_material_reservations(production_plan_revision_id,fabric_id,requested_meters,remaining_meters,created_at,updated_at) SELECT :other,id,1,1,now(),now() FROM crm_fabrics WHERE code LIKE 'PLAN-FABRIC-%'"
                    ),
                    parameters,
                )
                await session.execute(
                    text(
                        "INSERT INTO crm_material_reservations(production_plan_revision_id,fabric_id,requested_meters,remaining_meters,created_at,updated_at) SELECT :target,id,1,1,now(),now() FROM crm_fabrics WHERE code='FAB-BLACK-01'"
                    ),
                    parameters,
                )
                await session.execute(
                    text(
                        "INSERT INTO crm_garment_patterns(garment_model_id,garment_size_id,media_object_id,grid_key,code,name,width_cm,length_cm) SELECT s.garment_model_id,s.id,1,'plan-'||i,'ZZ-PLAN-'||s.id||'-'||i,'Plan',60,72 FROM crm_garment_sizes s CROSS JOIN generate_series(1,200) i WHERE s.code='M'"
                    )
                )
                await session.execute(
                    text(
                        "WITH media AS (INSERT INTO media_objects(bucket_name,object_key,content_type,size_bytes,checksum_sha256,is_public,status) SELECT 'private','plan-unrelated-'||i,'application/pdf',100,repeat('a',64),false,'ready' FROM generate_series(1,10000) i RETURNING id) INSERT INTO crm_file_attachments(media_object_id,production_project_id,role,sort_order,created_at) SELECT id,1,'production_evidence',id,now() FROM media"
                    )
                )
                for table in [
                    "crm_garment_models",
                    "crm_garment_sizes",
                    "crm_fabrics",
                    "crm_garment_fabric_requirements",
                    "crm_material_reservations",
                    "crm_garment_patterns",
                    "crm_file_attachments",
                    "media_objects",
                    "crm_production_plan_revisions",
                ]:
                    await session.execute(text("ANALYZE " + table))
                await session.commit()
            statements = []

            def capture(_connection, _cursor, statement, parameters, _context, _many):
                if statement.lstrip().upper().startswith(("SELECT", "WITH")):
                    statements.append((statement, parameters))

            event.listen(db.engine.sync_engine, "before_cursor_execute", capture)
            try:
                async with db.session() as session:
                    payload = await ProductionReadService().detail(
                        session, project_id=1, stations=["tech"]
                    )
            finally:
                event.remove(db.engine.sync_engine, "before_cursor_execute", capture)
            assert len(payload["units"]) == 2
            assert [f["id"] for f in payload["units"][0]["files"]] == [1, 2]
            report = []
            limits = {
                "crm_garment_patterns": 201,
                "crm_garment_fabric_requirements": 1,
                "crm_material_reservations": 1,
                "crm_file_attachments": 2,
                "media_objects": 2,
                "crm_fabrics": 2,
            }
            async with db.engine.connect() as connection:
                for index, (sql, query_parameters) in enumerate(statements):
                    name = "production_read_" + str(index)
                    await connection.exec_driver_sql("PREPARE " + name + " AS " + sql)
                    arguments = ",".join(
                        str(
                            literal(value).compile(
                                dialect=connection.dialect, compile_kwargs={"literal_binds": True}
                            )
                        )
                        for value in query_parameters
                    )
                    for mode in ["custom", "generic"]:
                        await connection.exec_driver_sql(
                            "SET LOCAL plan_cache_mode=force_" + mode + "_plan"
                        )
                        response = await connection.exec_driver_sql(
                            "EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) EXECUTE "
                            + name
                            + ("(" + arguments + ")" if query_parameters else "")
                        )
                        raw = response.scalar_one()
                        plan = json.loads(raw)[0] if isinstance(raw, str) else raw[0]
                        visits = {}
                        for table, maximum in limits.items():
                            scans = [
                                node
                                for node in nodes(plan["Plan"])
                                if node.get("Relation Name") == table
                            ]
                            count = sum(
                                (n["Actual Rows"] + n.get("Rows Removed by Filter", 0))
                                * n["Actual Loops"]
                                for n in scans
                            )
                            if scans:
                                visits[table] = count
                                assert count <= maximum, (mode, table, count, maximum, plan)
                        report.append({"mode": mode, "relations": visits, "plan": plan})
                    await connection.exec_driver_sql("DEALLOCATE " + name)
            async with db.session() as session:
                await session.execute(
                    text(
                        'DELETE FROM "'
                        + schema
                        + '".crm_material_reservations WHERE production_plan_revision_id=:plan'
                    ),
                    {"plan": parameters["target"]},
                )
                await session.commit()
                without = await ProductionReadService().detail(
                    session, project_id=1, stations=["tech"]
                )
                assert without["units"][0]["cutting"]["fabric"]["code"] == "FAB-BLACK-01"
            (tmp_path / "production-detail-plans.json").write_text(
                json.dumps(
                    {
                        "exactStatements": len(statements),
                        "explainPlans": len(report),
                        "realPostgres17": True,
                        "unrelatedReservations": 10000,
                        "unrelatedProjectFiles": 10000,
                        "otherModels": 50,
                        "missingPlanDoesNotUseNextPlan": True,
                        "plans": report,
                    },
                    indent=2,
                )
            )

    asyncio.run(scenario())


def test_material_lookup_index_migration_preserves_rows_in_both_directions(tmp_path):
    path = (
        Path(__file__).resolve().parents[2]
        / "migrations/versions/20261019_0080_production_material_first.py"
    )
    spec = importlib.util.spec_from_file_location("production_material_first", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    def change(connection, operation):
        with Operations.context(MigrationContext.configure(connection)):
            operation()

    async def scenario():
        async with setup(tmp_path, postgres_url=os.environ["PRODUCTION_TEST_POSTGRES_URL"]) as (
            db,
            commands,
            specification,
        ):
            await execute(db, commands, "plan", unit_id=1, specification=specification)
            async with db.engine.begin() as connection:
                schema = db.engine.get_execution_options()["schema_translate_map"][None]
                assert schema.startswith("production_test_") and schema.replace("_", "").isalnum()
                await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                await connection.execute(
                    text(
                        "INSERT INTO crm_material_reservations(production_plan_revision_id,fabric_id,requested_meters,remaining_meters,created_at,updated_at) SELECT p.id,f.id,1.125,1.125,now(),now() FROM crm_production_plan_revisions p CROSS JOIN crm_fabrics f LIMIT 1"
                    )
                )

                async def digests():
                    result = []
                    for table in ["crm_material_reservations", "crm_garment_fabric_requirements"]:
                        result.append(
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
                        )
                    return result

                before = await digests()
                assert all(row[0] > 0 for row in before)
                new = {
                    "ix_crm_material_reservation_plan_first",
                    "ix_crm_fabric_requirement_model_first",
                }
                old = {
                    "ix_crm_material_reservations_production_plan_revision_id",
                    "ix_crm_garment_fabric_requirements_garment_model_id",
                }

                async def indexes():
                    return set(
                        (
                            await connection.execute(
                                text("SELECT indexname FROM pg_indexes WHERE schemaname=:schema"),
                                {"schema": schema},
                            )
                        ).scalars()
                    )

                for _ in range(2):
                    await connection.run_sync(change, migration.downgrade)
                    assert await digests() == before
                    assert old <= await indexes() and not new & await indexes()
                    await connection.run_sync(change, migration.upgrade)
                    assert await digests() == before
                    assert new <= await indexes() and not old & await indexes()

    asyncio.run(scenario())
