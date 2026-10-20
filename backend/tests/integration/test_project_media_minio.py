"""Requires a disposable loopback MinIO server and migrated test PostgreSQL."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from minio import Minio
from PIL import Image
from sqlalchemy import delete, select

from app.core.config import Settings
from app.db.session import DatabaseManager
from app.factory import create_app
from app.modules.catalog.models import Product, ProductCategory
from app.modules.identity.models import User
from app.modules.media.models import MediaObject
from tests.favorites_scenario import favorite_settings, seed_favorites
from tests.postgres_schema import migrate
from tests.projects_scenario import project_payload

pytestmark = pytest.mark.skipif(
    not os.getenv("MINIO_TEST_CONFIG_PATH") or not os.getenv("SCHEMA_TEST_POSTGRES_URL"),
    reason="Requires isolated MinIO and PostgreSQL test infrastructure",
)


@pytest.fixture
def real_storage():
    config = json.loads(Path(os.environ["MINIO_TEST_CONFIG_PATH"]).read_text())
    endpoint = config["endpoint"]
    assert urlsplit(f"http://{endpoint}").hostname in {"127.0.0.1", "localhost", "::1"}
    sdk = Minio(
        endpoint, access_key=config["access_key"], secret_key=config["secret_key"], secure=False
    )

    # Exercise the same path stripping/internal Host contract as the storage proxy.
    class Proxy(BaseHTTPRequestHandler):
        def do_GET(self):
            if not self.path.startswith("/assets/"):
                self.send_error(404)
                return
            try:
                upstream = urlopen(
                    Request(f"http://{endpoint}{self.path[7:]}", headers={"Host": endpoint}),
                    timeout=15,
                )
            except HTTPError as error:
                upstream = error
            with upstream:
                body = upstream.read()
                self.send_response(upstream.status)
                for name in ("Content-Type", "Cache-Control", "Content-Disposition"):
                    value = upstream.headers.get(name)
                    if value:
                        self.send_header(name, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, *args):
            pass  # Signed query strings must never enter test logs.

    proxy = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()
    prefix = f"gb-test-{uuid4().hex[:12]}"
    buckets = [f"{prefix}-test-{suffix}" for suffix in ("media", "crm-private", "projects")]
    try:
        for bucket in buckets:
            sdk.make_bucket(bucket)
        yield config, sdk, prefix, f"http://127.0.0.1:{proxy.server_port}/assets"
    finally:
        for bucket in buckets:
            for obj in sdk.list_objects(bucket, recursive=True):
                sdk.remove_object(bucket, obj.object_name)
            sdk.remove_bucket(bucket)
        proxy.shutdown()
        proxy.server_close()
        thread.join(timeout=5)


def test_private_image_on_real_minio_postgres_and_reverse_proxy(postgres_url, real_storage):
    config, sdk, prefix, public_base = real_storage
    migrate(postgres_url, "upgrade", "head")
    base = favorite_settings(postgres_url)
    settings = Settings(
        _env_file=None,
        **{
            **base.model_dump(),
            "minio_enabled": True,
            "minio_endpoint": config["endpoint"],
            "minio_access_key": config["access_key"],
            "minio_secret_key": config["secret_key"],
            "minio_bucket_prefix": prefix,
            "minio_public_base_url": public_base,
        },
    )
    products, (owner, other), users = asyncio.run(seed_favorites(settings, create_schema=False))
    image = BytesIO()
    Image.new("RGBA", (12, 8), (20, 40, 60, 128)).save(image, format="PNG")

    async def operation(clean=False):
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.session() as session:
                if not clean:
                    return await session.scalar(
                        select(MediaObject).where(
                            MediaObject.uploaded_by_user_id == users[0],
                            MediaObject.bucket_name == settings.minio_customer_projects_bucket,
                        )
                    )
                categories = list(
                    await session.scalars(
                        select(Product.category_id).where(
                            Product.id.in_(products),
                            Product.category_id.is_not(None),
                        )
                    )
                )
                await session.execute(delete(User).where(User.id.in_(users)))
                await session.execute(delete(Product).where(Product.id.in_(products)))
                await session.execute(
                    delete(MediaObject).where(
                        MediaObject.bucket_name == settings.minio_customer_projects_bucket,
                    )
                )
                await session.execute(
                    delete(ProductCategory).where(ProductCategory.id.in_(categories))
                )
                await session.commit()
        finally:
            await database.shutdown()

    try:
        with TestClient(create_app(settings=settings)) as client:
            assert client.get("/health/ready").status_code == 200
            uploaded = client.post(
                "/api/profile/project-media",
                headers=owner,
                files={"file": ("private.png", image.getvalue(), "image/png")},
            )
            assert uploaded.status_code == 201, uploaded.text
            media_id = uploaded.json()["id"]
            access_path = f"/api/profile/project-media/{media_id}/access"
            assert client.get(access_path, headers=other).status_code == 404
            assert client.get(access_path).status_code == 401
            access = client.get(access_path, headers=owner)
            assert access.status_code == 200, access.text
            with urlopen(access.json()["url"], timeout=15) as fetched:
                data = fetched.read()
                assert fetched.headers["Content-Type"] == "image/webp"
                assert fetched.headers["Cache-Control"] == "private, no-store"
            with Image.open(BytesIO(data)) as decoded:
                assert decoded.size == (12, 8)
                assert decoded.getpixel((0, 0)) == (20, 40, 60, 128)
            media = asyncio.run(operation())
            assert media.checksum_sha256 == hashlib.sha256(data).hexdigest()
            assert media.size_bytes == len(data)
            anonymous = f"{public_base}/{media.bucket_name}/{media.object_key}"
            with pytest.raises(HTTPError) as denied:
                urlopen(anonymous, timeout=15)
            assert denied.value.code == 403
            saved = client.post(
                "/api/profile/projects", headers=owner, json=project_payload(products[0], media_id)
            )
            assert saved.status_code == 201, saved.text
            batch = client.get(
                f"/api/profile/projects/{saved.json()['id']}/media?version=1", headers=owner
            )
            assert batch.status_code == 200, batch.text
            assert batch.json()["version"] == 1
            assert [item["id"] for item in batch.json()["items"]] == [media_id]
            with urlopen(batch.json()["items"][0]["url"], timeout=15) as fetched:
                assert fetched.read() == data
        with TestClient(create_app(settings=settings)) as restarted:
            assert restarted.get(access_path, headers=owner).status_code == 200
            assert (
                restarted.get(
                    f"/api/profile/projects/{saved.json()['id']}", headers=owner
                ).status_code
                == 200
            )
            # A misconfigured anonymous policy must close both readiness and writes.
            sdk.set_bucket_policy(
                settings.minio_customer_projects_bucket,
                json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {"AWS": ["*"]},
                                "Action": ["s3:GetObject"],
                                "Resource": [
                                    f"arn:aws:s3:::{settings.minio_customer_projects_bucket}/*"
                                ],
                            }
                        ],
                    }
                ),
            )
            assert restarted.get("/health/ready").status_code == 503
            assert restarted.get(access_path, headers=owner).status_code == 503
            rejected = restarted.post(
                "/api/profile/project-media",
                headers=owner,
                files={"file": ("private.png", image.getvalue(), "image/png")},
            )
            assert rejected.status_code == 503
            sdk.delete_bucket_policy(settings.minio_customer_projects_bucket)
            assert restarted.get("/health/ready").status_code == 200
    finally:
        asyncio.run(operation(clean=True))
