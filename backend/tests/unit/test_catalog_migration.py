from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.integrations.minio import MinioStorage
from app.modules.catalog.mapper import CatalogResponseMapper
from app.modules.catalog.migration import (
    CatalogContractComparator,
    CatalogMigrationService,
    InvalidMigrationPlanError,
    LegacyCatalogPlanner,
    TargetCatalogNotEmptyError,
)
from app.modules.catalog.models import CatalogMigrationRun, Product, ProductVariant
from app.modules.catalog.service import CatalogService
from app.modules.media.models import MediaObject
from tests.fakes.minio import FakeMinioClient


def webp_bytes(color: tuple[int, int, int]) -> bytes:
    output = BytesIO()
    Image.new("RGB", (8, 8), color=color).save(output, format="WEBP")
    return output.getvalue()


def create_legacy_catalog(tmp_path: Path) -> tuple[Path, Path]:
    database_path = tmp_path / "legacy.db"
    uploads_path = tmp_path / "uploads"
    uploads_path.mkdir()
    (uploads_path / "first.webp").write_bytes(webp_bytes((10, 20, 30)))
    (uploads_path / "second.webp").write_bytes(webp_bytes((40, 50, 60)))
    (uploads_path / "unused.webp").write_bytes(webp_bytes((70, 80, 90)))

    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                title TEXT,
                price REAL,
                old_price REAL,
                video_src TEXT,
                image_left TEXT,
                image_right TEXT,
                description TEXT,
                composition TEXT,
                model_info TEXT,
                sizes TEXT,
                colors TEXT,
                gallery_images TEXT,
                is_active INTEGER,
                type TEXT,
                weight REAL,
                height REAL,
                width REAL,
                length REAL,
                stock_quantity INTEGER,
                size_chart_img_1 TEXT,
                size_chart_img_2 TEXT,
                desktop_video TEXT,
                desktop_video_poster TEXT,
                desktop_card_images TEXT,
                desktop_slider_images TEXT,
                mobile_card_image TEXT,
                mobile_video_poster TEXT,
                mobile_slider_images TEXT,
                mobile_product_slider_images TEXT,
                mobile_size_chart_first TEXT
            );
            CREATE TABLE product_variants (
                id INTEGER PRIMARY KEY,
                product_id INTEGER,
                size TEXT,
                color TEXT,
                color_hex TEXT,
                stock_quantity INTEGER,
                width_cm REAL,
                height_cm REAL,
                preview_image TEXT,
                images TEXT
            );
            """
        )
        connection.execute(
            """
            INSERT INTO products (
                id, title, price, old_price, description, composition, model_info,
                sizes, colors, is_active, type, weight, height, width, length,
                stock_quantity, desktop_slider_images, mobile_card_image
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                7,
                "Legacy product",
                12000.0,
                15000.0,
                "Description",
                "Composition",
                "Model info",
                "XS,S",
                "black,white",
                1,
                "normal",
                0.75,
                72.0,
                64.0,
                74.0,
                5,
                "/uploads/first.webp,/uploads/second.webp",
                "/uploads/first.webp",
            ),
        )
        connection.execute(
            """
            INSERT INTO product_variants (
                id, product_id, size, color, color_hex, stock_quantity,
                width_cm, height_cm, preview_image, images
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                70,
                7,
                "S",
                "Черный",
                "#1A1A1A",
                3,
                64.0,
                72.0,
                "/uploads/second.webp",
                None,
            ),
        )
        connection.commit()
    return database_path, uploads_path


def target_settings(database_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{database_path}",
        minio_enabled=True,
        minio_access_key="test-access",
        minio_secret_key="test-secret",
        minio_public_base_url="https://cdn.test",
    )


def test_catalog_migration_plan_is_read_only_and_deterministic(tmp_path: Path) -> None:
    database_path, uploads_path = create_legacy_catalog(tmp_path)
    database_before = database_path.read_bytes()
    planner = LegacyCatalogPlanner()

    first = planner.build(database_path, uploads_path)
    second = planner.build(database_path, uploads_path)

    assert first.valid
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
    assert first.report()["counts"] == {
        "products": 1,
        "variants": 1,
        "media_references": 4,
        "unique_media_assets": 2,
        "unused_upload_files": 1,
    }
    assert first.unused_upload_files == ("unused.webp",)
    assert [asset.source_url for asset in first.assets] == [
        "/uploads/first.webp",
        "/uploads/second.webp",
    ]
    assert all(len(asset.checksum_sha256) == 64 for asset in first.assets)
    assert database_path.read_bytes() == database_before

    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE products SET price = 13000 WHERE id = 7")
        connection.commit()
    changed = planner.build(database_path, uploads_path)
    assert changed.fingerprint != first.fingerprint


def test_catalog_migration_applies_once_and_preserves_response_values(
    tmp_path: Path,
) -> None:
    legacy_database, uploads_path = create_legacy_catalog(tmp_path)
    plan = LegacyCatalogPlanner().build(legacy_database, uploads_path)
    settings = target_settings(tmp_path / "target.db")

    async def scenario() -> None:
        database = DatabaseManager(settings)
        client = FakeMinioClient()
        storage = MinioStorage(settings, client=client)
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with database.session() as session:
            result = await CatalogMigrationService(storage).apply(session, plan)

        assert result.fingerprint_sha256 == plan.fingerprint
        assert result.products == 1
        assert result.variants == 1
        assert result.media_assets == 2
        assert result.media_references == 4
        assert [upload["object_name"] for upload in client.uploads] == [
            "uploads/first.webp",
            "uploads/second.webp",
        ]

        async with database.session() as session:
            counts = (
                await session.scalar(select(func.count()).select_from(Product)),
                await session.scalar(select(func.count()).select_from(ProductVariant)),
                await session.scalar(select(func.count()).select_from(MediaObject)),
                await session.scalar(select(func.count()).select_from(CatalogMigrationRun)),
            )
            catalog_service = CatalogService(CatalogResponseMapper(settings))
            detail = await catalog_service.get_product(session, 7)
            comparison = await CatalogContractComparator(catalog_service).compare(
                session,
                plan,
            )

        assert counts == (1, 1, 2, 1)
        assert comparison.matches
        assert comparison.report() == {
            "matches": True,
            "list_products": 1,
            "detail_products": 1,
            "mismatches": [],
        }
        assert detail is not None
        payload = detail.model_dump()
        assert payload["id"] == 7
        assert payload["price"] == 12000.0
        assert payload["sizes"] == "XS,S"
        assert payload["colors"] == "black,white"
        assert payload["desktop_slider_images"] == ("/uploads/first.webp,/uploads/second.webp")
        assert payload["mobile_card_image"] == "/uploads/first.webp"
        assert payload["variants"] == [
            {
                "id": 70,
                "product_id": 7,
                "size": "S",
                "color": "Черный",
                "color_hex": "#1A1A1A",
                "stock_quantity": 3,
                "width_cm": 64.0,
                "height_cm": 72.0,
                "preview_image": "/uploads/second.webp",
                "images": None,
            }
        ]

        uploads_before_retry = len(client.uploads)
        with pytest.raises(TargetCatalogNotEmptyError, match="must be empty"):
            async with database.session() as session:
                await CatalogMigrationService(storage).apply(session, plan)
        assert len(client.uploads) == uploads_before_retry
        await database.shutdown()

    asyncio.run(scenario())


def test_catalog_migration_refuses_changed_or_unsupported_media(tmp_path: Path) -> None:
    legacy_database, uploads_path = create_legacy_catalog(tmp_path)
    planner = LegacyCatalogPlanner()
    plan = planner.build(legacy_database, uploads_path)

    (uploads_path / "first.webp").write_bytes(webp_bytes((1, 2, 3)))
    settings = target_settings(tmp_path / "changed-target.db")

    async def changed_scenario() -> None:
        database = DatabaseManager(settings)
        client = FakeMinioClient()
        storage = MinioStorage(settings, client=client)
        await database.startup()
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        with pytest.raises(InvalidMigrationPlanError, match="changed after dry-run"):
            async with database.session() as session:
                await CatalogMigrationService(storage).apply(session, plan)
        assert client.uploads == []
        await database.shutdown()

    asyncio.run(changed_scenario())

    with sqlite3.connect(legacy_database) as connection:
        connection.execute(
            "UPDATE products SET mobile_card_image = ? WHERE id = 7",
            ("https://external.test/product.webp",),
        )
        connection.commit()

    unsupported = planner.build(legacy_database, uploads_path)
    assert not unsupported.valid
    assert any("require manual mapping" in error for error in unsupported.errors)


def test_catalog_apply_requires_reviewed_dry_run_fingerprint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path, uploads_path = create_legacy_catalog(tmp_path)
    from scripts.migrate_legacy_catalog import main

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "migrate_legacy_catalog",
            "--sqlite-db",
            str(database_path),
            "--uploads-dir",
            str(uploads_path),
            "--apply",
        ],
    )

    assert main() == 2
    report = json.loads(capsys.readouterr().out)
    assert report["apply_error"] == "--expect-fingerprint is required with --apply"
