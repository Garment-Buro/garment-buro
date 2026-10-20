import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.check_tests import DATABASE_KEYS, checked_report, run_suite, validated_environment


def valid_environment(tmp_path):
    config = tmp_path / "storage.json"
    config.write_text(
        json.dumps({"endpoint": "127.0.0.1:9000", "access_key": "test", "secret_key": "test"})
    )
    config.chmod(0o600)
    return {
        **{
            key: f"postgresql+asyncpg://test:test@127.0.0.1/test_gate_{index}"
            for index, key in enumerate(DATABASE_KEYS)
        },
        "MINIO_TEST_CONFIG_PATH": str(config),
        "PATH": "/test/bin",
        "DATABASE_URL": "must-not-reach-pytest",
        "PAYMENT_SECRET": "must-not-reach-pytest",
        "PYTEST_ADDOPTS": "--ignore=tests/integration",
    }


@pytest.mark.parametrize("key", [*DATABASE_KEYS, "MINIO_TEST_CONFIG_PATH"])
def test_full_gate_rejects_missing_native_dependencies(tmp_path, key):
    environment = valid_environment(tmp_path)
    del environment[key]
    with pytest.raises(ValueError):
        validated_environment(environment)


@pytest.mark.parametrize(
    "url",
    [
        "broken-private-value",
        "sqlite:///test.db",
        "postgresql+asyncpg://test:secret@localhost/production",
    ],
)
def test_full_gate_rejects_unsafe_database_without_echoing_connection(tmp_path, url):
    environment = valid_environment(tmp_path)
    environment[DATABASE_KEYS[0]] = url
    with pytest.raises(ValueError) as error:
        validated_environment(environment)
    assert url not in str(error.value)
    assert "secret" not in str(error.value)


def test_full_gate_requires_distinct_databases_and_scrubs_parent_environment(tmp_path):
    environment = valid_environment(tmp_path)
    safe = validated_environment(environment)
    assert safe["APP_ENV"] == "test"
    assert safe["PATH"] == environment["PATH"]
    assert safe["MINIO_TEST_CONFIG_PATH"] == environment["MINIO_TEST_CONFIG_PATH"]
    assert not {"DATABASE_URL", "PAYMENT_SECRET", "PYTEST_ADDOPTS"} & safe.keys()
    environment[DATABASE_KEYS[1]] = environment[DATABASE_KEYS[0]].replace(
        "test:test@", "other:password@"
    )
    with pytest.raises(ValueError, match="four separate"):
        validated_environment(environment)


@pytest.mark.parametrize(
    "contents,permissions",
    [
        ("{}", 0o600),
        ("invalid", 0o600),
        ('{"endpoint":"localhost:9000","access_key":"test","secret_key":"test"}', 0o644),
    ],
)
def test_full_gate_rejects_missing_fields_invalid_or_public_config(tmp_path, contents, permissions):
    environment = valid_environment(tmp_path)
    config = Path(environment["MINIO_TEST_CONFIG_PATH"])
    config.write_text(contents)
    config.chmod(permissions)
    with pytest.raises(ValueError):
        validated_environment(environment)


@pytest.mark.parametrize(
    "body",
    [
        "",
        "<testsuites/>",
        "<testsuites><testcase><skipped/></testcase></testsuites>",
        "<testsuites><testcase><failure/></testcase></testsuites>",
        "<testsuites><testcase><error/></testcase></testsuites>",
    ],
)
def test_full_gate_rejects_empty_invalid_skipped_and_failed_reports(tmp_path, body):
    report = tmp_path / "results.xml"
    report.write_text(body)
    with pytest.raises(ValueError):
        checked_report(report)


def test_full_gate_counts_actual_cases_and_handles_missing_report(tmp_path):
    report = tmp_path / "results.xml"
    with pytest.raises(ValueError):
        checked_report(report)
    report.write_text(
        '<testsuites><testsuite><testcase name="one"/><testcase name="two"/></testsuite></testsuites>'
    )
    assert checked_report(report) == 2


@pytest.mark.parametrize("exit_code,new_report", [(0, True), (0, False), (7, True)])
def test_full_gate_runs_complete_suite_and_cannot_accept_a_stale_report(
    tmp_path, monkeypatch, exit_code, new_report
):
    report = tmp_path / "results.xml"
    report.write_text("<testsuites><testcase/></testsuites>")
    environment = validated_environment(valid_environment(tmp_path))

    def child(command, **options):
        assert command[1:4] == ["-m", "pytest", "tests"]
        assert not report.exists()
        assert options["env"] == environment
        if new_report:
            report.write_text("<testsuites><testsuite><testcase/></testsuite></testsuites>")
        return SimpleNamespace(returncode=exit_code)

    monkeypatch.setattr("scripts.check_tests.subprocess.run", child)
    if not new_report and exit_code == 0:
        with pytest.raises(ValueError):
            run_suite(environment, report)
    else:
        assert run_suite(environment, report) == exit_code
