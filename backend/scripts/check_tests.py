"""Run the complete backend suite against explicitly supplied test dependencies."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

DATABASE_KEYS = (
    "SCHEMA_TEST_POSTGRES_URL",
    "TOCHKA_TEST_POSTGRES_URL",
    "PRODUCTION_TEST_POSTGRES_URL",
    "ORDER_WORKFLOW_TEST_POSTGRES_URL",
)


def validated_environment(source: Mapping[str, str]) -> dict[str, str]:
    # Never inherit application secrets or a working DATABASE_URL into pytest.
    environment = {key: source[key] for key in ("PATH", "TMPDIR", "LANG") if key in source}
    databases = set()
    for key in DATABASE_KEYS:
        value = source.get(key, "")
        try:
            url = make_url(value)
        except ArgumentError:
            raise ValueError(f"{key} must name an isolated PostgreSQL test database") from None
        if (
            url.drivername != "postgresql+asyncpg"
            or not (url.database or "").startswith("test_")
            or not url.host
        ):
            raise ValueError(f"{key} must name an isolated PostgreSQL test database")
        identity = (url.host, url.port or 5432, url.database)
        if identity in databases:
            raise ValueError("Full backend tests require four separate PostgreSQL databases")
        databases.add(identity)
        environment[key] = value
    config_path = Path(source.get("MINIO_TEST_CONFIG_PATH", ""))
    try:
        permissions = stat.S_IMODE(config_path.stat().st_mode)
        config = json.loads(config_path.read_text())
    except (OSError, ValueError):
        raise ValueError(
            "MINIO_TEST_CONFIG_PATH must point to a private test configuration"
        ) from None
    if (
        permissions & 0o077
        or not isinstance(config, dict)
        or not all(
            isinstance(config.get(key), str) and config[key].strip()
            for key in ("endpoint", "access_key", "secret_key")
        )
    ):
        raise ValueError(
            "MinIO test configuration requires private permissions and connection fields"
        )
    environment.update(APP_ENV="test", MINIO_TEST_CONFIG_PATH=str(config_path.resolve()))
    return environment


def checked_report(path: Path) -> int:
    try:
        report = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        raise ValueError("Backend test report is missing or invalid") from None
    cases = report.findall(".//testcase")
    if (
        not cases
        or report.findall(".//skipped")
        or report.findall(".//failure")
        or report.findall(".//error")
    ):
        raise ValueError("Full backend gate requires passing tests with no skips")
    return len(cases)


def run_suite(environment: Mapping[str, str], report: Path) -> int:
    # A stale successful report must never make this run green.
    report.unlink(missing_ok=True)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "--tb=short", "--junitxml=" + str(report)],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(environment),
        check=False,
    )
    if result.returncode:
        return result.returncode
    count = checked_report(report)
    print(f"Full backend gate: {count} passed, 0 skipped", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="Optional JUnit result outside the source tree")
    args = parser.parse_args()
    try:
        environment = validated_environment(os.environ)
        with TemporaryDirectory(prefix="garment-test-report-") as folder:
            report = args.report.resolve() if args.report else Path(folder) / "results.xml"
            return run_suite(environment, report)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
