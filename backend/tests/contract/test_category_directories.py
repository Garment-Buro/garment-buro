"""Two bounded category domains; fresh source, stable selection and real CAS writes."""

from decimal import Decimal

import pytest
from sqlalchemy import delete, event, update

from app.modules.catalog.models import Product, ProductCategory
from app.modules.catalog.router import category_router
from app.modules.catalog.schemas import ProductCategoryWrite
from app.modules.catalog.service import CatalogVersionConflictError, CatalogWriteService
from app.modules.crm.category_directory_schemas import CategoryDirectoryQuery
from app.modules.crm.category_directory_service import CategoryDirectoryService
from app.modules.crm.reference_models import CrmGarmentModel, CrmGarmentModelCategory
from app.modules.crm.reference_schemas import CrmGarmentModelCategoryWrite
from app.modules.crm.reference_service import CrmReferenceService, CrmReferenceVersionConflictError
from app.modules.identity.factory import build_identity_service
from tests.contract.test_reference_directory import ROOT, all_pages, sort_text
from tests.contract.test_reference_directory import references as references


@pytest.fixture
def categories(references):
    client, prefix, models, _, original_category, _, _ = references
    client.app.state.settings = client.app.state.settings.model_copy(
        update={"catalog_writes_enabled": True}
    )
    client.app.state.identity_service = build_identity_service(client.app.state.settings)
    client.app.include_router(category_router)
    owned = {"model-categories": [], "product-categories": [], "products": []}

    async def seed():
        async with client.app.state.database.session() as session:
            for kind, table in [
                ("model-categories", CrmGarmentModelCategory),
                ("product-categories", ProductCategory),
            ]:
                rows = []
                for i in range(130):
                    fields = {
                        "code" if kind == "model-categories" else "slug": f"{prefix}-{kind}-{i:03}"
                    }
                    name = (
                        f"{prefix} cat Категория {i // 2}"
                        if i % 2 == 0
                        else f"{prefix} cat КАТЕГОРИЯ {i // 2}"
                    )
                    if i == 129:
                        name = f"{prefix} cat УЗОР_%\\"
                    rows.append(table(**fields, name=name, is_active=i % 3 != 0, version=7))
                    if kind == "product-categories":
                        rows[-1].description = "Сохранённое описание\n" * 200
                session.add_all(rows)
                await session.flush()
                owned[kind] = [row.id for row in rows]
            await session.execute(
                update(CrmGarmentModel)
                .where(CrmGarmentModel.id.in_(models))
                .values(category_id=owned["model-categories"][-1])
            )
            products = [
                Product(
                    title=f"{prefix} Товар {i}",
                    category_id=category,
                    price=Decimal("80"),
                    is_active=i % 2 == 0,
                )
                for i, category in enumerate(owned["product-categories"])
            ]
            session.add_all(products)
            await session.flush()
            owned["products"] = [row.id for row in products]
            await session.commit()

    client.portal.call(seed)
    try:
        yield references, owned
    finally:

        async def cleanup():
            async with client.app.state.database.session() as session:
                await session.execute(delete(Product).where(Product.id.in_(owned["products"])))
                await session.execute(
                    update(CrmGarmentModel)
                    .where(CrmGarmentModel.id.in_(models))
                    .values(category_id=original_category)
                )
                await session.execute(
                    delete(ProductCategory).where(
                        ProductCategory.id.in_(owned["product-categories"])
                    )
                )
                await session.execute(
                    delete(CrmGarmentModelCategory).where(
                        CrmGarmentModelCategory.id.in_(owned["model-categories"])
                    )
                )
                await session.commit()

        client.portal.call(cleanup)


def test_categories_page_all_rows_with_literal_search_sort_and_bound_cursors(categories):
    (client, prefix, *_), owned = categories
    for kind in ["model-categories", "product-categories"]:
        path = "categories/" + kind
        for sorting in ["name:asc", "name:desc", "code:asc", "code:desc", "id:asc", "id:desc"]:
            rows = all_pages(client, path, {"query": prefix + " cat", "sort": sorting})
            assert len(rows) == 130 and {row["id"] for row in rows} == set(owned[kind])
            assert all(
                set(row) == {"id", "name", "code", "version", "is_active", "item_count"}
                for row in rows
            )
            field, direction = sorting.split(":")
            assert rows == sorted(
                rows,
                key=lambda row: (
                    row["id"] if field == "id" else sort_text(row[field], client),
                    row["id"],
                ),
                reverse=direction == "desc",
            )
        assert len(all_pages(client, path, {"query": prefix + " cat", "active": False})) == 44
        literal = all_pages(client, path, {"query": "_%\\"})
        assert owned[kind][-1] in {row["id"] for row in literal}
        first = client.get(f"{ROOT}/directory/{path}", params={"query": prefix}).json()
        for changes in [{"sort": "id:desc"}, {"active": True}, {"query": "other"}]:
            response = client.get(
                f"{ROOT}/directory/{path}",
                params={"query": prefix, "cursor": first["next_cursor"], **changes},
            )
            assert (
                response.status_code == 422
                and response.json()["detail"]["code"] == "invalid_cursor"
            )
        other = "product-categories" if kind == "model-categories" else "model-categories"
        assert (
            client.get(
                f"{ROOT}/directory/categories/{other}",
                params={"query": prefix, "cursor": first["next_cursor"]},
            ).status_code
            == 422
        )


def test_selected_category_and_joined_names_do_not_depend_on_first_page(categories):
    (client, prefix, models, *_), owned = categories
    for kind in ["model-categories", "product-categories"]:
        identity = owned[kind][-1]
        detail = client.get(f"{ROOT}/{kind}/{identity}")
        assert detail.status_code == 200 and detail.headers["cache-control"] == "no-store"
        row = detail.json()
        assert row["id"] == identity and row["version"] == 7 and row["is_active"] is False
        selected = client.get(f"{ROOT}/directory/selected", params={"kind": kind, "ids": identity})
        assert selected.status_code == 200 and selected.json()[0]["name"] == row["name"]
        assert client.get(f"{ROOT}/{kind}/2147483647").status_code == 404
        page = all_pages(client, "categories/" + kind, {"query": prefix})
        card = next(card for card in page if card["id"] == identity)
        assert card["item_count"] == (130 if kind == "model-categories" else 1)
        if kind == "product-categories":
            assert len(row["description"]) > 1000 and "description" not in card
    cards = all_pages(client, "models", {"query": prefix})
    assert {row["id"] for row in cards} == set(models)
    assert all(row["category_name"] == f"{prefix} cat УЗОР_%\\" for row in cards)
    assert client.get(f"{ROOT}/model-categories").status_code == 405
    assert client.get(f"{ROOT}/product-categories").status_code == 405


def test_category_reads_are_scalar_and_stale_identity_map_cannot_bypass_cas(categories):
    (client, prefix, _, _, _, users, _), owned = categories

    async def prove():
        statements = []

        def record(_conn, _cursor, statement, _params, _ctx, _many):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        engine = client.app.state.database.engine
        event.listen(engine.sync_engine, "before_cursor_execute", record)
        try:
            async with client.app.state.database.session() as session:
                for kind in ["model-categories", "product-categories"]:
                    statements.clear()
                    page = await CategoryDirectoryService().page(
                        session, kind, CategoryDirectoryQuery(query=prefix)
                    )
                    assert (
                        len(page.items) == 24 and len(statements) == 1 and not session.identity_map
                    )
                    statements.clear()
                    assert await CategoryDirectoryService().detail(session, kind, owned[kind][-1])
                    assert len(statements) == 1 and not session.identity_map
            async with client.app.state.database.session() as session:
                for kind, table in [
                    ("model-categories", CrmGarmentModelCategory),
                    ("product-categories", ProductCategory),
                ]:
                    identity = owned[kind][0]
                    stale = await session.get(table, identity)
                    await session.execute(
                        update(table)
                        .where(table.id == identity)
                        .values(version=8)
                        .execution_options(synchronize_session=False)
                    )
                    assert stale.version == 7
                    if kind == "model-categories":
                        with pytest.raises(CrmReferenceVersionConflictError):
                            await CrmReferenceService().update_garment_model_category(
                                session,
                                category_id=identity,
                                expected_version=7,
                                payload=CrmGarmentModelCategoryWrite(name="Changed"),
                                actor_user_id=users[0],
                            )
                    else:
                        with pytest.raises(CatalogVersionConflictError):
                            await CatalogWriteService(client.app.state.settings).update_category(
                                session,
                                category_id=identity,
                                expected_version=7,
                                payload=ProductCategoryWrite(name="Changed", slug="changed"),
                            )
                    assert stale.version == 8
                await session.rollback()
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", record)

    client.portal.call(prove)


def test_category_writes_keep_codes_descriptions_and_role_boundaries(categories):
    (client, prefix, _, _, _, _, tokens), owned = categories
    for kind in ["model-categories", "product-categories"]:
        identity = owned[kind][-1]
        row = client.get(f"{ROOT}/{kind}/{identity}").json()
        body = {
            key: row[key]
            for key in (
                ["name", "is_active"]
                if kind == "model-categories"
                else ["name", "is_active", "slug", "description"]
            )
        }
        body.update(name=f"{prefix} Переименована {kind}", expected_version=7)
        saved = client.put(f"{ROOT}/{kind}/{identity}", json=body)
        assert saved.status_code == 200 and saved.json()["version"] == 8
        assert (
            saved.json()["code" if kind == "model-categories" else "slug"]
            == row["code" if kind == "model-categories" else "slug"]
        )
        if kind == "product-categories":
            assert saved.json()["description"] == row["description"].strip()
        assert client.put(f"{ROOT}/{kind}/{identity}", json=body).status_code == 409
        new_body = {"name": f"{prefix} Новая {kind}", "is_active": True}
        if kind == "product-categories":
            new_body.update(slug=f"{prefix}-new", description="Новое описание")
        created = client.post(f"{ROOT}/{kind}", json=new_body)
        assert created.status_code == 201, created.text
        new_id = created.json()["id"]
        owned[kind].append(new_id)
        assert created.json()["version"] == 1
        assert client.get(f"{ROOT}/{kind}/{new_id}").json() == created.json()
    canonical = client.get("/api/product-categories", headers=tokens[0], params={"query": prefix})
    assert (
        canonical.status_code == 200
        and len(canonical.json()["items"]) == 24
        and canonical.json()["next_cursor"]
    )
    assert client.get("/api/product-categories").status_code == 401
    assert client.get("/api/product-categories", headers=tokens[1]).status_code == 403
    client.cookies.clear()
    for path in [
        "directory/categories/model-categories",
        "directory/categories/product-categories",
        "model-categories/" + str(owned["model-categories"][0]),
        "product-categories/" + str(owned["product-categories"][0]),
    ]:
        assert client.get(f"{ROOT}/{path}").status_code == 401
        assert client.get(f"{ROOT}/{path}", headers=tokens[0]).status_code == 401
