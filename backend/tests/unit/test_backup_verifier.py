import hashlib
import importlib.util
import subprocess
import sys
import tarfile
from io import BytesIO
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "deploy/scripts/verify-backup.py"
spec = importlib.util.spec_from_file_location("verify_backup", SCRIPT)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def manifest(directory):
    files = sorted(entry for entry in directory.iterdir() if entry.name != "SHA256SUMS")
    (directory / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256(entry.read_bytes()).hexdigest()}  {entry.name}\n" for entry in files
        )
    )
    for entry in directory.iterdir():
        entry.chmod(0o600)


def archive(directory, *, name="objects/image.txt", kind=tarfile.REGTYPE):
    with tarfile.open(directory / "minio-data.tar.gz", "w:gz") as output:
        item = tarfile.TarInfo(name)
        item.type, item.size = kind, 0
        item.linkname = "outside"
        output.addfile(item, BytesIO())


@pytest.fixture
def bundle(tmp_path):
    tmp_path.chmod(0o700)
    for name in verifier.REQUIRED:
        (tmp_path / name).write_bytes(
            b"PGDMPfixture" if name == "postgresql.dump" else b"private fixture"
        )
    archive(tmp_path)
    manifest(tmp_path)
    return tmp_path


def test_bundle_checks_metadata_and_archives_without_executing_configuration(bundle):
    (bundle / "deployment.env").write_text("SECRET=local-only\n$(must-never-execute)\n")
    manifest(bundle)
    before = {entry.name: entry.read_bytes() for entry in bundle.iterdir()}
    assert verifier.verify_backup(bundle) == {
        "verified_files": 5,
        "archives": {"minio-data.tar.gz": {"files": 1, "bytes": 0}},
    }
    assert before == {entry.name: entry.read_bytes() for entry in bundle.iterdir()}
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(bundle)], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "local-only" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    "file", ["deployment.env", "release", "docker-compose.yml", "postgresql.dump"]
)
def test_verifier_detects_corruption_in_metadata_and_primary_dump(bundle, file):
    (bundle / file).write_bytes(b"changed")
    with pytest.raises(verifier.BackupVerificationError, match="checksum"):
        verifier.verify_backup(bundle)


@pytest.mark.parametrize(
    "name,kind",
    [
        ("../escape", tarfile.REGTYPE),
        ("/absolute", tarfile.REGTYPE),
        ("objects/link", tarfile.SYMTYPE),
        ("objects/link", tarfile.LNKTYPE),
    ],
)
def test_verifier_rejects_unsafe_archive_members_even_with_matching_hash(bundle, name, kind):
    archive(bundle, name=name, kind=kind)
    manifest(bundle)
    with pytest.raises(verifier.BackupVerificationError, match="unsafe"):
        verifier.verify_backup(bundle)


def test_verifier_reads_gzip_footer_even_after_tar_end_marker(bundle):
    path = bundle / "minio-data.tar.gz"
    data = bytearray(path.read_bytes())
    data[-8] ^= 1
    path.write_bytes(data)
    manifest(bundle)
    with pytest.raises(OSError):
        verifier.verify_backup(bundle)


@pytest.mark.parametrize(
    "failure", ["missing", "unexpected", "duplicate", "permissions", "symlink"]
)
def test_verifier_refuses_incomplete_or_exposed_bundle(bundle, failure):
    if failure == "missing":
        (bundle / "release").unlink()
    elif failure == "unexpected":
        (bundle / "untracked").write_text("unexpected")
    elif failure == "duplicate":
        path = bundle / "SHA256SUMS"
        path.write_text(path.read_text() * 2)
    elif failure == "permissions":
        (bundle / "deployment.env").chmod(0o644)
    else:
        (bundle / "release").unlink()
        (bundle / "release").symlink_to(bundle / "deployment.env")
    with pytest.raises(verifier.BackupVerificationError):
        verifier.verify_backup(bundle)


def test_verifier_rejects_non_dump_even_if_its_checksum_matches(bundle):
    (bundle / "postgresql.dump").write_bytes(b"not a custom dump")
    manifest(bundle)
    with pytest.raises(verifier.BackupVerificationError, match="header"):
        verifier.verify_backup(bundle)


def test_verifier_rejects_duplicate_normalized_tar_paths(bundle):
    with tarfile.open(bundle / "minio-data.tar.gz", "w:gz") as output:
        for name in ["objects/image", "./objects/image"]:
            output.addfile(tarfile.TarInfo(name), BytesIO())
    manifest(bundle)
    with pytest.raises(verifier.BackupVerificationError, match="duplicate"):
        verifier.verify_backup(bundle)


def test_incomplete_backup_cli_fails_without_leaking_metadata_or_path(bundle):
    (bundle / "SHA256SUMS").unlink()
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(bundle)], capture_output=True, text=True
    )
    assert result.returncode == 1
    assert result.stdout.strip() == '{"verified": false, "error": "Backup verification failed"}'
    assert not result.stderr
