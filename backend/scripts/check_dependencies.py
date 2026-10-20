"""Check that tested Python dependencies include the exact production lock."""

from __future__ import annotations

import re
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name


def read_lock(path: Path) -> dict[tuple[str, str], tuple[str, frozenset[str]]]:
    result = {}
    for line in path.read_text().replace("\\\n", " ").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"\s+--hash=", line)
        try:
            requirement = Requirement(parts[0].strip())
        except InvalidRequirement as error:
            raise ValueError(f"{path.name}: invalid locked requirement") from error
        specifiers = list(requirement.specifier)
        if (
            requirement.url
            or requirement.extras
            or len(specifiers) != 1
            or specifiers[0].operator != "=="
            or "*" in specifiers[0].version
        ):
            raise ValueError(f"{path.name}: every dependency must have one exact version")
        hashes = frozenset(part.strip() for part in parts[1:])
        if not hashes or any(not re.fullmatch(r"sha256:[a-f0-9]{64}", item) for item in hashes):
            raise ValueError(f"{path.name}: missing or invalid SHA256 hashes")
        key = (canonicalize_name(requirement.name), str(requirement.marker or ""))
        if key in result:
            raise ValueError(f"{path.name}: duplicate locked dependency {key[0]}")
        result[key] = (specifiers[0].version, hashes)
    if not result:
        raise ValueError(f"{path.name}: empty dependency lock")
    return result


def check_locks(production: Path, development: Path) -> tuple[int, int]:
    runtime = read_lock(production)
    tested = read_lock(development)
    for key, locked in runtime.items():
        if tested.get(key) != locked:
            raise ValueError(f"Development lock differs from production: {key[0]}")
    return len(runtime), len(tested)


def check_policy(source: Path, lock: Path, *, include: str | None = None) -> None:
    inventory = read_lock(lock)
    for line in source.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or (include and line == f"-r {include}"):
            continue
        requirement = Requirement(line)
        key = (canonicalize_name(requirement.name), str(requirement.marker or ""))
        locked = inventory.get(key)
        if locked is None or not requirement.specifier.contains(locked[0], prereleases=True):
            raise ValueError(f"{source.name}: regenerate lock for {requirement.name}")


def main() -> None:
    backend = Path(__file__).resolve().parents[1]
    runtime, tested = check_locks(backend / "requirements.txt", backend / "requirements-dev.txt")
    check_policy(backend / "requirements.in", backend / "requirements.txt")
    check_policy(
        backend / "requirements-dev.in", backend / "requirements-dev.txt", include="requirements.in"
    )
    print(f"Dependency locks agree: {runtime} production, {tested} development entries")


if __name__ == "__main__":
    main()
