from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from io import BytesIO
from typing import Any, Protocol
from urllib.parse import quote

from anyio import to_thread
from fastapi import HTTPException, Request
from minio import Minio
from minio.error import S3Error
from urllib3.exceptions import HTTPError

from app.core.config import Settings, get_settings
from app.core.exceptions import ConfigurationError


class SyncMinioClient(Protocol):
    def bucket_exists(self, bucket_name: str) -> bool: ...

    def put_object(
        self,
        bucket_name: str,
        object_name: str,
        data: BytesIO,
        length: int,
        content_type: str,
    ) -> Any: ...

    def remove_object(self, bucket_name: str, object_name: str) -> None: ...

    def stat_object(self, bucket_name: str, object_name: str) -> Any | None: ...

    def get_bucket_policy(self, bucket_name: str) -> str: ...

    def presigned_get_object(
        self,
        bucket_name: str,
        object_name: str,
        expires: timedelta,
        response_headers: dict[str, str] | None = None,
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class StoredObject:
    bucket_name: str
    object_key: str
    etag: str | None
    version_id: str | None
    public_url: str | None


class MinioStorage:
    """Async application boundary around the synchronous MinIO Python SDK."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: SyncMinioClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.enabled = self.settings.minio_enabled
        self._client = client

    @property
    def backend_name(self) -> str:
        return "minio" if self.enabled else "legacy"

    @property
    def client(self) -> SyncMinioClient:
        if self._client is None:
            raise ConfigurationError("MinIO client has not been started")
        return self._client

    async def startup(self) -> None:
        if not self.enabled or self._client is not None:
            return

        self._client = Minio(
            endpoint=self.settings.minio_endpoint.strip(),
            access_key=self.settings.require_secret("minio_access_key", "MINIO_ACCESS_KEY"),
            secret_key=self.settings.require_secret("minio_secret_key", "MINIO_SECRET_KEY"),
            secure=self.settings.minio_secure,
        )

    async def shutdown(self) -> None:
        self._client = None

    async def ping(self) -> bool:
        if not self.enabled or self._client is None:
            return False
        try:
            for bucket_name in (
                self.settings.minio_media_bucket,
                self.settings.minio_crm_bucket,
            ):
                exists = await to_thread.run_sync(
                    partial(self._client.bucket_exists, bucket_name=bucket_name)
                )
                if not exists:
                    return False
            return True
        except (HTTPError, OSError, S3Error):
            return False

    async def put_object(
        self,
        *,
        object_key: str,
        data: bytes,
        content_type: str,
    ) -> StoredObject:
        self._validate_object_key(object_key)
        if not data:
            raise ValueError("Object data must not be empty")
        if len(data) > self.settings.media_max_upload_bytes:
            raise ValueError("Object exceeds MEDIA_MAX_UPLOAD_BYTES")

        result = await to_thread.run_sync(
            partial(
                self.client.put_object,
                bucket_name=self.settings.minio_media_bucket,
                object_name=object_key,
                data=BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
        )
        return StoredObject(
            bucket_name=self.settings.minio_media_bucket,
            object_key=object_key,
            etag=getattr(result, "etag", None),
            version_id=getattr(result, "version_id", None),
            public_url=self.public_url(object_key),
        )

    async def put_private_crm_object(
        self,
        *,
        object_key: str,
        data: bytes,
        content_type: str,
    ) -> StoredObject:
        return await self._put_object(
            bucket_name=self.settings.minio_crm_bucket,
            object_key=object_key,
            data=data,
            content_type=content_type,
            public_url=None,
        )

    async def remove_object(self, object_key: str) -> None:
        self._validate_object_key(object_key)
        await to_thread.run_sync(
            partial(
                self.client.remove_object,
                bucket_name=self.settings.minio_media_bucket,
                object_name=object_key,
            )
        )

    async def remove_private_crm_object(self, object_key: str) -> None:
        self._validate_object_key(object_key)
        await to_thread.run_sync(
            partial(
                self.client.remove_object,
                bucket_name=self.settings.minio_crm_bucket,
                object_name=object_key,
            )
        )

    async def presigned_get_url(self, object_key: str) -> str:
        self._validate_object_key(object_key)
        return await to_thread.run_sync(
            partial(
                self.client.presigned_get_object,
                bucket_name=self.settings.minio_media_bucket,
                object_name=object_key,
                expires=timedelta(seconds=self.settings.minio_presigned_expire_seconds),
            )
        )

    async def presigned_crm_get_url(self, object_key: str, *, filename: str) -> str:
        self._validate_object_key(object_key)
        encoded_filename = quote(filename or "download", safe="")
        return await to_thread.run_sync(
            partial(
                self.client.presigned_get_object,
                bucket_name=self.settings.minio_crm_bucket,
                object_name=object_key,
                expires=timedelta(seconds=self.settings.minio_presigned_expire_seconds),
                response_headers={
                    "response-content-disposition": (
                        f"attachment; filename*=UTF-8''{encoded_filename}"
                    ),
                    "response-content-type": "application/octet-stream",
                },
            )
        )

    async def private_crm_object_exists(self, object_key: str) -> bool:
        self._validate_object_key(object_key)
        try:
            result = await to_thread.run_sync(
                partial(
                    self.client.stat_object,
                    bucket_name=self.settings.minio_crm_bucket,
                    object_name=object_key,
                )
            )
        except S3Error as error:
            if error.code in {"NoSuchKey", "NoSuchObject"}:
                return False
            raise
        return result is not None

    async def get_private_crm_bucket_policy(self) -> str | None:
        try:
            return await to_thread.run_sync(
                partial(
                    self.client.get_bucket_policy,
                    bucket_name=self.settings.minio_crm_bucket,
                )
            )
        except S3Error as error:
            if error.code in {"NoSuchBucketPolicy", "NoSuchPolicy"}:
                return None
            raise

    async def _put_object(
        self,
        *,
        bucket_name: str,
        object_key: str,
        data: bytes,
        content_type: str,
        public_url: str | None,
    ) -> StoredObject:
        self._validate_object_key(object_key)
        if not data:
            raise ValueError("Object data must not be empty")
        if len(data) > self.settings.media_max_upload_bytes:
            raise ValueError("Object exceeds MEDIA_MAX_UPLOAD_BYTES")
        result = await to_thread.run_sync(
            partial(
                self.client.put_object,
                bucket_name=bucket_name,
                object_name=object_key,
                data=BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
        )
        return StoredObject(
            bucket_name=bucket_name,
            object_key=object_key,
            etag=getattr(result, "etag", None),
            version_id=getattr(result, "version_id", None),
            public_url=public_url,
        )

    def public_url(self, object_key: str) -> str:
        self._validate_object_key(object_key)
        public_base_url = (self.settings.minio_public_base_url or "").rstrip("/")
        if not self.enabled or not public_base_url:
            raise ConfigurationError("MinIO public URL is not configured")
        encoded_key = quote(object_key, safe="/")
        return f"{public_base_url}/{self.settings.minio_media_bucket}/{encoded_key}"

    @staticmethod
    def _validate_object_key(object_key: str) -> None:
        parts = object_key.split("/")
        if (
            not object_key
            or object_key.startswith("/")
            or len(object_key) > 1_024
            or "\\" in object_key
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise ValueError("Invalid object key")


def get_minio_storage(request: Request) -> MinioStorage:
    storage = getattr(request.app.state, "storage", None)
    if not isinstance(storage, MinioStorage) or not storage.enabled:
        raise HTTPException(status_code=503, detail="Object storage is not enabled")
    return storage
