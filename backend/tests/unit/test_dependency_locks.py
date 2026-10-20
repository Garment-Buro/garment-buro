from __future__ import annotations

import pytest

from scripts.check_dependencies import check_locks, check_policy, read_lock


def locked(name="package", version="1.2.3", digest="a"):
    return f"{name}=={version} \\\n    --hash=sha256:{digest * 64}\n"


def test_development_must_test_the_same_versions_and_hashes_as_production(tmp_path):
    production = tmp_path / "production.txt"
    development = tmp_path / "development.txt"
    production.write_text(locked("Some-Package"))
    development.write_text(locked("some_package") + locked("test-tool"))
    assert check_locks(production, development) == (1, 2)
    for changed in ("", locked(version="1.2.4"), locked(digest="b")):
        development.write_text(changed + locked("test-tool"))
        with pytest.raises(ValueError, match="differs from production"):
            check_locks(production, development)


@pytest.mark.parametrize(
    "content",
    ["", "package>=1.2.3", "package==1.2.3", locked() + locked(), "-r other.txt"],
)
def test_incomplete_or_ambiguous_locks_are_rejected(tmp_path, content):
    path = tmp_path / "lock.txt"
    path.write_text(content)
    with pytest.raises(ValueError):
        read_lock(path)


def test_platform_markers_must_also_agree(tmp_path):
    production = tmp_path / "production.txt"
    development = tmp_path / "development.txt"
    production.write_text(locked().replace(" \\", '; sys_platform == "win32" \\'))
    development.write_text(locked())
    with pytest.raises(ValueError, match="differs from production"):
        check_locks(production, development)


def test_editing_version_policy_requires_regenerating_the_lock(tmp_path):
    source, lock = tmp_path / "requirements.in", tmp_path / "requirements.txt"
    lock.write_text(locked())
    source.write_text("# Version policy\npackage==1.2.3\n")
    check_policy(source, lock)
    for edited in ("package==1.2.4\n", "new-package==1.2.3\n"):
        source.write_text(edited)
        with pytest.raises(ValueError, match="regenerate lock"):
            check_policy(source, lock)
