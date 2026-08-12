from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO


@dataclass
class WriteResult:
    etag: str = "etag-1"
    version_id: str = "version-1"


class FakeMinioClient:
    def __init__(self, *, bucket_available: bool = True, bucket_policy: str | None = None) -> None:
        self.bucket_available = bucket_available
        self.bucket_policy = bucket_policy
        self.uploads: list[dict[str, object]] = []
        self.removed: list[tuple[str, str]] = []

    def bucket_exists(self, bucket_name: str) -> bool:
        return self.bucket_available and bucket_name in {
            "garment-buro-test-media",
            "garment-buro-test-crm-private",
        }

    def put_object(
        self,
        bucket_name: str,
        object_name: str,
        data: BytesIO,
        length: int,
        content_type: str,
    ) -> WriteResult:
        self.uploads.append(
            {
                "bucket_name": bucket_name,
                "object_name": object_name,
                "data": data.read(),
                "length": length,
                "content_type": content_type,
            }
        )
        return WriteResult()

    def remove_object(self, bucket_name: str, object_name: str) -> None:
        self.removed.append((bucket_name, object_name))

    def stat_object(self, bucket_name: str, object_name: str) -> object | None:
        if (bucket_name, object_name) in self.removed:
            return None
        if any(
            upload["bucket_name"] == bucket_name and upload["object_name"] == object_name
            for upload in self.uploads
        ):
            return object()
        return None

    def get_bucket_policy(self, bucket_name: str) -> str:
        del bucket_name
        return self.bucket_policy or ""

    def presigned_get_object(
        self,
        bucket_name: str,
        object_name: str,
        expires: timedelta,
        response_headers: dict[str, str] | None = None,
    ) -> str:
        suffix = "&download=1" if response_headers else ""
        return f"https://signed.test/{bucket_name}/{object_name}?ttl={expires.seconds}{suffix}"
