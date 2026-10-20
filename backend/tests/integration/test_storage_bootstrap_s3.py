"""Real S3 policy and data checks against a disposable loopback storage server."""

from __future__ import annotations

import json
import os
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

import pytest
from minio import Minio

from app.integrations.storage_bootstrap import StorageBuckets, bootstrap_storage
from scripts.bootstrap_storage import run

pytestmark = pytest.mark.skipif(
    not os.getenv("MINIO_TEST_CONFIG_PATH"), reason="Requires isolated loopback S3 infrastructure"
)


def test_real_bootstrap_retains_data_and_restricts_anonymous_access():
    config = json.loads(Path(os.environ["MINIO_TEST_CONFIG_PATH"]).read_text())
    endpoint = config["endpoint"]
    assert urlsplit(f"http://{endpoint}").hostname in {"127.0.0.1", "localhost", "::1"}
    sdk = Minio(
        endpoint, access_key=config["access_key"], secret_key=config["secret_key"], secure=False
    )
    prefix = "gb-bootstrap-test-" + uuid4().hex[:12]
    buckets = StorageBuckets(prefix + "-media", prefix + "-crm", prefix + "-projects")
    names = [buckets.media, buckets.crm, buckets.projects]
    try:
        for name in [buckets.crm, buckets.projects]:
            sdk.make_bucket(name)
            sdk.put_object(name, "retained.txt", BytesIO(b"retained"), 8, content_type="text/plain")
            # Begin with a deliberately unsafe policy and verify provisioning repairs it.
            sdk.set_bucket_policy(
                name,
                json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {"AWS": ["*"]},
                                "Action": ["s3:GetObject"],
                                "Resource": [f"arn:aws:s3:::{name}/*"],
                            }
                        ],
                    }
                ),
            )
        environment = {
            "MINIO_ENDPOINT": endpoint,
            "MINIO_ACCESS_KEY": config["access_key"],
            "MINIO_SECRET_KEY": config["secret_key"],
            "MINIO_SECURE": "false",
            "MINIO_MEDIA_BUCKET": buckets.media,
            "MINIO_CRM_BUCKET": buckets.crm,
            "MINIO_PROJECTS_BUCKET": buckets.projects,
        }
        run(environment)
        sdk.put_object(
            buckets.media, "retained.txt", BytesIO(b"retained"), 8, content_type="text/plain"
        )
        run(environment)
        for name in names:
            response = sdk.get_object(name, "retained.txt")
            try:
                assert response.read() == b"retained"
            finally:
                response.close()
                response.release_conn()
        with urlopen(f"http://{endpoint}/{buckets.media}/retained.txt", timeout=10) as response:
            assert response.read() == b"retained"
        for name in [buckets.crm, buckets.projects]:
            with pytest.raises(HTTPError) as denied:
                urlopen(f"http://{endpoint}/{name}/retained.txt", timeout=10)
            assert denied.value.code == 403
        # Public media may be read, but cannot be anonymously listed or overwritten.
        for request in [
            Request(f"http://{endpoint}/{buckets.media}/?list-type=2"),
            Request(
                f"http://{endpoint}/{buckets.media}/retained.txt", data=b"changed", method="PUT"
            ),
        ]:
            with pytest.raises(HTTPError) as denied:
                urlopen(request, timeout=10)
            assert denied.value.code == 403
        bootstrap_storage(sdk, buckets)  # The direct boundary is also safe to repeat.
    finally:
        for name in names:
            if sdk.bucket_exists(name):
                for item in sdk.list_objects(name, recursive=True):
                    sdk.remove_object(name, item.object_name)
                sdk.remove_bucket(name)
