"""Large stock directories never hydrate all model links to render a card."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event

from app.modules.crm.assortment_models import (
    CrmAccessory,
    CrmAccessoryCategory,
    CrmGarmentAccessoryRequirement,
    CrmGarmentPackagingRule,
    CrmPackagingBox,
)
from app.modules.crm.stock_directory_schemas import (
    AccessoryCategoryQuery,
    AccessoryDirectoryQuery,
    AccessoryRequirementQuery,
    BoxDirectoryQuery,
    PackagingRuleQuery,
)
from app.modules.crm.stock_directory_service import StockDirectoryService
from tests.contract.test_reference_directory import ROOT, all_pages, sort_text
from tests.contract.test_reference_directory import references as references


@pytest.fixture
def stock_records(references):
    client, prefix, models, _, _, _, _ = references

    async def seed():
        async with client.app.state.database.session() as session:
            categories = [
                CrmAccessoryCategory(
                    code=f"{prefix.upper()}-C{i:03}",
                    name=f"{prefix} Категория {i % 7}",
                    description=f"Описание категории {i}",
                    is_active=i % 3 != 0,
                )
                for i in range(130)
            ]
            session.add_all(categories)
            await session.flush()
            categories[-2].is_active = True
            accessories = [
                CrmAccessory(
                    category_id=categories[i].id,
                    code=f"{prefix.upper()}-A{i:03}",
                    name=f"{prefix} Фурнитура {i % 7}",
                    unit_cost=Decimal(i % 7) + Decimal("0.25"),
                    stock_quantity=i % 5,
                    minimum_stock_quantity=2,
                    is_active=i % 3 != 0 or i == 0,
                )
                for i in range(130)
            ]
            boxes = [
                CrmPackagingBox(
                    code=f"{prefix.upper()}-B{i:03}",
                    name=f"{prefix} Коробка {i % 7}",
                    inner_length_cm=Decimal("30.25"),
                    inner_width_cm=Decimal("20.35"),
                    inner_height_cm=Decimal("10.45"),
                    max_items=i % 5 + 2,
                    unit_cost=Decimal(i % 7) + Decimal("0.35"),
                    stock_quantity=i % 5,
                    minimum_stock_quantity=2,
                    is_active=i % 3 != 0,
                )
                for i in range(130)
            ]
            accessories[-1].name = f"{prefix} ФУРНИТУРА_%\\"
            boxes[-1].name = f"{prefix} КОРОБКА_%\\"
            session.add_all([*accessories, *boxes])
            await session.flush()
            requirements = [
                CrmGarmentAccessoryRequirement(
                    garment_model_id=model,
                    accessory_id=accessories[0].id,
                    quantity_per_unit=Decimal("1.234"),
                    is_optional=i % 2 == 0,
                    notes="Сохранить заметку",
                )
                for i, model in enumerate(models)
            ]
            rules = [
                CrmGarmentPackagingRule(
                    garment_model_id=model, box_id=boxes[i].id, max_items=1, priority=i % 4
                )
                for i, model in enumerate(models)
            ]
            session.add_all([*requirements, *rules])
            await session.flush()
            await session.commit()
            return (
                [row.id for row in categories],
                [row.id for row in accessories],
                [row.id for row in boxes],
                [row.id for row in requirements],
                [row.id for row in rules],
            )

    categories, accessories, boxes, requirements, rules = client.portal.call(seed)
    try:
        yield references, categories, accessories, boxes, requirements, rules
    finally:

        async def cleanup():
            async with client.app.state.database.session() as session:
                await session.execute(
                    delete(CrmGarmentAccessoryRequirement).where(
                        CrmGarmentAccessoryRequirement.id.in_(requirements)
                    )
                )
                await session.execute(
                    delete(CrmGarmentPackagingRule).where(CrmGarmentPackagingRule.id.in_(rules))
                )
                await session.execute(delete(CrmAccessory).where(CrmAccessory.id.in_(accessories)))
                await session.execute(delete(CrmPackagingBox).where(CrmPackagingBox.id.in_(boxes)))
                await session.execute(
                    delete(CrmAccessoryCategory).where(CrmAccessoryCategory.id.in_(categories))
                )
                await session.commit()

        client.portal.call(cleanup)


def test_all_stock_categories_and_capacity_orders_continue_without_truncation(stock_records):
    (client, prefix, _, _, _, _, _), categories, accessories, boxes, _, _ = stock_records
    for kind, ids, sorts in [
        (
            "accessories",
            accessories,
            ["name:asc", "code:asc", "stock:asc", "stock:desc", "price:asc", "price:desc"],
        ),
        (
            "boxes",
            boxes,
            [
                "name:asc",
                "code:asc",
                "stock:asc",
                "stock:desc",
                "price:asc",
                "price:desc",
                "capacity:asc",
                "capacity:desc",
            ],
        ),
        ("accessory-categories", categories, ["name:asc", "code:asc"]),
    ]:
        for sorting in sorts:
            rows = all_pages(client, kind, {"query": prefix, "sort": sorting})
            assert len(rows) == 130 and {row["id"] for row in rows} == set(ids)
            field, direction = sorting.split(":")

            def key(row, field=field):
                values = {
                    "name": sort_text(row["name"], client),
                    "code": sort_text(row["code"], client),
                    "stock": row.get("stock_quantity", 0),
                    "price": Decimal(row.get("unit_cost", "0")),
                    "capacity": row.get("max_items", 0),
                }
                return values[field], row["id"]

            assert rows == sorted(rows, key=key, reverse=direction == "desc")
        hidden = all_pages(client, kind, {"query": prefix, "active": "false"})
        assert hidden and all(row["is_active"] is False for row in hidden)
        if kind != "accessory-categories":
            for stock in ["low", "available"]:
                rows = all_pages(client, kind, {"query": prefix, "stock": stock})
                assert rows and all(
                    (row["stock_quantity"] <= row["minimum_stock_quantity"]) == (stock == "low")
                    for row in rows
                )
    rows = all_pages(client, "accessories", {"query": prefix})
    first = next(row for row in rows if row["id"] == accessories[0])
    assert first["model_count"] == 130 and "model_ids" not in first
    category = all_pages(client, "accessories", {"category_id": categories[-1]})
    assert [row["id"] for row in category] == [accessories[-1]]
    for kind, last in [("accessories", accessories[-1]), ("boxes", boxes[-1])]:
        assert last in {row["id"] for row in all_pages(client, kind, {"query": "_%\\"})}
        if client.app.state.database.engine.dialect.name == "postgresql":
            word = "фурнитура" if kind == "accessories" else "коробка"
            assert last in {
                row["id"] for row in all_pages(client, kind, {"query": f"{prefix} {word}_%\\"})
            }


def test_joined_rule_names_and_priority_survive_more_than_one_page(stock_records):
    (client, prefix, _, _, _, _, _), _, _, _, requirements, rules = stock_records
    for kind, ids in [("accessory-requirements", requirements), ("packaging-rules", rules)]:
        rows = all_pages(client, kind, {"query": prefix})
        assert len(rows) == 130 and {row["id"] for row in rows} == set(ids)
        if kind == "packaging-rules":
            assert rows == sorted(rows, key=lambda row: (row["priority"], row["id"]))
            assert all(
                row["garment_model_name"]
                and row["box_name"]
                and row["box_capacity"] >= row["max_items"]
                for row in rows
            )
        else:
            assert [row["id"] for row in rows] == sorted(ids, reverse=True)
            assert all(
                row["garment_model_name"]
                and row["accessory_name"]
                and row["quantity_per_unit"] == "1.234"
                for row in rows
            )
        first = client.get(f"{ROOT}/directory/{kind}", params={"query": prefix}).json()
        invalid = client.get(
            f"{ROOT}/directory/{kind}", params={"query": "changed", "cursor": first["next_cursor"]}
        )
        assert invalid.status_code == 422 and invalid.json()["detail"]["code"] == "invalid_cursor"


def test_selected_metadata_access_and_one_scalar_statement_for_every_stock_page(stock_records):
    (client, prefix, _, _, _, _, tokens), categories, accessories, boxes, _, _ = stock_records
    endpoints = [
        "accessories",
        "boxes",
        "accessory-categories",
        "accessory-requirements",
        "packaging-rules",
    ]
    with TestClient(client.app, base_url="https://test") as guest:
        for kind in endpoints:
            assert guest.get(f"{ROOT}/directory/{kind}").status_code == 401
            assert guest.get(f"{ROOT}/directory/{kind}", headers=tokens[0]).status_code == 401
    for kind, value in [
        ("accessories", accessories[-1]),
        ("boxes", boxes[-1]),
        ("accessory-categories", categories[-1]),
    ]:
        response = client.get(f"{ROOT}/directory/selected", params={"kind": kind, "ids": value})
        assert response.status_code == 200, response.text
        row = response.json()[0]
        assert row["id"] == value
        assert (row["max_items"] is not None) == (kind == "boxes")
    cursor = client.get(f"{ROOT}/directory/accessories", params={"query": prefix}).json()[
        "next_cursor"
    ]
    for kind in endpoints:
        for params in [{"limit": 101}, {"cursor": ""}, {"unknown": "no"}, {"cursor": "bad"}]:
            assert client.get(f"{ROOT}/directory/{kind}", params=params).status_code == 422
    crossed = client.get(f"{ROOT}/directory/boxes", params={"cursor": cursor, "query": prefix})
    assert crossed.status_code == 422 and crossed.json()["detail"]["code"] == "invalid_cursor"

    async def prove():
        statements = []

        def capture(conn, cursor, statement, parameters, context, many):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        engine = client.app.state.database.engine
        event.listen(engine.sync_engine, "before_cursor_execute", capture)
        try:
            for kind, query_type in [
                ("accessories", AccessoryDirectoryQuery),
                ("boxes", BoxDirectoryQuery),
                ("accessory-categories", AccessoryCategoryQuery),
                ("accessory-requirements", AccessoryRequirementQuery),
                ("packaging-rules", PackagingRuleQuery),
            ]:
                statements.clear()
                async with client.app.state.database.session() as session:
                    page = await StockDirectoryService().page(
                        session, kind, query_type(query=prefix)
                    )
                    assert (
                        len(page.items) == 24 and len(statements) == 1 and not session.identity_map
                    )
                    assert "crm_garment_models.description" not in statements[0]
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", capture)

    client.portal.call(prove)


def test_native_stock_commands_keep_values_and_recheck_versions_and_box_capacity(stock_records):
    (client, prefix, models, _, _, _, _), _, accessories, boxes, requirements, rules = stock_records
    accessory = next(
        row
        for row in all_pages(client, "accessories", {"query": prefix})
        if row["id"] == accessories[-2]
    )
    body = {
        key: value
        for key, value in accessory.items()
        if key not in {"id", "version", "category_name", "model_count"}
    }
    body.update(name="Only name changed", expected_version=1)
    saved = client.put(f"{ROOT}/accessories/{accessories[-2]}", json=body)
    assert saved.status_code == 200, saved.text
    assert (
        saved.json()["unit_cost"] == accessory["unit_cost"]
        and saved.json()["stock_quantity"] == accessory["stock_quantity"]
    )
    assert client.put(f"{ROOT}/accessories/{accessories[-2]}", json=body).status_code == 409
    box = next(
        row for row in all_pages(client, "boxes", {"query": prefix}) if row["id"] == boxes[-2]
    )
    body = {key: value for key, value in box.items() if key not in {"id", "version"}}
    body.update(name="Changed box name", expected_version=1)
    saved = client.put(f"{ROOT}/boxes/{boxes[-2]}", json=body)
    assert saved.status_code == 200, saved.text
    assert [
        saved.json()[key]
        for key in [
            "inner_length_cm",
            "inner_width_cm",
            "inner_height_cm",
            "unit_cost",
            "stock_quantity",
        ]
    ] == [
        box[key]
        for key in [
            "inner_length_cm",
            "inner_width_cm",
            "inner_height_cm",
            "unit_cost",
            "stock_quantity",
        ]
    ]
    assert client.put(f"{ROOT}/boxes/{boxes[-2]}", json=body).status_code == 409
    expense = client.put(
        f"{ROOT}/accessory-requirements/{requirements[1]}",
        json={
            "expected_version": 1,
            "garment_model_id": models[1],
            "accessory_id": accessories[0],
            "quantity_per_unit": "1.234",
            "is_optional": True,
            "notes": "Сохранить заметку",
        },
    )
    assert expense.status_code == 200, expense.text
    assert expense.json()["quantity_per_unit"] == "1.234"
    bad = client.put(
        f"{ROOT}/packaging-rules/{rules[-2]}",
        json={
            "expected_version": 1,
            "garment_model_id": models[-2],
            "box_id": boxes[-2],
            "max_items": box["max_items"] + 1,
            "priority": 2,
        },
    )
    assert bad.status_code == 409, bad.text
