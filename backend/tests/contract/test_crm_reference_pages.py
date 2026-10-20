"""Both HTTP boundaries share bounded projections without sharing credentials."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, update

from app.modules.crm.assortment_models import CrmAccessory, CrmGarmentAccessoryRequirement
from app.modules.crm.assortment_schemas import CrmAccessoryWrite
from app.modules.crm.assortment_service import (
    CrmAssortmentService,
    CrmAssortmentVersionConflictError,
)
from tests.contract.test_reference_directory import ROOT
from tests.contract.test_reference_directory import references as references
from tests.contract.test_stock_directories import stock_records as stock_records

PATHS = {
    "models": "/api/crm/reference/garment-models",
    "fabrics": "/api/crm/reference/fabrics",
    **{
        kind: f"/api/crm/assortment/{kind}"
        for kind in (
            "fabric-requirements",
            "accessory-categories",
            "accessories",
            "accessory-requirements",
            "boxes",
            "packaging-rules",
        )
    },
}


def test_canonical_pages_match_production_and_continue_past_100(stock_records):
    (client, prefix, models, fabrics, _, _, tokens), categories, accessories, boxes, reqs, rules = (
        stock_records
    )
    headers = tokens[0]
    expected = dict(
        models=models,
        fabrics=fabrics,
        accessories=accessories,
        boxes=boxes,
        **{
            "accessory-categories": categories,
            "accessory-requirements": reqs,
            "packaging-rules": rules,
        },
    )
    for kind, path in PATHS.items():
        params = {"limit": 24}
        if kind != "fabric-requirements":
            params["query"] = prefix
        rows = []
        seen = set()
        for _ in range(100):
            response = client.get(path, params=params, headers=headers)
            assert response.status_code == 200, response.text
            assert response.headers["cache-control"] == "no-store"
            data = response.json()
            production = client.get(f"{ROOT}/directory/{kind}", params=params)
            assert production.status_code == 200, production.text
            assert data == production.json()
            assert len(data["items"]) <= 24
            rows.extend(data["items"])
            cursor = data["next_cursor"]
            if cursor is None:
                break
            assert cursor not in seen
            seen.add(cursor)
            params["cursor"] = cursor
        else:
            pytest.fail("Directory cursor did not terminate")
        assert len({row["id"] for row in rows}) == len(rows)
        if kind in expected:
            assert {row["id"] for row in rows} == set(expected[kind])
        else:
            assert {row["garment_model_id"] for row in rows} >= set(models)
        if kind == "models":
            assert all("sizes" not in row and "catalog_product_ids" not in row for row in rows)
        if kind == "accessories":
            assert all("model_ids" not in row for row in rows)
            assert next(row for row in rows if row["id"] == accessories[0])["model_count"] == 130


def test_canonical_reference_auth_filters_and_cursor_boundaries(stock_records):
    (client, prefix, models, _, _, _, tokens), _, accessories, _, _, _ = stock_records
    admin = tokens[0]
    customer = tokens[1]
    source = f"/api/crm/reference/garment-models/{models[-1]}"
    for path in [*PATHS.values(), source]:
        assert client.get(path).status_code == 401
        assert client.get(path, headers=customer).status_code == 403
        assert client.get(path, headers=admin).status_code == 200
    with TestClient(client.app, base_url="https://test") as guest:
        assert guest.get(f"{ROOT}/directory/models", headers=admin).status_code == 401
    detail = client.get(source, headers=admin)
    assert detail.json() == client.get(f"{ROOT}/models/{models[-1]}").json()
    assert detail.headers["cache-control"] == "no-store"
    assert (
        client.get("/api/crm/reference/garment-models/2147483647", headers=admin).status_code == 404
    )
    assert (
        client.get("/api/crm/reference/garment-models/2147483648", headers=admin).status_code == 422
    )
    for kind, path in PATHS.items():
        for invalid in ({"limit": 101}, {"is_active": True}, {"cursor": "bad"}):
            assert client.get(path, params=invalid, headers=admin).status_code == 422
        if kind in {
            "fabric-requirements",
            "accessory-requirements",
            "packaging-rules",
            "accessories",
        }:
            response = client.get(path, params={"garment_model_id": models[-1]}, headers=admin)
            assert response.status_code == 200, response.text
            rows = response.json()["items"]
            assert len(rows) == 1
            assert (
                rows[0]["id"] == accessories[0]
                if kind == "accessories"
                else rows[0]["garment_model_id"] == models[-1]
            )
            for invalid in (0, 2147483648):
                assert (
                    client.get(
                        path, params={"garment_model_id": invalid}, headers=admin
                    ).status_code
                    == 422
                )
    first = client.get(PATHS["models"], params={"query": prefix, "limit": 1}, headers=admin).json()
    cursor = first["next_cursor"]
    for kind, query in (("models", prefix + " changed"), ("fabrics", prefix)):
        rejected = client.get(PATHS[kind], params={"query": query, "cursor": cursor}, headers=admin)
        assert rejected.status_code == 422
        assert rejected.json()["detail"]["code"] == "invalid_cursor"
        assert rejected.headers["cache-control"] == "no-store"
    path = PATHS["accessories"]
    cursor = client.get(path, params={"query": prefix, "limit": 1}, headers=admin).json()[
        "next_cursor"
    ]
    rejected = client.get(
        path,
        params={"query": prefix, "garment_model_id": models[-1], "cursor": cursor},
        headers=admin,
    )
    assert rejected.status_code == 422 and rejected.json()["detail"]["code"] == "invalid_cursor"


def test_accessory_command_preserves_links_without_hydrating_them(stock_records):
    (client, prefix, _, _, _, _, tokens), categories, accessories, _, _, _ = stock_records
    identity = accessories[0]
    page = client.get(f"{ROOT}/directory/accessories", params={"query": prefix}).json()
    card = next(row for row in page["items"] if row["id"] == identity)
    payload = CrmAccessoryWrite.model_validate(
        {**card, "unit_cost": "12.75", "category_id": categories[-2]}
    )
    body = {**payload.model_dump(mode="json"), "expected_version": 1}
    headers = tokens[0]
    statements = []

    def capture(conn, cursor, statement, parameters, context, many):
        statements.append(statement)

    engine = client.app.state.database.engine
    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        response = client.put(
            f"/api/crm/assortment/accessories/{identity}", json=body, headers=headers
        )
        assert response.status_code == 200, response.text
        assert "model_ids" not in response.json() and response.json()["version"] == 2
        assert len(response.content) < 2000
        assert not any("crm_garment_accessory_requirements" in sql for sql in statements)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)
    stale = client.put(f"/api/crm/assortment/accessories/{identity}", json=body, headers=headers)
    assert stale.status_code == 409

    async def unchanged_links_and_fresh_lock():
        async with client.app.state.database.session() as session:
            row = await session.get(CrmAccessory, identity)
            assert row.version == 2 and row.unit_cost == Decimal("12.75")
            count = await session.scalar(
                select(func.count())
                .select_from(CrmGarmentAccessoryRequirement)
                .where(CrmGarmentAccessoryRequirement.accessory_id == identity)
            )
            assert count == 130
            await session.execute(
                update(CrmAccessory)
                .where(CrmAccessory.id == identity)
                .values(version=3)
                .execution_options(synchronize_session=False)
            )
            assert row.version == 2
            with pytest.raises(CrmAssortmentVersionConflictError):
                await CrmAssortmentService().update_accessory(
                    session, accessory_id=identity, expected_version=2, payload=payload
                )
            await session.rollback()

    client.portal.call(unchanged_links_and_fresh_lock)
