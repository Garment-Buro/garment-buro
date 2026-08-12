from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppEnvironment, Settings
from app.core.rehearsal_repository import RehearsalRepository


class RehearsalStorage(Protocol):
    async def ping(self) -> bool: ...

    async def get_private_crm_bucket_policy(self) -> str | None: ...

    async def put_private_crm_object(
        self,
        *,
        object_key: str,
        data: bytes,
        content_type: str,
    ) -> object: ...

    async def private_crm_object_exists(self, object_key: str) -> bool: ...

    async def presigned_crm_get_url(self, object_key: str, *, filename: str) -> str: ...

    async def remove_private_crm_object(self, object_key: str) -> None: ...


@dataclass(frozen=True, slots=True)
class StagingRehearsalReport:
    healthy: bool
    environment: str
    expected_schema_head: str
    database_server_version: str
    database_tls: bool
    storage_roundtrip: str
    issues: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "healthy": self.healthy,
            "environment": self.environment,
            "expected_schema_head": self.expected_schema_head,
            "database_server_version": self.database_server_version,
            "database_tls": self.database_tls,
            "storage_roundtrip": self.storage_roundtrip,
            "issues": list(self.issues),
        }


class StagingRehearsalService:
    def __init__(self, repository: RehearsalRepository | None = None) -> None:
        self.repository = repository or RehearsalRepository()

    async def inspect(
        self,
        session: AsyncSession,
        *,
        settings: Settings,
        storage: RehearsalStorage,
        expected_environment: AppEnvironment,
        expected_schema_head: str,
        require_crm_writes: bool = False,
        require_crm_files: bool = False,
        require_database_tls: bool = False,
        storage_roundtrip: bool = False,
    ) -> StagingRehearsalReport:
        issues: list[str] = []
        self._inspect_settings(
            settings,
            expected_environment=expected_environment,
            require_crm_writes=require_crm_writes,
            require_crm_files=require_crm_files,
            issues=issues,
        )
        snapshot = await self.repository.inspect_postgres(session)
        if snapshot.schema_revisions != (expected_schema_head,):
            issues.append("database_schema_head_mismatch")
        if snapshot.transaction_read_only:
            issues.append("database_default_read_only")
        if snapshot.in_recovery:
            issues.append("database_is_replica")
        if snapshot.is_superuser:
            issues.append("database_role_is_superuser")
        if require_database_tls and not snapshot.tls_in_use:
            issues.append("database_tls_not_in_use")

        if not await storage.ping():
            issues.append("storage_buckets_unavailable")
        else:
            policy = await storage.get_private_crm_bucket_policy()
            if private_bucket_policy_allows_public_access(policy):
                issues.append("private_bucket_policy_is_public")

        roundtrip_status = "skipped"
        if storage_roundtrip and "storage_buckets_unavailable" not in issues:
            roundtrip_status = "passed" if await self._storage_roundtrip(storage) else "failed"
            if roundtrip_status == "failed":
                issues.append("private_storage_roundtrip_failed")

        return StagingRehearsalReport(
            healthy=not issues,
            environment=settings.app_env.value,
            expected_schema_head=expected_schema_head,
            database_server_version=snapshot.server_version,
            database_tls=snapshot.tls_in_use,
            storage_roundtrip=roundtrip_status,
            issues=tuple(sorted(set(issues))),
        )

    @staticmethod
    def _inspect_settings(
        settings: Settings,
        *,
        expected_environment: AppEnvironment,
        require_crm_writes: bool,
        require_crm_files: bool,
        issues: list[str],
    ) -> None:
        if settings.app_env != expected_environment:
            issues.append("environment_mismatch")
        if not settings.database_enabled:
            issues.append("database_disabled")
        if not (settings.database_url or "").startswith(("postgresql://", "postgres://")):
            if not (settings.database_url or "").startswith("postgresql+asyncpg://"):
                issues.append("database_is_not_postgresql")
        if not settings.minio_enabled:
            issues.append("storage_disabled")
        if not settings.identity_api_enabled:
            issues.append("identity_api_disabled")
        if not settings.crm_api_enabled:
            issues.append("crm_api_disabled")
        if require_crm_writes and not settings.crm_writes_enabled:
            issues.append("crm_writes_disabled")
        if require_crm_files and not settings.crm_files_enabled:
            issues.append("crm_files_disabled")
        public_url = urlsplit(settings.public_base_url)
        if public_url.scheme != "https" or not public_url.netloc:
            issues.append("public_base_url_is_not_https")
        storage_url = urlsplit(settings.minio_public_base_url or "")
        if storage_url.scheme != "https" or not storage_url.netloc:
            issues.append("storage_public_url_is_not_https")

    @staticmethod
    async def _storage_roundtrip(storage: RehearsalStorage) -> bool:
        object_key = f"rehearsal/private/{uuid4().hex}.txt"
        checks_passed = False
        try:
            await storage.put_private_crm_object(
                object_key=object_key,
                data=b"staging-rehearsal",
                content_type="text/plain",
            )
            if not await storage.private_crm_object_exists(object_key):
                return False
            signed_url = await storage.presigned_crm_get_url(
                object_key,
                filename="staging-rehearsal.txt",
            )
            parsed_url = urlsplit(signed_url)
            checks_passed = parsed_url.scheme == "https" and bool(
                parsed_url.netloc and parsed_url.query
            )
        finally:
            await storage.remove_private_crm_object(object_key)
        return checks_passed and not await storage.private_crm_object_exists(object_key)


def private_bucket_policy_allows_public_access(policy: str | None) -> bool:
    if not policy:
        return False
    payload = json.loads(policy)
    statements = payload.get("Statement", []) if isinstance(payload, dict) else []
    if isinstance(statements, dict):
        statements = [statements]
    if not isinstance(statements, list):
        raise ValueError("Private bucket policy Statement must be an object or array")
    for statement in statements:
        if not isinstance(statement, dict) or statement.get("Effect") != "Allow":
            continue
        principal = statement.get("Principal")
        if _contains_public_principal(principal) or "NotPrincipal" in statement:
            return True
    return False


def _contains_public_principal(value: object) -> bool:
    if value == "*":
        return True
    if isinstance(value, dict):
        return any(_contains_public_principal(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_public_principal(item) for item in value)
    return False
