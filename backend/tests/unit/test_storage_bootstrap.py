from __future__ import annotations

import json

import pytest
from minio.error import MinioException, S3Error

from app.integrations.storage_bootstrap import StorageBuckets, bootstrap_storage
from scripts import bootstrap_storage as command


def s3_error(code):
    return S3Error(None, code, "synthetic-private-credential", "resource", "request", "host")


class BucketStore:
    def __init__(self):
        self.buckets = {"unrelated": {"retained": b"bytes"}}
        self.policies = {"unrelated": "unchanged"}
        self.ignore_delete = False
        self.policy_error = None

    def bucket_exists(self, bucket):
        return bucket in self.buckets

    def make_bucket(self, bucket):
        assert bucket not in self.buckets
        self.buckets[bucket] = {}

    def get_bucket_policy(self, bucket):
        if self.policy_error:
            raise s3_error(self.policy_error)
        if bucket not in self.policies:
            raise s3_error("NoSuchBucketPolicy")
        return self.policies[bucket]

    def delete_bucket_policy(self, bucket):
        if not self.ignore_delete:
            self.policies.pop(bucket, None)

    def set_bucket_policy(self, bucket, policy):
        self.policies[bucket] = policy


def test_idempotent_setup_preserves_objects_and_closes_private_policies():
    client = BucketStore()
    buckets = StorageBuckets("gb-test-media", "gb-test-crm", "gb-test-projects")
    for name in (buckets.crm, buckets.projects):
        client.buckets[name] = {"retained": b"private"}
        client.policies[name] = '{"Statement":[{"Effect":"Allow"}]}'
    bootstrap_storage(client, buckets)
    bootstrap_storage(client, buckets)
    assert client.buckets == {
        "unrelated": {"retained": b"bytes"},
        buckets.crm: {"retained": b"private"},
        buckets.projects: {"retained": b"private"},
        buckets.media: {},
    }
    assert client.policies["unrelated"] == "unchanged"
    assert buckets.crm not in client.policies and buckets.projects not in client.policies
    policy = json.loads(client.policies[buckets.media])
    assert policy["Statement"] == [
        {
            "Effect": "Allow",
            "Principal": {"AWS": ["*"]},
            "Action": ["s3:GetObject"],
            "Resource": ["arn:aws:s3:::gb-test-media/*"],
        }
    ]


@pytest.mark.parametrize("error", ["AccessDenied", "InternalError", "NoSuchBucket"])
def test_policy_lookup_errors_do_not_grant_public_access(error):
    client = BucketStore()
    client.policy_error = error
    with pytest.raises(S3Error):
        bootstrap_storage(
            client, StorageBuckets("gb-test-media", "gb-test-crm", "gb-test-projects")
        )
    assert client.policies == {"unrelated": "unchanged"}


def test_unremoved_private_policy_blocks_public_policy():
    client = BucketStore()
    client.ignore_delete = True
    client.policies["gb-test-crm"] = "public"
    with pytest.raises(RuntimeError, match="not removed"):
        bootstrap_storage(
            client, StorageBuckets("gb-test-media", "gb-test-crm", "gb-test-projects")
        )
    assert "gb-test-media" not in client.policies


@pytest.mark.parametrize("name", ["ab", "GB-test", "127.0.0.1", "gb..test", "gb/test", "gb-test-"])
def test_invalid_bucket_configuration_is_rejected(name):
    with pytest.raises(ValueError):
        StorageBuckets(name, "gb-test-crm", "gb-test-projects")


@pytest.mark.parametrize(
    "crm,projects", [("gb-test-media", "gb-test-projects"), ("gb-test-crm", "gb-test-crm")]
)
def test_overlapping_public_and_private_buckets_are_rejected(crm, projects):
    with pytest.raises(ValueError, match="distinct"):
        StorageBuckets("gb-test-media", crm, projects)


def test_cli_rejects_invalid_names_before_constructing_client(monkeypatch):
    monkeypatch.setattr(command, "Minio", lambda *_a, **_k: pytest.fail("Unexpected S3 client"))
    with pytest.raises(ValueError):
        command.run({"MINIO_MEDIA_BUCKET": "gb-test-media"})


@pytest.mark.parametrize(
    "error", [s3_error("AccessDenied"), MinioException("synthetic-private-credential")]
)
def test_cli_failure_does_not_expose_sdk_secrets(monkeypatch, capsys, error):
    def fail(_environment):
        raise error

    monkeypatch.setattr(command, "run", fail)
    assert command.main([]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "synthetic-private-credential" not in captured.err
    assert json.loads(captured.err) == {
        "event": "storage.bootstrap_failed",
        "error_type": type(error).__name__,
    }


def test_cli_help_never_provisions_storage(monkeypatch, capsys):
    monkeypatch.setattr(command, "run", lambda _env: pytest.fail("Unexpected provisioning"))
    with pytest.raises(SystemExit) as stopped:
        command.main(["--help"])
    assert stopped.value.code == 0
    assert "Provision" in capsys.readouterr().out
