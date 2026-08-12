from __future__ import annotations

import argparse
import asyncio
import base64
import json

import pytest

from app.core.config import AppEnvironment, Settings
from app.core.rehearsal import (
    StagingRehearsalService,
    private_bucket_policy_allows_public_access,
)
from app.core.rehearsal_repository import PostgresRehearsalSnapshot
from app.integrations.minio import MinioStorage
from scripts.rehearse_staging import run
from tests.fakes.minio import FakeMinioClient

HEAD = "20260812_0027"


class FakeRehearsalRepository:
    def __init__(self, snapshot: PostgresRehearsalSnapshot) -> None:
        self.snapshot = snapshot

    async def inspect_postgres(self, _session: object) -> PostgresRehearsalSnapshot:
        return self.snapshot


def rehearsal_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": AppEnvironment.TEST,
        "public_base_url": "https://app.test",
        "database_enabled": True,
        "database_url": "postgresql+asyncpg://user:password@db.test/app",
        "identity_api_enabled": True,
        "identity_migration_fingerprint": "a" * 64,
        "jwt_secret": "j" * 32,
        "identity_otp_pepper": "p" * 32,
        "notification_encryption_key": base64.urlsafe_b64encode(b"n" * 32)
        .decode("ascii")
        .rstrip("="),
        "crm_api_enabled": True,
        "minio_enabled": True,
        "minio_access_key": "test-access",
        "minio_secret_key": "test-secret",
        "minio_public_base_url": "https://objects.test",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def snapshot(**overrides: object) -> PostgresRehearsalSnapshot:
    values: dict[str, object] = {
        "server_version": "17.5",
        "transaction_read_only": False,
        "in_recovery": False,
        "is_superuser": False,
        "tls_in_use": True,
        "schema_revisions": (HEAD,),
    }
    values.update(overrides)
    return PostgresRehearsalSnapshot(**values)  # type: ignore[arg-type]


def test_rehearsal_passes_safe_postgres_and_private_storage_roundtrip() -> None:
    async def scenario() -> None:
        settings = rehearsal_settings()
        minio = FakeMinioClient()
        service = StagingRehearsalService(FakeRehearsalRepository(snapshot()))  # type: ignore[arg-type]
        report = await service.inspect(
            object(),  # type: ignore[arg-type]
            settings=settings,
            storage=MinioStorage(settings, client=minio),
            expected_environment=AppEnvironment.TEST,
            expected_schema_head=HEAD,
            require_database_tls=True,
            storage_roundtrip=True,
        )

        assert report.healthy
        assert report.storage_roundtrip == "passed"
        assert report.issues == ()
        assert len(minio.uploads) == 1
        assert minio.uploads[0]["bucket_name"] == settings.minio_crm_bucket
        assert minio.removed == [(settings.minio_crm_bucket, str(minio.uploads[0]["object_name"]))]
        rendered = report.to_dict()
        assert "password" not in repr(rendered)
        assert settings.minio_crm_bucket not in repr(rendered)

    asyncio.run(scenario())


def test_rehearsal_reports_flags_schema_database_and_public_policy_drift() -> None:
    async def scenario() -> None:
        settings = rehearsal_settings(crm_writes_enabled=False)
        public_policy = json.dumps(
            {
                "Statement": {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["arn:example:role/reviewer", "*"]},
                    "Action": "s3:GetObject",
                }
            }
        )
        service = StagingRehearsalService(
            FakeRehearsalRepository(  # type: ignore[arg-type]
                snapshot(
                    transaction_read_only=True,
                    is_superuser=True,
                    tls_in_use=False,
                    schema_revisions=("old-head",),
                )
            )
        )
        report = await service.inspect(
            object(),  # type: ignore[arg-type]
            settings=settings,
            storage=MinioStorage(
                settings,
                client=FakeMinioClient(bucket_policy=public_policy),
            ),
            expected_environment=AppEnvironment.TEST,
            expected_schema_head=HEAD,
            require_crm_writes=True,
            require_database_tls=True,
        )

        assert not report.healthy
        assert report.issues == (
            "crm_writes_disabled",
            "database_default_read_only",
            "database_role_is_superuser",
            "database_schema_head_mismatch",
            "database_tls_not_in_use",
            "private_bucket_policy_is_public",
        )

    asyncio.run(scenario())


def test_private_policy_parser_is_conservative_and_rejects_malformed_shape() -> None:
    assert not private_bucket_policy_allows_public_access(None)
    assert not private_bucket_policy_allows_public_access(
        json.dumps(
            {
                "Statement": {
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:example:role/staff"},
                }
            }
        )
    )
    assert private_bucket_policy_allows_public_access(
        json.dumps({"Statement": {"Effect": "Allow", "NotPrincipal": {"AWS": "blocked"}}})
    )
    with pytest.raises(ValueError, match="Statement"):
        private_bucket_policy_allows_public_access(json.dumps({"Statement": "public"}))


def test_production_storage_roundtrip_requires_a_second_explicit_guard() -> None:
    args = argparse.Namespace(
        expect_environment="production",
        storage_roundtrip=True,
        allow_production_storage_roundtrip=False,
        require_crm_writes=False,
        require_crm_files=False,
        require_database_tls=False,
    )
    with pytest.raises(RuntimeError, match="allow-production-storage-roundtrip"):
        asyncio.run(run(args))
