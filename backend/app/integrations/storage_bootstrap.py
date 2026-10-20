"""Explicit S3 provisioning; application startup never changes bucket permissions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from minio.error import S3Error
from minio.helpers import check_bucket_name


class BucketClient(Protocol):
    def bucket_exists(self, bucket_name: str) -> bool: ...

    def make_bucket(self, bucket_name: str) -> None: ...

    def get_bucket_policy(self, bucket_name: str) -> str: ...

    def set_bucket_policy(self, bucket_name: str, policy: str) -> None: ...

    def delete_bucket_policy(self, bucket_name: str) -> None: ...


@dataclass(frozen=True, slots=True)
class StorageBuckets:
    media: str
    crm: str
    projects: str

    def __post_init__(self) -> None:
        names = (self.media, self.crm, self.projects)
        for name in names:
            check_bucket_name(name, strict=True, s3_check=True)
        if len(set(names)) != len(names):
            raise ValueError("Public and private buckets must have distinct names")


def _policy(client: BucketClient, bucket: str) -> str:
    try:
        return client.get_bucket_policy(bucket)
    except S3Error as error:
        if error.code in {"NoSuchBucketPolicy", "NoSuchPolicy"}:
            return ""
        raise


def bootstrap_storage(client: BucketClient, buckets: StorageBuckets) -> None:
    """Provision named buckets without touching objects or unrelated buckets.

    Close both private buckets before granting anonymous media reads. A policy
    lookup failure must abort provisioning rather than imply a private bucket.
    """
    for bucket in (buckets.crm, buckets.projects, buckets.media):
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
    for bucket in (buckets.crm, buckets.projects):
        if _policy(client, bucket).strip():
            client.delete_bucket_policy(bucket)
        if _policy(client, bucket).strip():
            raise RuntimeError("Private bucket policy was not removed")
    client.set_bucket_policy(
        buckets.media,
        json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{buckets.media}/*"],
                    }
                ],
            }
        ),
    )
