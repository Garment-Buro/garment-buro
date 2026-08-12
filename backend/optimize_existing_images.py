from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Tuple

import redis

from image_optimization import (
    DEFAULT_MAX_DIMENSION,
    DEFAULT_WEBP_QUALITY,
    optimize_image_bytes,
)


SOURCE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def _quote_identifier(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def convert_uploads(
    uploads_dir: Path,
    *,
    quality: int = DEFAULT_WEBP_QUALITY,
    max_dimension: int = DEFAULT_MAX_DIMENSION,
    dry_run: bool = False,
) -> Tuple[Dict[str, str], int, int]:
    replacements: Dict[str, str] = {}
    source_bytes = 0
    webp_bytes = 0

    for source in sorted(uploads_dir.iterdir()):
        if not source.is_file() or source.suffix.lower() not in SOURCE_SUFFIXES:
            continue

        target = source.with_suffix(".webp")
        optimized = optimize_image_bytes(
            source.read_bytes(),
            quality=quality,
            max_dimension=max_dimension,
        )
        if optimized is None:
            continue

        target_size = len(optimized)
        if not dry_run:
            temporary = target.with_suffix(".webp.tmp")
            temporary.write_bytes(optimized)
            os.replace(temporary, target)

        replacements[f"/uploads/{source.name}"] = f"/uploads/{target.name}"
        source_bytes += source.stat().st_size
        webp_bytes += target_size

    return replacements, source_bytes, webp_bytes


def _text_columns(connection: sqlite3.Connection) -> Iterable[Tuple[str, str]]:
    tables = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    for (table_name,) in tables:
        table = _quote_identifier(table_name)
        for column in connection.execute(f"PRAGMA table_info({table})").fetchall():
            column_name = column[1]
            column_type = (column[2] or "").upper()
            if any(marker in column_type for marker in ("CHAR", "CLOB", "TEXT")):
                yield table_name, column_name


def update_database_references(
    database_path: Path,
    replacements: Dict[str, str],
    *,
    dry_run: bool = False,
) -> Tuple[int, Path | None]:
    if not replacements:
        return 0, None

    connection = sqlite3.connect(database_path)
    backup_path = None
    updated_rows = 0
    try:
        if not dry_run:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = database_path.with_name(
                f"{database_path.name}.backup-webp-{timestamp}"
            )
            backup = sqlite3.connect(backup_path)
            try:
                connection.backup(backup)
            finally:
                backup.close()

        columns = list(_text_columns(connection))
        if dry_run:
            for table_name, column_name in columns:
                table = _quote_identifier(table_name)
                column = _quote_identifier(column_name)
                for old_url in replacements:
                    count = connection.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE {column} LIKE ?",
                        (f"%{old_url}%",),
                    ).fetchone()[0]
                    updated_rows += count
            return updated_rows, None

        with connection:
            for table_name, column_name in columns:
                table = _quote_identifier(table_name)
                column = _quote_identifier(column_name)
                for old_url, new_url in replacements.items():
                    cursor = connection.execute(
                        f"UPDATE {table} SET {column} = REPLACE({column}, ?, ?) "
                        f"WHERE {column} LIKE ?",
                        (old_url, new_url, f"%{old_url}%"),
                    )
                    updated_rows += max(cursor.rowcount, 0)
    finally:
        connection.close()

    return updated_rows, backup_path


def clear_catalog_cache(redis_url: str | None) -> int:
    if not redis_url:
        return 0

    try:
        client = redis.Redis.from_url(redis_url)
        keys = list(client.scan_iter(match="catalog:products:*"))
        return client.delete(*keys) if keys else 0
    except redis.RedisError as error:
        print(f"Warning: catalog cache was not cleared: {error}")
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert existing PNG/JPEG uploads to WebP and update SQLite URLs."
    )
    parser.add_argument("--uploads", type=Path, default=Path("uploads"))
    parser.add_argument("--database", type=Path, default=Path("ecommerce.db"))
    parser.add_argument("--quality", type=int, default=DEFAULT_WEBP_QUALITY)
    parser.add_argument("--max-dimension", type=int, default=DEFAULT_MAX_DIMENSION)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--delete-originals",
        action="store_true",
        help="Delete converted PNG/JPEG files after the database update.",
    )
    args = parser.parse_args()

    replacements, source_bytes, webp_bytes = convert_uploads(
        args.uploads,
        quality=args.quality,
        max_dimension=args.max_dimension,
        dry_run=args.dry_run,
    )
    updated_rows, backup_path = update_database_references(
        args.database,
        replacements,
        dry_run=args.dry_run,
    )
    cleared_cache_keys = 0
    if not args.dry_run and updated_rows:
        cleared_cache_keys = clear_catalog_cache(os.getenv("REDIS_URL"))

    if args.delete_originals and not args.dry_run:
        for old_url in replacements:
            (args.uploads / Path(old_url).name).unlink(missing_ok=True)

    saved_bytes = max(source_bytes - webp_bytes, 0)
    print(f"Converted images: {len(replacements)}")
    print(f"Database rows updated: {updated_rows}")
    print(f"Catalog cache keys cleared: {cleared_cache_keys}")
    print(f"Image bytes: {source_bytes} -> {webp_bytes} (saved {saved_bytes})")
    if backup_path:
        print(f"Database backup: {backup_path}")
    if args.dry_run:
        print("Dry run: no files or database rows were changed")


if __name__ == "__main__":
    main()
