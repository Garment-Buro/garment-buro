"""Database text rules shared by public directories and their indexes."""

from sqlalchemy import String, literal
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement


class UnicodeLower(FunctionElement[str]):
    """PostgreSQL 17 Unicode casing, independent of the cluster's default locale."""

    type = String()
    inherit_cache = True


@compiles(UnicodeLower)
def _lower(element, compiler, **kwargs):
    # SQLite is only a lightweight test dialect; production uses PostgreSQL 17.
    return f"lower({compiler.process(element.clauses, **kwargs)})"


@compiles(UnicodeLower, "postgresql")
def _postgres_lower(element, compiler, **kwargs):
    # Match the reflected expression-index form, including varchar's implicit
    # text cast, without redundant parentheses that Alembic treats as a change.
    return f'lower({compiler.process(element.clauses, **kwargs)}::text COLLATE "pg_c_utf8")'


def unicode_contains(column, value: str):
    """Case-insensitive substring; %, _ and backslash remain literal input."""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return UnicodeLower(column).like(UnicodeLower(literal(f"%{escaped}%")), escape="\\")
