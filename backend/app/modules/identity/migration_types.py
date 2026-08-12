from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class LegacyIdentityRecord:
    id: int
    email: str | None
    email_normalized: str | None
    telegram_id: str | None
    first_name: str | None
    last_name: str | None
    username: str | None
    created_at: datetime
    phone: str | None
    gender: str | None
    birth_date: date | None
    height_cm: Decimal | None
    weight_kg: Decimal | None
    had_legacy_otp: bool


@dataclass(frozen=True, slots=True)
class IdentityMigrationPlan:
    source_database: str
    users: tuple[LegacyIdentityRecord, ...]
    discarded_legacy_otp_count: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def fingerprint(self) -> str:
        payload = {
            "source_database": self.source_database,
            "users": [asdict(user) for user in self.users],
            "discarded_legacy_otp_count": self.discarded_legacy_otp_count,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def report(self) -> dict[str, object]:
        return {
            "source_database": self.source_database,
            "valid": self.valid,
            "fingerprint_sha256": self.fingerprint,
            "counts": {
                "users": len(self.users),
                "discarded_legacy_otp": self.discarded_legacy_otp_count,
            },
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class IdentityMigrationResult:
    fingerprint_sha256: str
    users: int


class InvalidIdentityMigrationPlanError(RuntimeError):
    pass


class TargetIdentityNotEmptyError(RuntimeError):
    pass
