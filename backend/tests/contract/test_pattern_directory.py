"""Pattern coverage is a bounded window, independent of total lattice/files/sizes."""

from decimal import Decimal

import pytest
from sqlalchemy import delete, event, select, update

from app.modules.crm.assortment_models import CrmGarmentPattern
from app.modules.crm.assortment_router import router as crm_router
from app.modules.crm.assortment_schemas import CrmGarmentPatternWrite
from app.modules.crm.assortment_service import (
    CrmAssortmentService,
    CrmAssortmentVersionConflictError,
)
from app.modules.crm.pattern_directory_schemas import (
    PatternFileQuery,
    PatternGridQuery,
    PatternModelQuery,
    PatternSizeQuery,
)
from app.modules.crm.pattern_directory_service import PatternDirectoryService
from app.modules.crm.reference_models import CrmGarmentModel, CrmGarmentSize
from app.modules.identity.factory import build_identity_service
from app.modules.media.models import MediaObject
from tests.contract.test_reference_directory import ROOT, all_pages, sort_text
from tests.contract.test_reference_directory import references as references


@pytest.fixture
def pattern_records(references):
    client, prefix, models, _, _, _, _ = references
    client.app.include_router(crm_router)
    client.app.state.identity_service = build_identity_service(client.app.state.settings)

    async def seed():
        async with client.app.state.database.session() as session:
            media = MediaObject(
                provider="minio",
                bucket_name="private",
                object_key=f"patterns/{prefix}.pdf",
                original_filename="pattern.pdf",
                content_type="application/pdf",
                size_bytes=1024,
                checksum_sha256="a" * 64,
                is_public=False,
                status="ready",
            )
            session.add(media)
            await session.flush()
            sizes = list(
                await session.scalars(
                    select(CrmGarmentSize)
                    .where(CrmGarmentSize.garment_model_id.in_(models))
                    .order_by(CrmGarmentSize.id)
                )
            )
            first = {
                model: next(row for row in sizes if row.garment_model_id == model and row.is_active)
                for model in models
            }
            large = first[models[-1]]
            large.min_width_cm, large.max_width_cm = Decimal("50.25"), Decimal("550.25")
            large.min_length_cm, large.max_length_cm = Decimal("60.35"), Decimal("560.35")
            large.allow_standard_sleeve = large.allow_height_sleeve = True
            await session.execute(
                update(CrmGarmentModel)
                .where(CrmGarmentModel.id == models[-1])
                .values(is_active=True)
            )
            extra = [
                CrmGarmentSize(
                    garment_model_id=models[-1],
                    code=f"OLD-{i:03}",
                    sort_order=100 + i // 2,
                    base_price=80,
                    is_active=False,
                )
                for i in range(128)
            ]
            session.add_all(extra)
            rows = []
            for index, model in enumerate(models):
                size = first[model]
                for number in range(130 if index == 129 else 1):
                    width, length = (
                        size.min_width_cm + 2 * (number % 20),
                        size.min_length_cm + 2 * (number // 20),
                    )
                    rows.append(
                        CrmGarmentPattern(
                            code=f"{prefix.upper()}-PAT-{index:03}-{number:03}",
                            name=f"{prefix} ФАЙЛ_%\\"
                            if index == 129 and number == 129
                            else "Сохранённое имя",
                            garment_model_id=model,
                            garment_size_id=size.id,
                            media_object_id=media.id,
                            grid_key=f"{size.code}:{width:.2f}:{length:.2f}:standard",
                            sleeve_variant="standard",
                            width_cm=width,
                            length_cm=length,
                            is_active=number % 5 != 0,
                        )
                    )
            archived = next(
                row for row in sizes if row.garment_model_id == models[-1] and not row.is_active
            )
            for size, width, length, suffix in [
                (large, Decimal("1000"), Decimal("1000"), "OLD-GRID"),
                (archived, Decimal("50"), Decimal("60"), "ARCHIVED"),
            ]:
                rows.append(
                    CrmGarmentPattern(
                        code=f"{prefix.upper()}-{suffix}",
                        name="Исторический файл",
                        garment_model_id=models[-1],
                        garment_size_id=size.id,
                        media_object_id=media.id,
                        grid_key=f"{size.code}:{width:.2f}:{length:.2f}:standard",
                        sleeve_variant="standard",
                        width_cm=width,
                        length_cm=length,
                        is_active=False,
                    )
                )
            session.add_all(rows)
            await session.commit()
            return media.id, large.id, [row.id for row in rows], [row.id for row in extra]

    media, size, patterns, extra = client.portal.call(seed)
    try:
        yield references, media, size, patterns, extra
    finally:

        async def cleanup():
            async with client.app.state.database.session() as session:
                await session.execute(
                    delete(CrmGarmentPattern).where(CrmGarmentPattern.garment_model_id.in_(models))
                )
                await session.execute(delete(CrmGarmentSize).where(CrmGarmentSize.id.in_(extra)))
                await session.execute(delete(MediaObject).where(MediaObject.id == media))
                await session.commit()

        client.portal.call(cleanup)


def test_pattern_pages_include_models_files_and_archived_sizes_after_100(pattern_records):
    (client, prefix, models, _, _, _, _), _, size, patterns, _ = pattern_records
    records = all_pages(client, "pattern-models", {"query": prefix})
    assert len(records) == 130
    large = next(row for row in records if row["id"] == models[-1])
    assert (
        large["required_count"] == "126002"
        and large["uploaded_count"] == 130
        and large["pattern_count"] == 132
    ), large
    assert "sizes" not in large and "patterns" not in large
    for sort in ["model:asc", "model:desc", "code:asc", "code:desc"]:
        rows = all_pages(client, "pattern-models", {"query": prefix, "sort": sort})
        assert rows == sorted(
            records,
            key=lambda row: (
                sort_text(row["name" if sort.startswith("model") else "code"], client),
                row["id"],
            ),
            reverse=sort.endswith(":desc"),
        )
    files = all_pages(client, "patterns", {"model_id": models[-1]})
    assert len(files) == 132 and any(not row["size_is_active"] for row in files)
    assert all(row["garment_model_name"] == large["name"] for row in files)
    for sort in ["id:desc", "code:asc"]:
        rows = all_pages(client, "patterns", {"model_id": models[-1], "sort": sort})
        assert rows == sorted(
            files,
            key=lambda row: (
                (row["id"], row["id"])
                if sort == "id:desc"
                else (sort_text(row["code"], client), row["id"])
            ),
            reverse=sort == "id:desc",
        )
    sizes = all_pages(client, "pattern-sizes", {"model_id": models[-1]})
    assert len(sizes) == 130 and sizes[0]["id"] == size
    assert len(all_pages(client, "patterns", {"model_id": models[-1], "active": True})) == 104
    response = client.get(f"{ROOT}/directory/patterns", params={"query": "файл_%\\"})
    assert response.status_code == 200
    assert len(response.json()["items"]) == (
        1 if client.app.state.database.engine.dialect.name == "postgresql" else 0
    )
    first = client.get(
        f"{ROOT}/directory/pattern-models", params={"query": prefix, "limit": 1}
    ).json()
    for kind, params in [
        ("pattern-models", {"query": prefix, "pattern_active": True}),
        ("pattern-models", {"query": prefix, "sort": "code:desc"}),
        ("patterns", {"query": prefix}),
    ]:
        bad = client.get(
            f"{ROOT}/directory/{kind}", params={**params, "cursor": first["next_cursor"]}
        )
        assert bad.status_code == 422 and bad.json()["detail"]["code"] == "invalid_cursor"
    assert len(patterns) == 261


def test_grid_windows_are_exact_bounded_and_versioned(pattern_records):
    (client, _, models, _, _, _, _), _, size, _, extra = pattern_records
    url = f"{ROOT}/models/{models[-1]}/pattern-coverage"
    response = client.get(url)
    assert response.status_code == 200, response.text
    row = response.json()
    assert row["size"]["id"] == size and row["width_values"] == [
        "50.25",
        "52.25",
        "54.25",
        "56.25",
        "58.25",
        "60.25",
    ]
    assert row["length_values"] == ["60.35", "62.35", "64.35", "66.35", "68.35", "70.35"]
    assert (
        row["width_count"] == row["length_count"] == 251
        and row["width_pages"] == row["length_pages"] == 42
    )
    assert (
        len(row["items"]) == 36
        and row["uploaded_count"] == 130
        and row["required_count"] == "126002"
    )
    last = client.get(
        url,
        params={"size_id": size, "width_page": 41, "length_page": 41, "expected_size_version": 1},
    ).json()
    assert (
        last["width_values"][-1] == "550.25"
        and last["length_values"][-1] == "560.35"
        and len(last["items"]) == 0
    )
    assert client.get(url, params={"width_page": 9999}).status_code == 422
    assert client.get(url, params={"unknown": 1}).status_code == 422
    assert client.get(f"{ROOT}/models/{models[0]}/pattern-size/{size}").status_code == 404

    async def change():
        async with client.app.state.database.session() as session:
            await session.execute(
                update(CrmGarmentSize).where(CrmGarmentSize.id == size).values(version=2)
            )
            await session.commit()

    client.portal.call(change)
    assert client.get(url, params={"size_id": size, "expected_size_version": 1}).status_code == 409

    async def huge():
        async with client.app.state.database.session() as session:
            await session.execute(
                update(CrmGarmentSize)
                .where(CrmGarmentSize.id.in_([size, *extra[:2]]))
                .values(
                    is_active=True,
                    min_width_cm=Decimal("0.25"),
                    min_length_cm=Decimal("0.35"),
                    max_width_cm=Decimal("99999999.99"),
                    max_length_cm=Decimal("99999999.99"),
                    allow_standard_sleeve=True,
                    allow_height_sleeve=True,
                )
            )
            await session.commit()

    client.portal.call(huge)
    huge_row = client.get(
        f"{ROOT}/directory/pattern-models", params={"model_id": models[-1]}
    ).json()["items"][0]
    expected = (
        (int((Decimal("99999999.99") - Decimal("0.25")) // 2) + 1)
        * (int((Decimal("99999999.99") - Decimal("0.35")) // 2) + 1)
        * 2
        * 3
    )
    assert int(huge_row["required_count"]) == expected and expected > 2**53, (huge_row, expected)
    assert len(client.get(url).json()["width_values"]) == 6


def test_pattern_reads_use_scalar_queries_and_keep_authority(pattern_records):
    (client, prefix, models, _, _, _, tokens), _, size, patterns, _ = pattern_records
    source = client.get(f"{ROOT}/patterns/{patterns[0]}")
    assert source.status_code == 200 and source.headers["cache-control"] == "no-store"
    assert source.json()["pattern"]["name"] == "Сохранённое имя"
    crm = client.get(
        "/api/crm/assortment/patterns", params={"model_id": models[-1]}, headers=tokens[0]
    )
    assert crm.status_code == 200 and len(crm.json()["items"]) == 24 and crm.json()["next_cursor"]
    assert client.get("/api/crm/assortment/patterns", headers=tokens[1]).status_code == 403
    assert client.get("/api/crm/assortment/patterns").status_code == 401
    cookie = client.cookies.get("gb_production_session")
    client.cookies.clear()
    for path in [
        "directory/pattern-models",
        "directory/patterns",
        f"directory/pattern-sizes?model_id={models[-1]}",
        f"patterns/{patterns[0]}",
        f"models/{models[-1]}/pattern-coverage",
    ]:
        assert client.get(f"{ROOT}/{path}").status_code == 401
        assert client.get(f"{ROOT}/{path}", headers=tokens[0]).status_code == 401
    client.cookies.set("gb_production_session", cookie)

    async def prove():
        statements = []

        def capture(conn, cursor, statement, parameters, context, many):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        engine = client.app.state.database.engine
        event.listen(engine.sync_engine, "before_cursor_execute", capture)
        try:
            for kind, query in [
                ("pattern-models", PatternModelQuery(query=prefix)),
                ("patterns", PatternFileQuery(model_id=models[-1])),
                ("pattern-sizes", PatternSizeQuery(model_id=models[-1])),
            ]:
                statements.clear()
                async with client.app.state.database.session() as session:
                    result = await PatternDirectoryService().page(session, kind, query)
                    assert (
                        len(result.items) == 24
                        and len(statements) == 1
                        and not session.identity_map
                    )
            statements.clear()
            async with client.app.state.database.session() as session:
                grid = await PatternDirectoryService().coverage(
                    session, models[-1], PatternGridQuery(size_id=size)
                )
                assert len(statements) == 4 and len(grid.items) <= 72 and not session.identity_map
            statements.clear()
            async with client.app.state.database.session() as session:
                editor = await PatternDirectoryService().editor(session, patterns[0])
                assert (
                    editor.pattern.id == patterns[0]
                    and len(statements) == 3
                    and not session.identity_map
                )
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", capture)

    client.portal.call(prove)


def test_pattern_commands_recheck_versions_geometry_and_media(pattern_records):
    (client, _, models, _, _, _, _), media, size, patterns, _ = pattern_records
    source = client.get(f"{ROOT}/patterns/{patterns[129]}").json()["pattern"]
    assert source["garment_model_id"] == models[-1]
    body = {key: value for key, value in source.items() if key not in {"id", "version", "grid_key"}}
    body.update(code=source["code"] + "-EDIT", expected_version=1)
    saved = client.put(f"{ROOT}/patterns/{source['id']}", json=body)
    assert saved.status_code == 200, saved.text
    assert (
        saved.json()["name"] == source["name"]
        and saved.json()["width_cm"] == "50.25"
        and saved.json()["length_cm"] == "60.35"
        and saved.json()["media_object_id"] == media
    )
    assert client.put(f"{ROOT}/patterns/{source['id']}", json=body).status_code == 409
    assert (
        client.put(
            f"{ROOT}/patterns/{source['id']}",
            json={**body, "expected_version": 2, "width_cm": "51.25"},
        ).status_code
        == 409
    )
    assert (
        client.put(
            f"{ROOT}/patterns/{source['id']}",
            json={**body, "expected_version": 2, "media_object_id": 2147483647},
        ).status_code
        == 409
    )

    async def stale():
        db = client.app.state.database
        service = CrmAssortmentService()
        async with db.session() as old:
            record = await old.get(CrmGarmentPattern, source["id"])
            assert record.version == 2
            async with db.session() as session:
                await service.update_pattern(
                    session,
                    pattern_id=record.id,
                    expected_version=2,
                    payload=CrmGarmentPatternWrite.model_validate(
                        {key: value for key, value in body.items() if key != "expected_version"}
                    ),
                )
                await session.commit()
            with pytest.raises(CrmAssortmentVersionConflictError):
                await service.update_pattern(
                    old,
                    pattern_id=record.id,
                    expected_version=2,
                    payload=CrmGarmentPatternWrite.model_validate(
                        {key: value for key, value in body.items() if key != "expected_version"}
                    ),
                )

    client.portal.call(stale)
