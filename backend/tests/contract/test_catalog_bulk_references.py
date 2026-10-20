"""Large preset writes validate unique references, not one SQL call per SKU."""

from copy import deepcopy

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, event, select, update

from app.modules.catalog.models import CatalogAuditEvent, Product, ProductCategory, ProductVariant
from app.modules.catalog.schemas import PresetWriteRequest, ProductWriteRequest
from app.modules.catalog.service import CatalogReferenceNotFoundError, CatalogWriteService
from app.modules.crm.assortment_models import CrmGarmentFabricRequirement
from app.modules.crm.reference_models import CrmFabric, CrmGarmentModel, CrmGarmentSize
from tests.contract.test_reference_directory import ROOT
from tests.contract.test_reference_directory import references as references


@pytest.fixture
def bulk_preset(references):
    client, prefix, models, fabrics, _, _, _ = references

    async def seed():
        async with client.app.state.database.session() as session:
            category = ProductCategory(slug=f"bulk-{prefix}", name="Bulk category")
            model = CrmGarmentModel(code=f"BULK-{prefix.upper()}", name="Bulk model")
            session.add_all([category, model])
            await session.flush()
            sizes = [
                CrmGarmentSize(garment_model_id=model.id, code=f"S{i:03}", base_price=80)
                for i in range(100)
            ]
            archived = CrmGarmentSize(
                garment_model_id=model.id, code="ARCHIVED", base_price=80, is_active=False
            )
            materials = [
                CrmFabric(
                    code=f"BULK-{prefix.upper()}-{i:03}",
                    name=f"Bulk fabric{i}",
                    color_name="black",
                    width_cm=150,
                )
                for i in range(200)
            ]
            session.add_all([*sizes, archived, *materials])
            await session.flush()
            session.add_all(
                CrmGarmentFabricRequirement(
                    garment_model_id=model.id, fabric_id=fabric.id, meters_per_unit=1
                )
                for fabric in materials
            )
            other_size = await session.scalar(
                select(CrmGarmentSize.id).where(CrmGarmentSize.garment_model_id == models[1])
            )
            await session.commit()
            return (
                category.id,
                model.id,
                [s.id for s in sizes],
                [f.id for f in materials],
                archived.id,
                other_size,
            )

    category, model, sizes, materials, archived, other_size = client.portal.call(seed)
    body = {
        "title": f"{prefix} bulk preset",
        "category_id": category,
        "garment_model_id": model,
        "price": "1234.56",
        "variants": [
            {
                "size": f"S{i % 100:03}",
                "garment_size_id": sizes[i % 100],
                "fabric_id": materials[i],
                "width_cm": "64.25",
                "height_cm": "72.35",
            }
            for i in range(200)
        ],
    }
    try:
        yield client, body, sizes, materials, archived, other_size, models[0], fabrics[1]
    finally:

        async def cleanup():
            async with client.app.state.database.session() as session:
                product_ids = list(
                    await session.scalars(
                        select(Product.id).where(Product.garment_model_id == model)
                    )
                )
                if product_ids:
                    await session.execute(
                        delete(CatalogAuditEvent).where(
                            CatalogAuditEvent.product_id.in_(product_ids)
                        )
                    )
                    await session.execute(delete(Product).where(Product.id.in_(product_ids)))
                await session.execute(
                    delete(CrmGarmentFabricRequirement).where(
                        CrmGarmentFabricRequirement.garment_model_id == model
                    )
                )
                await session.execute(
                    delete(CrmGarmentSize).where(CrmGarmentSize.garment_model_id == model)
                )
                await session.execute(delete(CrmGarmentModel).where(CrmGarmentModel.id == model))
                await session.execute(delete(CrmFabric).where(CrmFabric.id.in_(materials)))
                await session.execute(delete(ProductCategory).where(ProductCategory.id == category))
                await session.commit()

        client.portal.call(cleanup)


def test_200_skus_need_four_scalar_reference_selects_and_no_identity_hydration(bulk_preset):
    client, body, _, materials, _, _, _, _ = bulk_preset

    async def scenario():
        engine = client.app.state.database.engine
        statements = []

        def capture(conn, cursor, statement, parameters, context, many):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append((statement, parameters))

        event.listen(engine.sync_engine, "before_cursor_execute", capture)
        try:
            async with client.app.state.database.session() as session:
                service = CatalogWriteService(client.app.state.settings)
                payload = ProductWriteRequest.model_validate(body)
                await service._validate_product_references(session, payload)
                assert len(statements) == 4 and not session.identity_map
                assert len(statements[2][1]) == 101 and len(statements[3][1]) == 201
                assert "crm_garment_sizes.id IN" in statements[2][0]
                assert "crm_fabrics.id IN" in statements[3][0]
                assert "base_price" not in statements[2][0] and "width_cm" not in statements[3][0]
                # Repetition changes the bound set, never the number of SQL calls.
                for variant in payload.variants:
                    variant.garment_size_id = payload.variants[0].garment_size_id
                    variant.size = payload.variants[0].size
                    variant.fabric_id = materials[0]
                statements.clear()
                await service._validate_product_references(session, payload)
                assert (
                    len(statements) == 4
                    and len(statements[2][1]) == 2
                    and len(statements[3][1]) == 2
                )
                assert not session.identity_map
                statements.clear()
                await service._validate_product_references(
                    session, ProductWriteRequest(title="No references", price=1)
                )
                assert not statements
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", capture)

    client.portal.call(scenario)


def test_bulk_validation_rejects_every_invalid_reference_without_stale_orm_fallback(bulk_preset):
    client, body, sizes, materials, archived, other_size, inactive_model, unlinked_fabric = (
        bulk_preset
    )

    async def scenario():
        async with client.app.state.database.session() as session:
            service = CatalogWriteService(client.app.state.settings)
            cases = []
            for changes in (
                {"garment_size_id": archived},
                {"garment_size_id": other_size},
                {"garment_size_id": 2147483647},
                {"size": "Wrong code"},
                {"fabric_id": unlinked_fabric},
                {"fabric_id": 2147483647},
            ):
                invalid = deepcopy(body)
                invalid["variants"][-1].update(changes)
                cases.append(invalid)
            cases += [
                {**body, "garment_model_id": inactive_model},
                {**body, "garment_model_id": None},
                {**body, "category_id": 2147483647},
            ]
            for invalid in cases:
                with pytest.raises(CatalogReferenceNotFoundError):
                    await service._validate_product_references(
                        session, ProductWriteRequest.model_validate(invalid)
                    )
            # Existing cached objects must not make inactive DB references valid.
            for table, identity in (
                (ProductCategory, body["category_id"]),
                (CrmGarmentModel, body["garment_model_id"]),
                (CrmGarmentSize, sizes[-1]),
                (CrmFabric, materials[-1]),
            ):
                row = await session.get(table, identity)
                assert row.is_active is True
                await session.execute(
                    update(table)
                    .where(table.id == identity)
                    .values(is_active=False)
                    .execution_options(synchronize_session=False)
                )
                assert row.is_active is True
                with pytest.raises(CatalogReferenceNotFoundError):
                    await service._validate_product_references(
                        session, ProductWriteRequest.model_validate(body)
                    )
                await session.rollback()

    client.portal.call(scenario)


def test_real_200_variant_create_update_preserves_skus_ids_stock_and_rejects_bad_tail(bulk_preset):
    client, body, _, _, archived, _, _, _ = bulk_preset
    client.app.state.settings = client.app.state.settings.model_copy(
        update={"catalog_writes_enabled": True}
    )
    empty = client.post(f"{ROOT}/products", json={**body, "variants": []})
    assert empty.status_code == 201 and empty.json()["variants"] == [], empty.text
    assert empty.json()["media_assets"] == []
    created = client.post(f"{ROOT}/products", json=body)
    assert created.status_code == 201, created.text
    product = created.json()
    assert len(product["variants"]) == 200
    ids = [row["id"] for row in product["variants"]]
    identity = product["id"]

    async def assign_skus():
        async with client.app.state.database.session() as session:
            rows = list(
                await session.scalars(
                    select(ProductVariant).where(ProductVariant.product_id == identity)
                )
            )
            for row in rows:
                row.sku = f"BULK-{identity}-{row.id}"
                row.stock_quantity = 7
            await session.commit()

    client.portal.call(assign_skus)
    changed = deepcopy(body)
    changed["title"] += " changed"
    changed["expected_version"] = 1
    for item, variant_id in zip(changed["variants"], ids, strict=True):
        item["id"] = variant_id
    changed["variants"].reverse()
    response = client.put(f"{ROOT}/products/{identity}", json=changed)
    assert response.status_code == 200 and response.json()["version"] == 2, response.text
    detail = client.get(f"{ROOT}/products/{identity}").json()
    assert [row["id"] for row in detail["variants"]] == ids
    assert all(
        row["sku"] == f"BULK-{identity}-{row['id']}" and row["stock_quantity"] == 7
        for row in detail["variants"]
    )
    assert all(row["width_cm"] == 64.25 and row["height_cm"] == 72.35 for row in detail["variants"])
    invalid = deepcopy(changed)
    invalid["expected_version"] = 2
    invalid["variants"][-1]["garment_size_id"] = archived
    rejected = client.put(f"{ROOT}/products/{identity}", json=invalid)
    assert rejected.status_code == 409, rejected.text
    assert client.get(f"{ROOT}/products/{identity}").json() == detail
    assert client.put(f"{ROOT}/products/{identity}", json=changed).status_code == 409


@pytest.mark.parametrize(
    "field", ["category_id", "garment_model_id", "garment_size_id", "fabric_id"]
)
def test_catalog_reference_ids_fit_database_integer_boundary(field):
    body = {"title": "Boundary", "price": 1}
    target = body if field in {"category_id", "garment_model_id"} else {}
    if target is not body:
        body["variants"] = [target]
    for invalid in (0, -1, 2147483648):
        target[field] = invalid
        with pytest.raises(ValidationError):
            ProductWriteRequest.model_validate(body)
    target[field] = 2147483647
    ProductWriteRequest.model_validate(body)
    if field == "garment_model_id":
        target[field] = 2147483648
        with pytest.raises(ValidationError):
            PresetWriteRequest.model_validate(body)
