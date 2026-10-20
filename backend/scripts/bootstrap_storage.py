"""Provision the three configured S3 buckets using the locked backend SDK."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence

from minio import Minio
from minio.error import MinioException
from urllib3 import PoolManager, Retry, Timeout
from urllib3.exceptions import HTTPError

from app.integrations.storage_bootstrap import StorageBuckets, bootstrap_storage


def required(environment: Mapping[str, str], key: str) -> str:
    value = environment.get(key, "")
    if not value.strip():
        raise ValueError(f"{key} is required")
    return value


def run(environment: Mapping[str, str]) -> None:
    # Validate every name before making any request, especially public/private overlap.
    buckets = StorageBuckets(
        media=required(environment, "MINIO_MEDIA_BUCKET"),
        crm=required(environment, "MINIO_CRM_BUCKET"),
        projects=required(environment, "MINIO_PROJECTS_BUCKET"),
    )
    secure = environment.get("MINIO_SECURE", "false").lower()
    if secure not in {"true", "false"}:
        raise ValueError("MINIO_SECURE must be true or false")
    client = Minio(
        required(environment, "MINIO_ENDPOINT"),
        access_key=required(environment, "MINIO_ACCESS_KEY"),
        secret_key=required(environment, "MINIO_SECRET_KEY"),
        secure=secure == "true",
        http_client=PoolManager(
            timeout=Timeout(connect=5, read=15),
            retries=Retry(total=2, backoff_factor=0.2, status_forcelist=[500, 502, 503, 504]),
        ),
    )
    bootstrap_storage(client, buckets)


def main(argv: Sequence[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    try:
        run(os.environ)
    except (HTTPError, OSError, MinioException, RuntimeError, TypeError, ValueError) as error:
        # SDK errors can include endpoints and credentials. Report only the class.
        print(
            json.dumps({"event": "storage.bootstrap_failed", "error_type": type(error).__name__}),
            file=sys.stderr,
        )
        return 1
    print(json.dumps({"event": "storage.bootstrap_completed", "buckets": 3}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
