from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from io import BytesIO
from itertools import islice
from typing import Any, Protocol, TypeVar
from urllib.parse import quote, urlsplit, urlunsplit

import certifi
from anyio import to_thread
from fastapi import HTTPException, Request
from minio import Minio
from minio.error import InvalidResponseError, S3Error, ServerError
from urllib3 import PoolManager, Retry, Timeout
from urllib3.exceptions import HTTPError

from app.core.config import Settings, get_settings
from app.core.exceptions import ConfigurationError

T = TypeVar("T")


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

    def remove_object(
        self, bucket_name: str, object_name: str, version_id: str | None = None
    ) -> None: ...

    def list_objects(
        self, bucket_name: str, *, prefix: str, recursive: bool, include_version: bool
    ) -> Iterable[Any]: ...

    def stat_object(self, bucket_name: str, object_name: str) -> Any | None: ...

    def get_object(
        self, bucket_name: str, object_name: str, *, version_id: str | None = None
    ) -> Any: ...

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
        self._http_client: PoolManager | None = None

    @property
    def backend_name(self) -> str:
        return "minio" if self.enabled else "disabled"

    @property
    def client(self) -> SyncMinioClient:
        if self._client is None:
            raise ConfigurationError("MinIO client has not been started")
        return self._client

    async def startup(self) -> None:
        if not self.enabled or self._client is not None:
            return

        http_client = PoolManager(
            timeout=Timeout(
                connect=self.settings.minio_connect_timeout_seconds,
                read=self.settings.minio_read_timeout_seconds,
            ),
            maxsize=10,
            cert_reqs="CERT_REQUIRED",
            ca_certs=os.environ.get("SSL_CERT_FILE") or certifi.where(),
            retries=Retry(
                total=1,
                connect=1,
                read=1,
                status=1,
                other=0,
                redirect=0,
                # PUT/DELETE can create new versions or delete markers after an
                # ambiguous failure. Only a connection failure before sending
                # the request may retry those methods.
                allowed_methods=frozenset({"GET", "HEAD"}),
                status_forcelist=(500, 502, 503, 504),
                backoff_factor=0.2,
                respect_retry_after_header=False,
            ),
        )
        try:
            client = Minio(
                endpoint=self.settings.minio_endpoint.strip(),
                access_key=self.settings.require_secret("minio_access_key", "MINIO_ACCESS_KEY"),
                secret_key=self.settings.require_secret("minio_secret_key", "MINIO_SECRET_KEY"),
                secure=self.settings.minio_secure,
                http_client=http_client,
            )
        except Exception:
            http_client.clear()
            raise
        self._http_client = http_client
        self._client = client

    async def shutdown(self) -> None:
        self._client = None
        http_client, self._http_client = self._http_client, None
        if http_client is not None:
            await to_thread.run_sync(http_client.clear)

    async def _run(self, operation: Callable[[], T]) -> T:
        try:
            return await to_thread.run_sync(operation)
        except (InvalidResponseError, ServerError) as error:
            # A proxy may return HTML rather than S3 XML. Keep such failures
            # inside existing unavailable/503 handlers without exposing its body.
            # S3Error remains intact for callers handling NoSuchKey/NoSuchPolicy.
            raise HTTPError("Object storage request failed") from error

    async def ping(self) -> bool:
        if not self.enabled or self._client is None:
            return False
        try:
            for bucket_name in (
                self.settings.minio_media_bucket,
                self.settings.minio_crm_bucket,
                self.settings.minio_customer_projects_bucket,
            ):
                exists = await self._run(
                    partial(self._client.bucket_exists, bucket_name=bucket_name)
                )
                if not exists:
                    return False
            return not (await self.get_private_customer_bucket_policy() or "").strip()
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

        result = await self._run(
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
        await self._run(
            partial(
                self.client.remove_object,
                bucket_name=self.settings.minio_media_bucket,
                object_name=object_key,
            )
        )

    async def put_private_customer_object(
        self, *, object_key: str, data: bytes, content_type: str
    ) -> StoredObject:
        return await self._put_object(
            bucket_name=self.settings.minio_customer_projects_bucket,
            object_key=object_key,
            data=data,
            content_type=content_type,
            public_url=None,
        )

    async def presigned_project_get_url(self, object_key: str, *, content_type: str) -> str:
        self._validate_object_key(object_key)
        signed_url = await self._run(
            partial(
                self.client.presigned_get_object,
                bucket_name=self.settings.minio_customer_projects_bucket,
                object_name=object_key,
                expires=timedelta(seconds=self.settings.minio_presigned_expire_seconds),
                response_headers={
                    "response-content-disposition": "inline",
                    "response-content-type": content_type,
                    "response-cache-control": "private, no-store",
                },
            )
        )
        return self._externalize_presigned_url(signed_url)

    async def read_private_customer_object(
        self, object_key: str, *, max_bytes: int, version_id: str | None = None
    ) -> bytes:
        self._validate_object_key(object_key)
        if not 1 <= max_bytes <= self.settings.media_max_upload_bytes:
            raise ValueError("Invalid private object read limit")
        return await self._run(
            partial(self._read_private_customer_object, object_key, max_bytes, version_id)
        )

    def _read_private_customer_object(
        self, object_key: str, max_bytes: int, version_id: str | None
    ) -> bytes:
        response = self.client.get_object(
            self.settings.minio_customer_projects_bucket, object_key, version_id=version_id
        )
        try:
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise OSError("Private object exceeds read limit")
            return data
        finally:
            try:
                response.close()
            finally:
                response.release_conn()

    async def get_private_customer_bucket_policy(self) -> str | None:
        return await self._get_bucket_policy(self.settings.minio_customer_projects_bucket)

    async def remove_private_customer_object(self, object_key: str) -> None:
        self._validate_object_key(object_key)
        await self._run(partial(self._remove_customer_versions, object_key))

    def _remove_customer_versions(self, object_key: str) -> None:
        bucket = self.settings.minio_customer_projects_bucket
        # Delete markers alone do not erase data in a versioned bucket. Bound each
        # attempt; the durable SQL tombstone retains exceptionally long histories.
        versions = list(
            islice(
                self.client.list_objects(
                    bucket,
                    prefix=object_key,
                    recursive=True,
                    include_version=True,
                ),
                1001,
            )
        )
        for item in versions[:1000]:
            if item.object_name == object_key:
                self.client.remove_object(bucket, object_key, version_id=item.version_id)
        if len(versions) > 1000:
            raise OSError("Project media version cleanup requires another bounded attempt")

    async def remove_private_crm_object(self, object_key: str) -> None:
        self._validate_object_key(object_key)
        await self._run(
            partial(
                self.client.remove_object,
                bucket_name=self.settings.minio_crm_bucket,
                object_name=object_key,
            )
        )

    async def presigned_get_url(self, object_key: str) -> str:
        self._validate_object_key(object_key)
        signed_url = await self._run(
            partial(
                self.client.presigned_get_object,
                bucket_name=self.settings.minio_media_bucket,
                object_name=object_key,
                expires=timedelta(seconds=self.settings.minio_presigned_expire_seconds),
            )
        )
        return self._externalize_presigned_url(signed_url)

    async def presigned_crm_get_url(self, object_key: str, *, filename: str) -> str:
        self._validate_object_key(object_key)
        encoded_filename = quote(filename or "download", safe="")
        signed_url = await self._run(
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
        return self._externalize_presigned_url(signed_url)

    async def presigned_crm_preview_url(
        self,
        object_key: str,
        *,
        filename: str,
        content_type: str,
    ) -> str:
        self._validate_object_key(object_key)
        encoded_filename = quote(filename or "preview", safe="")
        signed_url = await self._run(
            partial(
                self.client.presigned_get_object,
                bucket_name=self.settings.minio_crm_bucket,
                object_name=object_key,
                expires=timedelta(seconds=self.settings.minio_presigned_expire_seconds),
                response_headers={
                    "response-content-disposition": (
                        f"inline; filename*=UTF-8''{encoded_filename}"
                    ),
                    "response-content-type": content_type,
                },
            )
        )
        return self._externalize_presigned_url(signed_url)

    async def private_crm_object_exists(self, object_key: str) -> bool:
        self._validate_object_key(object_key)
        try:
            result = await self._run(
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
        return await self._get_bucket_policy(self.settings.minio_crm_bucket)

    async def _get_bucket_policy(self, bucket_name: str) -> str | None:
        try:
            return await self._run(
                partial(
                    self.client.get_bucket_policy,
                    bucket_name=bucket_name,
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
        result = await self._run(
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

    def _externalize_presigned_url(self, signed_url: str) -> str:
        """Expose SDK signatures through the configured reverse-proxy prefix.

        The proxy must strip the public prefix and send the internal MinIO Host
        header so the original SigV4 canonical request is preserved.
        """

        public = urlsplit((self.settings.minio_public_base_url or "").rstrip("/"))
        signed = urlsplit(signed_url)
        if not public.scheme or not public.netloc or not signed.path:
            raise ConfigurationError("MinIO public URL is not configured")
        public_path = public.path.rstrip("/")
        return urlunsplit(
            (
                public.scheme,
                public.netloc,
                f"{public_path}{signed.path}",
                signed.query,
                "",
            )
        )

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
