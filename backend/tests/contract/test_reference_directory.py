"""Reference directories stay bounded and editor reads preserve physical dimensions."""

import asyncio
import os
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, event, insert, select, update

from app.db.session import DatabaseManager
from app.modules.catalog.editor_option_schemas import EditorOptionsQuery, EditorSizeQuery
from app.modules.catalog.editor_options import CatalogEditorOptions
from app.modules.catalog.models import Product, ProductCategory
from app.modules.crm.assortment_models import CrmGarmentFabricRequirement
from app.modules.crm.assortment_router import router as crm_assortment_router
from app.modules.crm.assortment_router import write_router as crm_assortment_writes
from app.modules.crm.directory_schemas import FabricDirectoryQuery, ModelDirectoryQuery
from app.modules.crm.directory_service import ReferenceDirectoryService
from app.modules.crm.material_models import CrmMaterialBalance
from app.modules.crm.reference_models import (
    CrmFabric,
    CrmGarmentModel,
    CrmGarmentModelCategory,
    CrmGarmentSize,
)
from app.modules.crm.router import router as crm_router
from app.modules.identity.factory import build_identity_service
from app.modules.identity.models import RoleName, User, UserRole
from app.modules.identity.repository import IdentityRepository
from app.modules.production.auth_models import ProductionCredential, ProductionSession
from app.modules.production.auth_service import issue_code
from app.modules.production.router import router
from tests.favorites_scenario import favorite_settings, seed_favorites
from tests.postgres_schema import migrate

ROOT = "/api/production/admin/assortment"


@pytest.fixture(params=["sqlite", "postgres"])
def references(tmp_path, request):
    native = request.param == "postgres"
    if native and not os.getenv("SCHEMA_TEST_POSTGRES_URL"):
        pytest.skip("Requires disposable PostgreSQL")
    url = (
        os.environ["SCHEMA_TEST_POSTGRES_URL"]
        if native
        else f"sqlite+aiosqlite:///{tmp_path / 'references.db'}"
    )
    if native:
        migrate(url, "upgrade", "head")
    settings = favorite_settings(url).model_copy(
        update={
            "production_terminal_enabled": True,
            "crm_writes_enabled": True,
            "public_base_url": "https://test",
            "cors_origins": "https://test",
            # Each app owns its auth counters even when PostgreSQL is shared by the suite.
            "identity_otp_pepper": SecretStr(uuid4().hex + uuid4().hex),
        }
    )
    products, tokens, users = asyncio.run(seed_favorites(settings, create_schema=not native))
    database = DatabaseManager(settings)
    app = FastAPI()
    app.include_router(router)
    app.include_router(crm_router)
    app.include_router(crm_assortment_router)
    app.include_router(crm_assortment_writes)
    app.state.database = database
    app.state.settings = settings
    app.state.identity_service = build_identity_service(settings)
    with TestClient(app, base_url="https://test") as client:
        client.portal.call(database.startup)
        prefix = uuid4().hex[:12]

        async def seed():
            async with database.session() as session:
                role = await IdentityRepository().get_role(session, RoleName.ADMIN)
                session.add(UserRole(user_id=users[0], role_id=role.id))
                category = CrmGarmentModelCategory(code=prefix.upper(), name=prefix)
                session.add(category)
                await session.flush()
                models = []
                fabrics = []
                for index in range(130):
                    model = CrmGarmentModel(
                        category_id=category.id,
                        code=f"{prefix.upper()}-{index:03}",
                        name=f"{prefix} Модель {index % 7}",
                        base_size_code="M",
                        base_weight_g=500,
                        is_active=index % 3 != 0,
                    )
                    model.sizes = [
                        CrmGarmentSize(
                            code=code,
                            sort_order=i,
                            base_price=Decimal("80"),
                            base_length_cm=72,
                            base_width_cm=64,
                            min_length_cm=60,
                            max_length_cm=90,
                            min_width_cm=50,
                            max_width_cm=80,
                            extra_width_price_per_cm=Decimal("3.25"),
                            is_active=True,
                        )
                        for i, code in enumerate(["M", "L", "XL"][: index % 3 + 1])
                    ]
                    model.sizes.append(
                        CrmGarmentSize(
                            code="ARCHIVED",
                            sort_order=9,
                            base_price=70,
                            base_length_cm=71,
                            base_width_cm=63,
                            is_active=False,
                        )
                    )
                    fabric = CrmFabric(
                        code=f"{prefix.upper()}-{index:03}",
                        name=f"{prefix} Ткань {index % 5}",
                        color_name="СИНИЙ",
                        width_cm=150,
                        cost_per_kg=None if index % 4 == 0 else Decimal(index % 7) * 10,
                        cost_per_meter=Decimal("12.34"),
                        minimum_stock_meters=15,
                        is_active=index % 3 != 0,
                    )
                    models.append(model)
                    fabrics.append(fabric)
                models[-1].name = f"{prefix} МОДЕЛЬ_%\\"
                fabrics[-1].name = f"{prefix} ТКАНЬ_%\\"
                session.add_all([*models, *fabrics])
                await session.flush()
                for index, (model, fabric) in enumerate(zip(models, fabrics, strict=True)):
                    if index % 11:
                        session.add(
                            CrmMaterialBalance(
                                fabric_id=fabric.id,
                                on_hand_meters=(index % 5 + 1) * 10,
                                reserved_meters=5,
                                updated_at=datetime.now(timezone.utc),
                            )
                        )
                    session.add(
                        CrmGarmentFabricRequirement(
                            garment_model_id=model.id,
                            fabric_id=fabric.id,
                            meters_per_unit=Decimal("1.234"),
                            waste_percent=Decimal("2.50"),
                            is_primary=True,
                        )
                    )
                for index, product_id in enumerate(products):
                    await session.execute(
                        update(Product)
                        .where(Product.id == product_id)
                        .values(garment_model_id=models[index % 2].id)
                    )
                code = await issue_code(
                    session,
                    user_id=users[0],
                    station="admin",
                    pepper=settings.identity_otp_pepper.get_secret_value(),
                )
                await session.commit()
                return [row.id for row in models], [row.id for row in fabrics], category.id, code

        models, fabrics, category, code = client.portal.call(seed)
        try:
            authenticated = client.post("/api/production/auth/login", json={"code": code})
            assert authenticated.status_code == 200, authenticated.text
            yield client, prefix, models, fabrics, category, users, tokens
        finally:

            async def cleanup():
                async with database.session() as session:
                    await session.execute(
                        delete(CrmGarmentFabricRequirement).where(
                            CrmGarmentFabricRequirement.garment_model_id.in_(models)
                        )
                    )
                    await session.execute(
                        update(Product)
                        .where(Product.id.in_(products))
                        .values(garment_model_id=None)
                    )
                    await session.execute(
                        delete(CrmMaterialBalance).where(CrmMaterialBalance.fabric_id.in_(fabrics))
                    )
                    await session.execute(
                        delete(CrmGarmentSize).where(CrmGarmentSize.garment_model_id.in_(models))
                    )
                    await session.execute(
                        delete(CrmGarmentModel).where(CrmGarmentModel.id.in_(models))
                    )
                    await session.execute(delete(CrmFabric).where(CrmFabric.id.in_(fabrics)))
                    await session.execute(
                        delete(CrmGarmentModelCategory).where(
                            CrmGarmentModelCategory.id == category
                        )
                    )
                    categories = list(
                        await session.scalars(
                            select(Product.category_id).where(
                                Product.id.in_(products), Product.category_id.is_not(None)
                            )
                        )
                    )
                    await session.execute(delete(Product).where(Product.id.in_(products)))
                    await session.execute(
                        delete(ProductCategory).where(ProductCategory.id.in_(categories))
                    )
                    credential_ids = select(ProductionCredential.id).where(
                        ProductionCredential.user_id.in_(users)
                    )
                    await session.execute(
                        delete(ProductionSession).where(
                            ProductionSession.credential_id.in_(credential_ids)
                        )
                    )
                    await session.execute(
                        delete(ProductionCredential).where(ProductionCredential.user_id.in_(users))
                    )
                    await session.execute(delete(User).where(User.id.in_(users)))
                    await session.commit()

            client.portal.call(cleanup)
            client.portal.call(database.shutdown)


def sort_text(value, client):
    if client.app.state.database.engine.dialect.name == "postgresql":
        return value.lower()
    return value.translate(
        str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
    )


def all_pages(client, kind, params):
    rows = []
    cursor = None
    for _ in range(100):
        response = client.get(
            f"{ROOT}/directory/{kind}", params={**params, **({"cursor": cursor} if cursor else {})}
        )
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        page = response.json()
        assert len(page["items"]) <= params.get("limit", 24)
        rows += page["items"]
        cursor = page["next_cursor"]
        if cursor is None:
            return rows
    raise AssertionError("Continuation did not end")


def test_models_are_compact_searchable_and_sort_with_stable_ties(references):
    client, prefix, models, _, category, _, _ = references
    for sorting in ["name:asc", "name:desc", "code:asc", "sizes:desc", "products:desc"]:
        rows = all_pages(client, "models", {"query": prefix, "sort": sorting})
        assert len(rows) == 130 and {row["id"] for row in rows} == set(models)
        assert all(
            not {"sizes", "catalog_product_ids", "description"}.intersection(row) for row in rows
        )
        field, direction = sorting.split(":")

        def key(row, field=field):
            return (
                {
                    "name": sort_text(row["name"], client),
                    "code": sort_text(row["code"], client),
                    "sizes": row["size_count"],
                    "products": row["product_count"],
                }[field],
                row["id"],
            )

        assert rows == sorted(rows, key=key, reverse=direction == "desc")
    counts = client.get(
        f"{ROOT}/directory/categories/model-categories", params={"query": prefix}
    ).json()["items"]
    assert next(row for row in counts if row["id"] == category)["item_count"] == 130
    selected = client.get(
        f"{ROOT}/directory/selected", params={"kind": "models", "ids": models[-1]}
    ).json()
    assert selected[0]["id"] == models[-1]
    literal = all_pages(client, "models", {"query": "_%\\"})
    assert models[-1] in {row["id"] for row in literal}
    if client.app.state.database.engine.dialect.name == "postgresql":
        assert models[-1] in {
            row["id"] for row in all_pages(client, "models", {"query": f"{prefix} модель_%\\"})
        }


def test_fabrics_use_real_meter_balances_and_all_sort_orders_continue(references):
    client, prefix, _, fabrics, _, _, _ = references
    for sorting in ["name:asc", "code:asc", "stock:asc", "stock:desc", "price:asc", "price:desc"]:
        rows = all_pages(client, "fabrics", {"query": prefix, "sort": sorting})
        assert len(rows) == 130 and {row["id"] for row in rows} == set(fabrics)
        for row in rows:
            if row["balance"]:
                assert Decimal(row["balance"]["available_meters"]) == Decimal(
                    row["balance"]["on_hand_meters"]
                ) - Decimal(row["balance"]["reserved_meters"])
                assert "available_quantity" not in row["balance"]
        field, direction = sorting.split(":")

        def key(row, field=field):
            return (
                {
                    "name": sort_text(row["name"], client),
                    "code": sort_text(row["code"], client),
                    "stock": Decimal((row["balance"] or {}).get("available_meters", "0")),
                    "price": Decimal(row["cost_per_kg"] or "0"),
                }[field],
                row["id"],
            )

        assert rows == sorted(rows, key=key, reverse=direction == "desc")
    for stock in ["low", "available"]:
        rows = all_pages(client, "fabrics", {"query": prefix, "stock": stock})
        assert rows
        assert all(
            (
                Decimal((row["balance"] or {}).get("available_meters", "0"))
                <= Decimal(row["minimum_stock_meters"])
            )
            == (stock == "low")
            for row in rows
        )


def test_cursor_contracts_and_scalar_projection_never_load_editor_collections(references):
    client, prefix, models, _, _, _, tokens = references
    with TestClient(client.app, base_url="https://test") as guest:
        for path in [
            "directory/models",
            "directory/fabrics",
            "directory/fabric-requirements",
            f"models/{models[-1]}",
            f"directory/selected?kind=models&ids={models[-1]}",
        ]:
            assert guest.get(f"{ROOT}/{path}").status_code == 401
            assert guest.get(f"{ROOT}/{path}", headers=tokens[0]).status_code == 401
    first = client.get(f"{ROOT}/directory/models", params={"query": prefix}).json()
    cursor = first["next_cursor"]
    assert cursor
    for params in [
        {"query": prefix, "cursor": cursor, "sort": "sizes:desc"},
        {"query": "changed", "cursor": cursor},
        {"cursor": "bad"},
        {"limit": 101},
        {"cursor": ""},
        {"ignored": "no"},
    ]:
        response = client.get(f"{ROOT}/directory/models", params=params)
        assert response.status_code == 422, response.text
    crossed = client.get(f"{ROOT}/directory/fabrics", params={"query": prefix, "cursor": cursor})
    assert crossed.status_code == 422 and crossed.json()["detail"]["code"] == "invalid_cursor"

    async def projection():
        statements = []

        def capture(conn, cursor, statement, parameters, context, many):
            if statement.lstrip().upper().startswith(("SELECT", "WITH")):
                statements.append(statement)

        engine = client.app.state.database.engine
        event.listen(engine.sync_engine, "before_cursor_execute", capture)
        try:
            async with client.app.state.database.session() as session:
                page = await ReferenceDirectoryService().models(
                    session, ModelDirectoryQuery(query=prefix)
                )
                assert len(page.items) == 24 and len(statements) == 1 and not session.identity_map
                assert (
                    "crm_garment_models.description" not in statements[0]
                    and "crm_garment_sizes.base_width_cm" not in statements[0]
                )
            statements.clear()
            async with client.app.state.database.session() as session:
                page = await ReferenceDirectoryService().fabrics(
                    session, FabricDirectoryQuery(query=prefix)
                )
                assert len(page.items) == 24 and len(statements) == 1 and not session.identity_map
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", capture)

    client.portal.call(projection)


def test_complete_editor_roundtrip_keeps_geometry_prices_and_archived_sizes(references):
    client, _, models, fabrics, _, _, _ = references
    response = client.get(f"{ROOT}/models/{models[-1]}")
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["version"] == 1
    sizes = [row for row in detail["sizes"] if row["is_active"]]
    assert (
        sizes
        and sizes[0]["base_width_cm"] == "64.00"
        and sizes[0]["base_length_cm"] == "72.00"
        and sizes[0]["extra_width_price_per_cm"] == "3.25"
    )
    body = {
        key: detail[key]
        for key in [
            "category_id",
            "code",
            "name",
            "description",
            "base_size_code",
            "fit_model_name",
            "fit_model_height_cm",
            "base_weight_g",
            "size_chart_media_object_id",
            "is_active",
        ]
    }
    body.update(
        name="Changed name only",
        expected_version=1,
        sizes=[
            {key: value for key, value in size.items() if key not in {"id", "version", "is_active"}}
            for size in sizes
        ],
    )
    saved = client.put(f"{ROOT}/models/{models[-1]}", json=body)
    assert saved.status_code == 200, saved.text
    again = client.get(f"{ROOT}/models/{models[-1]}").json()
    assert [
        {k: v for k, v in row.items() if k != "version"}
        for row in again["sizes"]
        if row["is_active"]
    ] == [{k: v for k, v in row.items() if k != "version"} for row in sizes]
    assert all(row["is_active"] for row in again["sizes"])

    async def retained_archive():
        async with client.app.state.database.session() as session:
            return await session.scalar(
                select(CrmGarmentSize.id).where(
                    CrmGarmentSize.garment_model_id == models[-1],
                    CrmGarmentSize.code == "ARCHIVED",
                    CrmGarmentSize.is_active.is_(False),
                )
            )

    assert client.portal.call(retained_archive) is not None
    assert client.put(f"{ROOT}/models/{models[-1]}", json=body).status_code == 409
    rows = all_pages(client, "fabric-requirements", {})
    own = [row for row in rows if row["garment_model_id"] in models]
    assert len(own) == 130 and all(row["garment_model_name"] and row["fabric_name"] for row in own)


def test_model_lock_refreshes_stale_identity_map_and_reports_version_conflict(references):
    from app.modules.crm.reference_schemas import CrmGarmentModelWrite
    from app.modules.crm.reference_service import (
        CrmReferenceService,
        CrmReferenceVersionConflictError,
    )

    client, _, models, _, _, users, _ = references
    identity = models[-1]
    source = client.get(f"{ROOT}/models/{identity}").json()
    source["sizes"] = [size for size in source["sizes"] if size["is_active"]]
    payload = CrmGarmentModelWrite.model_validate(source)

    async def prove():
        async with client.app.state.database.session() as session:
            stale = await session.get(CrmGarmentModel, identity)
            previous = stale.version
            await session.execute(
                update(CrmGarmentModel)
                .where(CrmGarmentModel.id == identity)
                .values(version=previous + 1, name="Concurrent model")
                .execution_options(synchronize_session=False)
            )
            assert stale.version == previous
            with pytest.raises(CrmReferenceVersionConflictError):
                await CrmReferenceService().update_garment_model(
                    session,
                    garment_model_id=identity,
                    expected_version=previous,
                    payload=payload,
                    actor_user_id=users[0],
                )
            assert stale.version == previous + 1
            assert stale.name == "Concurrent model"
            await session.rollback()

    client.portal.call(prove)
    response = client.put(
        f"{ROOT}/models/{identity}", json={**source, "expected_version": source["version"] + 1}
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "crm_reference_version_conflict"
    assert client.get(f"{ROOT}/models/{identity}").json()["version"] == source["version"]


def test_preset_size_choices_page_and_read_selected_archives_without_history(references):
    client, _, models, _, _, _, _ = references
    identity = models[-1]

    async def seed_choices():
        async with client.app.state.database.session() as session:
            await session.execute(
                insert(CrmGarmentSize),
                [
                    {
                        "garment_model_id": identity,
                        "code": f"PAGE-{i:03}",
                        "sort_order": 20 + i,
                        "base_price": 80,
                        "is_active": True,
                    }
                    for i in range(130)
                ],
            )
            await session.execute(
                insert(CrmGarmentSize),
                [
                    {
                        "garment_model_id": identity,
                        "code": f"HISTORY-{i:04}",
                        "sort_order": i,
                        "base_price": 70,
                        "is_active": False,
                    }
                    for i in range(5000)
                ],
            )
            await session.commit()
            expected = list(
                await session.scalars(
                    select(CrmGarmentSize.id)
                    .where(
                        CrmGarmentSize.garment_model_id == identity,
                        CrmGarmentSize.is_active.is_(True),
                    )
                    .order_by(CrmGarmentSize.id)
                )
            )
            archived = await session.scalar(
                select(CrmGarmentSize.id).where(
                    CrmGarmentSize.garment_model_id == identity,
                    CrmGarmentSize.code == "HISTORY-4999",
                )
            )
            foreign = await session.scalar(
                select(CrmGarmentSize.id).where(CrmGarmentSize.garment_model_id == models[0])
            )
            return expected, archived, foreign

    expected, archived, foreign = client.portal.call(seed_choices)
    choices = f"{ROOT}/editor-options"
    ids, cursor = [], None
    for _ in range(10):
        response = client.get(
            f"{choices}/sizes",
            params={"model_id": identity, "limit": 24, **({"cursor": cursor} if cursor else {})},
        )
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        page = response.json()
        assert len(page["items"]) <= 24 and all(row["is_active"] for row in page["items"])
        assert all(set(row) == {"id", "code", "is_active"} for row in page["items"])
        ids.extend(row["id"] for row in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    else:
        raise AssertionError("Size page did not terminate")
    assert ids == expected and len(ids) > 130
    assert client.get(f"{choices}/models/{identity}").json()["sizes"] == []
    selected = client.get(
        f"{choices}/models/{identity}",
        params=[
            ("selected_size_ids", archived),
            ("selected_size_ids", expected[-1]),
            ("selected_size_ids", archived),
        ],
    ).json()
    assert {row["id"] for row in selected["sizes"]} == {archived, expected[-1]}
    assert next(row for row in selected["sizes"] if row["id"] == archived)["is_active"] is False
    assert (
        client.get(f"{choices}/models/{identity}", params={"selected_size_ids": foreign}).json()[
            "sizes"
        ]
        == []
    )
    assert (
        client.get(f"{choices}/sizes", params={"model_id": identity, "query": "page-129"}).json()[
            "items"
        ][0]["id"]
        == expected[-1]
    )
    assert (
        client.get(f"{choices}/sizes", params={"model_id": identity, "query": "_%"}).json()["items"]
        == []
    )
    for params in [
        {},
        {"model_id": 0},
        {"model_id": identity, "limit": 101},
        {"model_id": identity, "cursor": 0},
        {"model_id": identity, "extra": "ignored"},
    ]:
        assert client.get(f"{choices}/sizes", params=params).status_code == 422
    for params in [
        [("selected_size_ids", 0)],
        [("selected_size_ids", archived)] * 201,
        [("unknown", 1)],
    ]:
        assert client.get(f"{choices}/models/{identity}", params=params).status_code == 422

    async def projection():
        statements = []

        def capture(conn, cursor, statement, parameters, context, many):
            if statement.lstrip().upper().startswith(("SELECT", "WITH")):
                statements.append(statement)

        engine = client.app.state.database.engine
        event.listen(engine.sync_engine, "before_cursor_execute", capture)
        try:
            for operation, count in [
                (lambda session: CatalogEditorOptions.models(session, EditorOptionsQuery()), 1),
                (lambda session: CatalogEditorOptions.fabrics(session, EditorOptionsQuery()), 1),
                (lambda session: CatalogEditorOptions.selected_fabrics(session, [1]), 1),
                (
                    lambda session: CatalogEditorOptions.sizes(
                        session, EditorSizeQuery(model_id=identity)
                    ),
                    1,
                ),
                (lambda session: CatalogEditorOptions.model(session, identity), 1),
                (lambda session: CatalogEditorOptions.model(session, identity, [archived]), 2),
            ]:
                statements.clear()
                async with client.app.state.database.session() as session:
                    await operation(session)
                    assert len(statements) == count and not session.identity_map
                    assert all(
                        "description" not in statement
                        and "base_width_cm" not in statement
                        and "cost_per_kg" not in statement
                        for statement in statements
                    )
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", capture)

    client.portal.call(projection)


def test_model_source_excludes_archives_and_rejects_oversized_grid_without_truncation(references):
    client, _, models, _, _, _, tokens = references
    identity = models[-1]
    before = client.get(f"{ROOT}/models/{identity}").json()
    source = f"/api/crm/reference/garment-models/{identity}"
    assert client.get(source, headers=tokens[0]).json() == before

    async def scenario():
        async with client.app.state.database.session() as session:
            await session.execute(
                insert(CrmGarmentSize),
                [
                    {
                        "garment_model_id": identity,
                        "code": f"OLD-{i:04}",
                        "sort_order": i,
                        "base_price": 80,
                        "is_active": False,
                    }
                    for i in range(5000)
                ],
            )
            await session.commit()
        statements = []

        def capture(conn, cursor, statement, parameters, context, many):
            if statement.lstrip().upper().startswith(("SELECT", "WITH")):
                statements.append((statement, parameters))

        engine = client.app.state.database.engine
        event.listen(engine.sync_engine, "before_cursor_execute", capture)
        try:
            async with client.app.state.database.session() as session:
                row = await ReferenceDirectoryService().model(session, identity)
                assert len(row.sizes) == 1 and row.sizes[0].code == "M"
                assert len(statements) == 2 and not session.identity_map
                assert "LIMIT" in statements[1][0] and 101 in statements[1][1]
                assert row.sizes[0].base_width_cm == Decimal("64.00")
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", capture)
        async with client.app.state.database.session() as session:
            await session.execute(
                insert(CrmGarmentSize),
                [
                    {
                        "garment_model_id": identity,
                        "code": f"NEW-{i:03}",
                        "sort_order": i + 1,
                        "base_price": 80,
                        "is_active": True,
                    }
                    for i in range(100)
                ],
            )
            await session.commit()

    client.portal.call(scenario)
    response = client.get(f"{ROOT}/models/{identity}")
    assert response.status_code == 409 and response.json()["detail"]["code"] == "model_size_limit"
    assert response.headers["cache-control"] == "no-store"
    canonical = client.get(source, headers=tokens[0])
    assert canonical.status_code == 409 and canonical.json() == response.json()
    assert canonical.headers["cache-control"] == "no-store"
    rejected = client.put(
        f"{ROOT}/models/{identity}",
        json={**before, "name": "Partial replacement", "expected_version": before["version"]},
    )
    assert rejected.status_code == 409, rejected.text

    async def unchanged():
        async with client.app.state.database.session() as session:
            model = await session.get(CrmGarmentModel, identity)
            assert model.version == before["version"] and model.name == before["name"]
            rows = await session.scalars(
                select(CrmGarmentSize.version).where(
                    CrmGarmentSize.garment_model_id == identity,
                    CrmGarmentSize.is_active.is_(True),
                )
            )
            assert list(rows) == [1] * 101

    client.portal.call(unchanged)


def test_model_command_bounds_history_and_refreshes_reactivated_size_versions(references):
    from sqlalchemy import func, inspect

    from app.modules.crm.reference_models import CrmReferenceEvent
    from app.modules.crm.reference_schemas import CrmGarmentModelWrite
    from app.modules.crm.reference_service import CrmReferenceService

    client, _, models, _, _, users, _ = references
    identity = models[-1]
    source = client.get(f"{ROOT}/models/{identity}").json()
    original = source["sizes"][0]
    body = CrmGarmentModelWrite.model_validate(source).model_dump(mode="json")
    body["sizes"] = [
        {**body["sizes"][0], "code": "OLD-4999", "sort_order": 1},
        {**body["sizes"][0], "code": "NEW", "sort_order": 2},
    ]
    body["base_size_code"] = "OLD-4999"

    async def prove():
        async with client.app.state.database.session() as session:
            await session.execute(
                insert(CrmGarmentSize),
                [
                    {
                        "garment_model_id": identity,
                        "code": f"OLD-{i:04}",
                        "sort_order": i,
                        "base_price": 80,
                        "is_active": False,
                    }
                    for i in range(5000)
                ],
            )
            await session.commit()
        async with client.app.state.database.session() as session:
            stale = await session.scalar(
                select(CrmGarmentSize).where(
                    CrmGarmentSize.garment_model_id == identity,
                    CrmGarmentSize.code == "OLD-4999",
                )
            )
            old_id = stale.id
            await session.execute(
                update(CrmGarmentSize)
                .where(CrmGarmentSize.id == old_id)
                .values(version=7)
                .execution_options(synchronize_session=False)
            )
            assert stale.version == 1
            statements = []

            def capture(conn, cursor, statement, parameters, context, many):
                if statement.lstrip().upper().startswith(("SELECT", "WITH")):
                    statements.append((statement, parameters))

            engine = client.app.state.database.engine
            event.listen(engine.sync_engine, "before_cursor_execute", capture)
            try:
                result = await CrmReferenceService().update_garment_model(
                    session,
                    garment_model_id=identity,
                    expected_version=1,
                    payload=CrmGarmentModelWrite.model_validate(body),
                    actor_user_id=users[0],
                )
                assert result.version == 2
                assert [(size.code, size.is_active) for size in result.sizes] == [
                    ("OLD-4999", True),
                    ("NEW", True),
                ]
                assert result.sizes[0].id == old_id and result.sizes[0].version == 8
                assert stale.version == 8 and stale.is_active
                assert result.sizes[1].version == 1
                assert result.base_width_cm == Decimal("64.00")
                sizes = [
                    row for row in session.identity_map.values() if isinstance(row, CrmGarmentSize)
                ]
                assert len(sizes) <= 3
                parent = await session.get(CrmGarmentModel, identity)
                assert "sizes" in inspect(parent).unloaded
                size_reads = [
                    (sql, args) for sql, args in statements if "FROM crm_garment_sizes" in sql
                ]
                assert len(size_reads) == 2
                assert "LIMIT" in size_reads[0][0] and 101 in size_reads[0][1]
                assert "requested_size_codes" in size_reads[1][0]
                assert not any("count(" in sql.lower() for sql, _ in statements)
            finally:
                event.remove(engine.sync_engine, "before_cursor_execute", capture)
            await session.commit()
        async with client.app.state.database.session() as session:
            old_active = await session.get(CrmGarmentSize, original["id"])
            assert not old_active.is_active and old_active.version == 2
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(CrmGarmentSize)
                    .where(
                        CrmGarmentSize.garment_model_id == identity,
                    )
                )
                == 5003
            )
            untouched = await session.scalar(
                select(CrmGarmentSize).where(
                    CrmGarmentSize.garment_model_id == identity,
                    CrmGarmentSize.code == "OLD-0000",
                )
            )
            assert untouched.version == 1 and not untouched.is_active
            audit = await session.scalar(
                select(CrmReferenceEvent).where(
                    CrmReferenceEvent.entity_type == "garment_model",
                    CrmReferenceEvent.entity_id == identity,
                    CrmReferenceEvent.entity_version == 2,
                )
            )
            assert audit.details == {
                "active_sizes_count": 2,
                "created_sizes_count": 1,
                "reactivated_sizes_count": 1,
                "archived_sizes_count": 1,
            }
        return old_id

    old_id = client.portal.call(prove)
    saved = client.put(f"{ROOT}/models/{identity}", json={**body, "expected_version": 2})
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 3
    assert len(saved.json()["sizes"]) == 2
    assert saved.json()["sizes"][0]["id"] == old_id
    assert saved.json()["sizes"][0]["version"] == 9
    assert len(saved.content) < 5000
    assert saved.json() == client.get(f"{ROOT}/models/{identity}").json()


def test_model_links_and_tech_card_creation_do_not_read_size_history(references):
    from app.modules.crm.reference_schemas import CrmTechCardCreate
    from app.modules.crm.reference_service import CrmReferenceService

    client, prefix, models, _, _, users, _ = references
    identity = models[-1]

    async def prove():
        async with client.app.state.database.session() as session:
            product = Product(title="Linked", slug=prefix + "-command-link", price=80)
            session.add(product)
            await session.flush()
            statements = []

            def capture(conn, cursor, statement, parameters, context, many):
                if statement.lstrip().upper().startswith(("SELECT", "WITH")):
                    statements.append(statement)

            engine = client.app.state.database.engine
            event.listen(engine.sync_engine, "before_cursor_execute", capture)
            try:
                service = CrmReferenceService()
                linked = await service.link_catalog_product(
                    session,
                    garment_model_id=identity,
                    catalog_product_id=product.id,
                    actor_user_id=users[0],
                )
                assert linked.garment_model_id == identity and linked.version == 2
                card = await service.create_tech_card(
                    session,
                    garment_model_id=identity,
                    actor_user_id=users[0],
                    payload=CrmTechCardCreate.model_validate(
                        {
                            "code": prefix + "-CARD",
                            "revision": {
                                "name": "Revision",
                                "checkpoints": [
                                    {"position": 1, "stage_code": "sewing", "name": "Sewing"},
                                ],
                            },
                        }
                    ),
                )
                assert card.garment_model_id == identity
                assert not any("crm_garment_sizes" in sql for sql in statements)
                assert not any(
                    isinstance(row, CrmGarmentSize) for row in session.identity_map.values()
                )
            finally:
                event.remove(engine.sync_engine, "before_cursor_execute", capture)
            await session.rollback()

    client.portal.call(prove)
