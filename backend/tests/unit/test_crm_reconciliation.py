from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.integrations.minio import MinioStorage
from app.modules.crm.command_models import CrmStaffCommand
from app.modules.crm.file_models import CrmFileAttachment
from app.modules.crm.material_models import CrmMaterialBalance
from app.modules.crm.models import (
    CrmOrderProject,
    CrmProductionUnit,
    CrmProjectEvent,
)
from app.modules.crm.production_models import CrmProductionUnitEvent
from app.modules.crm.reconciliation import CrmReconciliationService
from app.modules.media.models import MediaObject
from tests.fakes.minio import FakeMinioClient

NOW = datetime(2026, 8, 13, 4, 0, tzinfo=timezone.utc)


def _settings(path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
        minio_enabled=True,
        minio_access_key="test-access",
        minio_secret_key="test-secret",
        minio_public_base_url="https://cdn.test",
    )


def test_crm_reconciliation_is_read_only_and_reports_bounded_safe_drift(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "crm-reconciliation.db")
        database = DatabaseManager(settings)
        storage = MinioStorage(settings, client=FakeMinioClient())
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

            async with database.session() as session:
                project = CrmOrderProject(
                    id=1,
                    order_id=1,
                    source_fulfillment_job_id=1,
                    source_payment_attempt_id=1,
                    status="completed",
                    version=1,
                    order_version_snapshot=1,
                    items_count=1,
                    units_count=1,
                    total_price_snapshot=Decimal("100.00"),
                    currency="RUB",
                    payment_succeeded_at_snapshot=NOW,
                    started_at=NOW,
                    closed_at=NOW,
                    created_at=NOW,
                    updated_at=NOW,
                )
                unit = CrmProductionUnit(
                    id=1,
                    project_id=1,
                    order_item_id=1,
                    product_id_snapshot=1,
                    unit_number=1,
                    status="queued",
                    version=1,
                    created_at=NOW,
                    updated_at=NOW,
                )
                session.add_all(
                    [
                        project,
                        unit,
                        CrmProjectEvent(
                            project_id=1,
                            event_key="project:1:version:1",
                            version=1,
                            from_status=None,
                            to_status="completed",
                            reason_code="test_fixture",
                            occurred_at=NOW,
                        ),
                        CrmProductionUnitEvent(
                            production_unit_id=1,
                            event_key="unit:1:version:1",
                            version=1,
                            event_type="initialized",
                            from_status=None,
                            to_status="queued",
                            production_plan_revision_id=None,
                            reason_code="test_fixture",
                            occurred_at=NOW,
                        ),
                    ]
                )
                session.add(
                    CrmMaterialBalance(
                        fabric_id=1,
                        on_hand_meters=Decimal("2.000"),
                        reserved_meters=Decimal("0.000"),
                        version=2,
                        updated_at=NOW,
                    )
                )
                attached_media = MediaObject(
                    id=1,
                    bucket_name=settings.minio_crm_bucket,
                    object_key="crm/production_evidence/2026/08/13/missing.pdf",
                    original_filename="private-name.pdf",
                    content_type="application/pdf",
                    size_bytes=10,
                    checksum_sha256="a" * 64,
                    is_public=False,
                    status="ready",
                    created_at=NOW,
                    updated_at=NOW,
                )
                session.add_all(
                    [
                        attached_media,
                        MediaObject(
                            id=2,
                            bucket_name=settings.minio_crm_bucket,
                            object_key="crm/production_evidence/2026/08/13/orphan.pdf",
                            content_type="application/pdf",
                            size_bytes=10,
                            checksum_sha256="b" * 64,
                            is_public=False,
                            status="ready",
                            created_at=NOW,
                            updated_at=NOW,
                        ),
                        MediaObject(
                            id=3,
                            bucket_name=settings.minio_crm_bucket,
                            object_key="crm/pattern/2026/08/13/pending.pdf",
                            content_type="application/pdf",
                            size_bytes=10,
                            checksum_sha256="c" * 64,
                            is_public=False,
                            status="pending",
                            created_at=NOW - timedelta(hours=1),
                            updated_at=NOW - timedelta(hours=1),
                        ),
                    ]
                )
                await session.flush()
                session.add(
                    CrmFileAttachment(
                        media_object_id=attached_media.id,
                        production_project_id=1,
                        role="production_evidence",
                        sort_order=0,
                        created_at=NOW,
                    )
                )
                session.add(
                    CrmStaffCommand(
                        idempotency_key_sha256="d" * 64,
                        command_sha256="e" * 64,
                        command_type="project.transition",
                        target_id=1,
                        status="processing",
                        created_at=NOW - timedelta(hours=1),
                    )
                )
                await session.commit()

            async with database.session() as session:
                before = (
                    (await session.get(CrmOrderProject, 1)).status,
                    (await session.get(CrmProductionUnit, 1)).status,
                    (await session.get(CrmMaterialBalance, 1)).version,
                    tuple(
                        await session.scalars(select(MediaObject.status).order_by(MediaObject.id))
                    ),
                )

            async with database.session() as session:
                report = await CrmReconciliationService().inspect(
                    session,
                    private_bucket=settings.minio_crm_bucket,
                    storage=storage,
                    max_issues=4,
                    stale_after_seconds=900,
                    now=NOW,
                )
                rendered = report.to_dict()
                assert not report.healthy
                assert report.total_issues == 6
                assert len(report.issues) == 4
                assert rendered["issues_truncated"] is True
                assert rendered["object_verification"] == "performed"
                assert rendered["counts"] == {
                    "projects": 1,
                    "units": 1,
                    "material_balances": 1,
                    "material_reservations": 0,
                    "material_movements": 0,
                    "file_attachments": 1,
                    "private_media": 3,
                    "staff_commands": 1,
                }
                all_codes = {
                    "completed_project_unit_drift",
                    "material_balance_version_drift",
                    "crm_file_object_missing",
                    "crm_private_media_orphan",
                    "crm_private_media_stale_pending",
                    "crm_staff_command_stale_processing",
                }
                assert {issue.code for issue in report.issues} <= all_codes
                assert set(rendered) == {
                    "healthy",
                    "checked_at",
                    "object_verification",
                    "counts",
                    "total_issues",
                    "issues_truncated",
                    "issues",
                }
                assert "private-name.pdf" not in repr(rendered)

            async with database.session() as session:
                after = (
                    (await session.get(CrmOrderProject, 1)).status,
                    (await session.get(CrmProductionUnit, 1)).status,
                    (await session.get(CrmMaterialBalance, 1)).version,
                    tuple(
                        await session.scalars(select(MediaObject.status).order_by(MediaObject.id))
                    ),
                )
                assert after == before
        finally:
            await database.shutdown()

    asyncio.run(scenario())


def test_empty_crm_reconciliation_is_healthy_without_object_probe(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "crm-reconciliation-empty.db")
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                report = await CrmReconciliationService().inspect(
                    session,
                    private_bucket=settings.minio_crm_bucket,
                    now=NOW,
                )
                assert report.healthy
                assert report.total_issues == 0
                assert report.object_verification == "skipped"
                assert report.issues == ()
        finally:
            await database.shutdown()

    asyncio.run(scenario())
