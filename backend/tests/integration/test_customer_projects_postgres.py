from __future__ import annotations

import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, insert, select
from sqlalchemy.exc import IntegrityError

from app.db.session import DatabaseManager
from app.factory import create_app
from app.modules.catalog.models import Product, ProductCategory
from app.modules.customer_projects.models import CustomerProject, CustomerProjectMedia
from app.modules.identity.models import User
from app.modules.media.models import MediaObject
from tests.favorites_scenario import favorite_settings, seed_favorites
from tests.postgres_schema import migrate
from tests.projects_scenario import project_edit, project_payload, seed_project_media

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL test database"
)
PROJECTS = "/api/profile/projects"


def test_postgres_projects_resist_concurrent_creation_edits_and_asset_deletion(postgres_url):
    migrate(postgres_url, "upgrade", "head")
    settings = favorite_settings(postgres_url)
    products, (owner, _), users = asyncio.run(seed_favorites(settings, create_schema=False))
    media = asyncio.run(seed_project_media(settings, products, users))

    async def operation(action):
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.session() as session:
                result = await action(session)
                await session.commit()
                return result
        finally:
            await database.shutdown()

    async def cleanup(session):
        categories = list(
            await session.scalars(
                select(Product.category_id).where(
                    Product.id.in_(products), Product.category_id.is_not(None)
                )
            )
        )
        await session.execute(delete(User).where(User.id.in_(users)))
        await session.execute(delete(Product).where(Product.id.in_(products)))
        await session.execute(delete(MediaObject).where(MediaObject.id.in_(media)))
        await session.execute(delete(ProductCategory).where(ProductCategory.id.in_(categories)))

    try:
        with TestClient(create_app(settings=settings)) as client:
            payload = project_payload(products[0], media[0])
            with ThreadPoolExecutor(max_workers=4) as executor:
                responses = list(
                    executor.map(
                        lambda _: client.post(PROJECTS, headers=owner, json=payload), range(8)
                    )
                )
            assert sorted(response.status_code for response in responses) == [200] * 7 + [201]
            ids = {response.json()["id"] for response in responses}
            assert len(ids) == 1
            project = responses[0].json()
            url = f"{PROJECTS}/{project['id']}"
            with ThreadPoolExecutor(max_workers=2) as executor:
                updates = list(
                    executor.map(
                        lambda title: client.put(
                            url, headers=owner, json=project_edit(project, title=title)
                        ),
                        ("Первое устройство", "Второе устройство"),
                    )
                )
            assert sorted(response.status_code for response in updates) == [200, 409]
            winner = next(response.json() for response in updates if response.status_code == 200)
            assert client.get(url, headers=owner).json() == winner
            receipt_url = f"{PROJECTS}/by-client-key/{payload['client_key']}"
            receipt = client.get(receipt_url, headers=owner)
            assert receipt.status_code == 200
            assert receipt.json() == {
                key: value for key, value in winner.items() if key != "snapshot"
            }

        async def remove_referenced_file(session):
            await session.execute(delete(MediaObject).where(MediaObject.id == media[0]))

        with pytest.raises(IntegrityError):
            asyncio.run(operation(remove_referenced_file))

        async def remove_product(session):
            await session.execute(delete(Product).where(Product.id == products[0]))

        asyncio.run(operation(remove_product))
        with TestClient(create_app(settings=settings)) as second:
            read = second.get(url, headers=owner)
            assert read.status_code == 200
            assert read.json()["product_id"] is None
            assert read.json()["snapshot"] == payload["snapshot"]
            changed = second.put(
                url, headers=owner, json=project_edit(read.json(), title="После удаления товара")
            )
            assert changed.status_code == 200
            assert changed.json()["version"] == 3
            assert (
                second.delete(url, headers=owner, params={"expected_version": 3}).status_code == 204
            )
            assert (
                second.delete(url, headers=owner, params={"expected_version": 3}).status_code == 204
            )
            assert second.get(url, headers=owner).status_code == 404
            assert second.post(PROJECTS, headers=owner, json=payload).status_code == 410
            assert second.get(receipt_url, headers=owner).status_code == 410

        async def check_deleted(session):
            project_row = await session.get(CustomerProject, project["id"])
            assert project_row.snapshot is None
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(CustomerProjectMedia)
                    .where(CustomerProjectMedia.project_id == project["id"])
                )
                == 0
            )
            await session.execute(delete(MediaObject).where(MediaObject.id == media[0]))

        asyncio.run(operation(check_deleted))
    finally:
        asyncio.run(operation(cleanup))


def test_project_list_does_not_scan_deleted_documents_or_load_snapshots(postgres_url):
    migrate(postgres_url, "upgrade", "head")
    settings = favorite_settings(postgres_url)
    products, (owner, _), users = asyncio.run(seed_favorites(settings, create_schema=False))
    now = datetime.now(timezone.utc)

    async def fill_or_cleanup(*, cleanup=False, explain=None):
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.session() as session:
                if explain is not None:
                    connection = await session.connection()
                    return await connection.exec_driver_sql(
                        "EXPLAIN (ANALYZE, FORMAT JSON) " + explain[0], explain[1]
                    )
                if cleanup:
                    categories = list(
                        await session.scalars(
                            select(Product.category_id).where(
                                Product.id.in_(products), Product.category_id.is_not(None)
                            )
                        )
                    )
                    await session.execute(delete(User).where(User.id.in_(users)))
                    await session.execute(delete(Product).where(Product.id.in_(products)))
                    await session.execute(
                        delete(ProductCategory).where(ProductCategory.id.in_(categories))
                    )
                else:
                    document = project_payload(products[0], 1)["snapshot"]
                    await session.execute(
                        insert(CustomerProject),
                        [
                            {
                                "user_id": users[0],
                                "product_id": products[0],
                                "client_key": f"perf-{index}",
                                "creation_sha256": "a" * 64,
                                "kind": "draft",
                                "title": "Проверка списка",
                                "version": 1,
                                "snapshot": document if index < 24 else None,
                                "deleted_at": None if index < 24 else now,
                            }
                            for index in range(10024)
                        ],
                    )
                await session.commit()
        finally:
            await database.shutdown()

    try:
        asyncio.run(fill_or_cleanup())
        queries = []
        application = create_app(settings=settings)
        with TestClient(application) as client:

            def capture(connection, cursor, statement, parameters, context, executemany):
                if (
                    statement.lstrip().startswith("SELECT")
                    and "FROM customer_projects" in statement
                ):
                    queries.append((statement, parameters))

            event.listen(
                application.state.database.engine.sync_engine, "before_cursor_execute", capture
            )
            response = client.get(PROJECTS, headers=owner, params={"limit": 24})
            assert response.status_code == 200
            assert len(response.json()["items"]) == 24
        assert len(queries) == 1
        assert "customer_projects.snapshot" not in queries[0][0]
        result = asyncio.run(fill_or_cleanup(explain=queries[0]))
        plan = result.scalar_one()[0]["Plan"]

        def discarded(node):
            return node.get("Rows Removed by Filter", 0) + sum(
                discarded(child) for child in node.get("Plans", [])
            )

        assert discarded(plan) < 50, {"discarded": discarded(plan), "plan": plan["Node Type"]}
    finally:
        asyncio.run(fill_or_cleanup(cleanup=True))


def test_project_text_is_valid_for_postgres_and_invalid_edits_do_not_mutate(postgres_url):
    migrate(postgres_url, "upgrade", "head")
    settings = favorite_settings(postgres_url)
    products, (owner, _), users = asyncio.run(seed_favorites(settings, create_schema=False))
    media = asyncio.run(seed_project_media(settings, products, users))

    async def cleanup():
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.session() as session:
                categories = list(
                    await session.scalars(
                        select(Product.category_id).where(
                            Product.id.in_(products), Product.category_id.is_not(None)
                        )
                    )
                )
                await session.execute(delete(User).where(User.id.in_(users)))
                await session.execute(delete(Product).where(Product.id.in_(products)))
                await session.execute(delete(MediaObject).where(MediaObject.id.in_(media)))
                await session.execute(
                    delete(ProductCategory).where(ProductCategory.id.in_(categories))
                )
                await session.commit()
        finally:
            await database.shutdown()

    try:
        with TestClient(create_app(settings=settings), raise_server_exceptions=False) as client:
            for invalid in ("hello\u0000world", "\ud800"):
                for field in ("title", "comment"):
                    payload = project_payload(products[0], media[0])
                    if field == "title":
                        payload["title"] = invalid
                    else:
                        payload["snapshot"]["customization"]["comment"] = invalid
                    response = client.post(
                        PROJECTS,
                        headers={**owner, "Content-Type": "application/json"},
                        content=json.dumps(payload),
                    )
                    assert response.status_code == 422, response.text
            assert client.get(PROJECTS, headers=owner).json()["items"] == []
            created = client.post(
                PROJECTS, headers=owner, json=project_payload(products[0], media[0])
            )
            assert created.status_code == 201
            url = f"{PROJECTS}/{created.json()['id']}"
            edit = project_edit(created.json(), title="hello\u0000world")
            assert client.put(url, headers=owner, json=edit).status_code == 422
            assert client.get(url, headers=owner).json() == created.json()
    finally:
        asyncio.run(cleanup())
