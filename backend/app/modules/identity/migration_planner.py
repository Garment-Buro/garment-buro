from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.modules.identity.exceptions import InvalidEmailError
from app.modules.identity.migration_types import (
    IdentityMigrationPlan,
    LegacyIdentityRecord,
)
from app.modules.identity.security import normalize_email

LEGACY_USER_COLUMNS = (
    "id",
    "email",
    "telegram_id",
    "first_name",
    "last_name",
    "username",
    "created_at",
    "phone",
    "gender",
    "birth_date",
    "height",
    "weight",
    "otp_code",
    "otp_expiry",
)


class LegacyIdentityPlanner:
    def build(self, database_path: Path) -> IdentityMigrationPlan:
        database_path = database_path.expanduser().resolve()
        errors: list[str] = []
        warnings: list[str] = []
        users: list[LegacyIdentityRecord] = []
        discarded_legacy_otp_count = 0

        if not database_path.is_file():
            errors.append(f"Legacy database does not exist: {database_path}")
            return self._plan(database_path, users, 0, errors, warnings)

        try:
            with self._connect_readonly(database_path) as connection:
                actual_columns = {
                    row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()
                }
                missing = sorted(set(LEGACY_USER_COLUMNS) - actual_columns)
                if missing:
                    errors.append(f"Legacy table users is missing columns: {', '.join(missing)}")
                else:
                    rows = connection.execute(
                        f"SELECT {', '.join(LEGACY_USER_COLUMNS)} FROM users ORDER BY id"
                    ).fetchall()
                    for row in rows:
                        record, row_errors = self._record(row)
                        errors.extend(row_errors)
                        if record is not None:
                            users.append(record)
                        if row["otp_code"] is not None or row["otp_expiry"] is not None:
                            discarded_legacy_otp_count += 1
        except sqlite3.Error as error:
            errors.append(f"Unable to read legacy SQLite database: {error}")

        errors.extend(self._duplicate_errors(users))
        if discarded_legacy_otp_count:
            warnings.append(
                f"{discarded_legacy_otp_count} legacy OTP states will be discarded; "
                "users must request a new code"
            )
        return self._plan(
            database_path,
            users,
            discarded_legacy_otp_count,
            errors,
            warnings,
        )

    @staticmethod
    def _connect_readonly(database_path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _record(
        row: sqlite3.Row,
    ) -> tuple[LegacyIdentityRecord | None, list[str]]:
        user_id = int(row["id"])
        errors: list[str] = []
        email: str | None = None
        email_normalized: str | None = None
        if row["email"] is not None and str(row["email"]).strip():
            try:
                email, email_normalized = normalize_email(str(row["email"]))
            except InvalidEmailError:
                errors.append(f"User {user_id} has an invalid email")
        telegram_id = _optional_text(row["telegram_id"])
        if email_normalized is None and telegram_id is None:
            errors.append(f"User {user_id} has no usable email or Telegram identifier")

        birth_date: date | None = None
        raw_birth_date = _optional_text(row["birth_date"])
        if raw_birth_date is not None:
            try:
                birth_date = date.fromisoformat(raw_birth_date)
            except ValueError:
                errors.append(f"User {user_id} has an invalid birth date")

        height_cm = _optional_decimal(row["height"], user_id, "height", errors)
        weight_kg = _optional_decimal(row["weight"], user_id, "weight", errors)
        if height_cm is not None and height_cm < 0:
            errors.append(f"User {user_id} has negative height")
        if weight_kg is not None and weight_kg < 0:
            errors.append(f"User {user_id} has negative weight")

        created_at = _parse_datetime(row["created_at"], user_id, errors)
        if errors:
            return None, errors
        return (
            LegacyIdentityRecord(
                id=user_id,
                email=email,
                email_normalized=email_normalized,
                telegram_id=telegram_id,
                first_name=_optional_text(row["first_name"]),
                last_name=_optional_text(row["last_name"]),
                username=_optional_text(row["username"]),
                created_at=created_at,
                phone=_optional_text(row["phone"]),
                gender=_optional_text(row["gender"]),
                birth_date=birth_date,
                height_cm=height_cm,
                weight_kg=weight_kg,
                had_legacy_otp=(row["otp_code"] is not None or row["otp_expiry"] is not None),
            ),
            [],
        )

    @staticmethod
    def _duplicate_errors(users: list[LegacyIdentityRecord]) -> list[str]:
        errors: list[str] = []
        emails: dict[str, int] = {}
        telegram_ids: dict[str, int] = {}
        for user in users:
            if user.email_normalized is not None:
                previous = emails.get(user.email_normalized)
                if previous is not None:
                    errors.append(f"Users {previous} and {user.id} share one normalized email")
                emails[user.email_normalized] = user.id
            if user.telegram_id is not None:
                previous = telegram_ids.get(user.telegram_id)
                if previous is not None:
                    errors.append(f"Users {previous} and {user.id} share one Telegram ID")
                telegram_ids[user.telegram_id] = user.id
        return errors

    @staticmethod
    def _plan(
        database_path: Path,
        users: list[LegacyIdentityRecord],
        discarded_legacy_otp_count: int,
        errors: list[str],
        warnings: list[str],
    ) -> IdentityMigrationPlan:
        return IdentityMigrationPlan(
            source_database=str(database_path),
            users=tuple(users),
            discarded_legacy_otp_count=discarded_legacy_otp_count,
            errors=tuple(sorted(errors)),
            warnings=tuple(sorted(warnings)),
        )


def _optional_text(value: object | None) -> str | None:
    text_value = str(value).strip() if value is not None else ""
    return text_value or None


def _optional_decimal(
    value: object | None,
    user_id: int,
    field_name: str,
    errors: list[str],
) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        errors.append(f"User {user_id} has invalid {field_name}")
        return None


def _parse_datetime(
    value: object | None,
    user_id: int,
    errors: list[str],
) -> datetime:
    if value is None or str(value).strip() == "":
        errors.append(f"User {user_id} has no creation timestamp")
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        errors.append(f"User {user_id} has an invalid creation timestamp")
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
