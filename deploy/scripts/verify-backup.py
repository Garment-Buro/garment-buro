#!/usr/bin/env python3
"""Read-only release bundle checks. Passing is not a database/storage restore proof."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import stat
import tarfile
from pathlib import Path, PurePosixPath

REQUIRED = frozenset(
    {"postgresql.dump", "minio-data.tar.gz", "deployment.env", "release", "docker-compose.yml"}
)
OPTIONAL = frozenset({"ecommerce.sqlite3", "legacy-uploads.tar.gz"})
CHUNK = 1024 * 1024


class BackupVerificationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BackupVerificationError(message)


def _archive(path: Path) -> dict[str, int]:
    files, total_bytes, names = 0, 0, set()
    with gzip.open(path, "rb") as compressed:
        with tarfile.open(fileobj=compressed, mode="r|") as archive:
            for member in archive:
                name = PurePosixPath(member.name)
                _require(
                    not name.is_absolute()
                    and ".." not in name.parts
                    and "\\" not in member.name
                    and (member.isfile() or member.isdir()),
                    "Archive contains an unsafe member",
                )
                normalized = str(name)
                _require(normalized not in names, "Archive contains duplicate members")
                names.add(normalized)
                if member.isfile():
                    _require(bool(name.parts), "Archive file has no name")
                    source = archive.extractfile(member)
                    _require(source is not None, "Archive file is unreadable")
                    actual = 0
                    with source:
                        while chunk := source.read(CHUNK):
                            actual += len(chunk)
                    _require(actual == member.size, "Archive file is truncated")
                    files += 1
                    total_bytes += actual
        # tar's end marker may precede gzip's footer. Drain it to verify CRC and
        # catch truncated/corrupt trailing compressed bytes, without extraction.
        while compressed.read(CHUNK):
            pass
    return {"files": files, "bytes": total_bytes}


def verify_backup(directory: Path) -> dict[str, object]:
    _require(directory.is_dir() and not directory.is_symlink(), "Backup directory is invalid")
    _require(not directory.stat().st_mode & 0o077, "Backup directory is not private")
    entries = {entry.name: entry for entry in directory.iterdir()}
    _require("SHA256SUMS" in entries, "Backup has no completion manifest")
    _require(
        REQUIRED <= entries.keys() - {"SHA256SUMS"} <= REQUIRED | OPTIONAL,
        "Backup has missing or unexpected files",
    )
    for entry in entries.values():
        mode = entry.lstat().st_mode
        _require(stat.S_ISREG(mode), "Backup contains a non-regular file")
        _require(not mode & 0o077, "Backup file is not private")
    manifest = entries["SHA256SUMS"]
    _require(manifest.stat().st_size <= 4096, "Backup manifest is too large")
    checksums = {}
    for line in manifest.read_text(encoding="ascii").splitlines():
        match = re.fullmatch(r"([a-f0-9]{64})  ([A-Za-z0-9_.-]+)", line)
        _require(match is not None, "Backup manifest is malformed")
        digest, name = match.groups()
        _require(name not in checksums, "Backup manifest repeats a file")
        checksums[name] = digest
    _require(checksums.keys() == entries.keys() - {"SHA256SUMS"}, "Backup manifest is incomplete")
    for name, expected in checksums.items():
        digest = hashlib.sha256()
        with entries[name].open("rb") as source:
            while chunk := source.read(CHUNK):
                digest.update(chunk)
        _require(digest.hexdigest() == expected, "Backup checksum mismatch")
    with entries["postgresql.dump"].open("rb") as source:
        _require(source.read(5) == b"PGDMP", "PostgreSQL custom dump header is invalid")
    if "ecommerce.sqlite3" in entries:
        with entries["ecommerce.sqlite3"].open("rb") as source:
            _require(source.read(16) == b"SQLite format 3\x00", "SQLite backup header is invalid")
    archives = {
        name: _archive(entries[name])
        for name in ("minio-data.tar.gz", "legacy-uploads.tar.gz")
        if name in entries
    }
    # Never parse/source configuration, print its contents, or extract tar files.
    return {"verified_files": len(checksums), "archives": archives}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    args = parser.parse_args()
    try:
        report = verify_backup(args.backup)
    except (OSError, ValueError, tarfile.TarError, EOFError):
        # Paths, saved environment values and archive names may be private.
        print(json.dumps({"verified": False, "error": "Backup verification failed"}))
        return 1
    print(json.dumps({"verified": True, **report}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
