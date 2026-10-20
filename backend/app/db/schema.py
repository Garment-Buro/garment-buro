"""Use physical constraint names when comparing the ORM with a live schema."""

from sqlalchemy import CheckConstraint, MetaData
from sqlalchemy.engine import Dialect
from sqlalchemy.schema import conv


def comparison_metadata(dialect: Dialect, metadata: MetaData) -> MetaData:
    # PostgreSQL limits identifiers to 63 bytes. SQLAlchemy shortens convention
    # names during DDL compilation; Alembic's check comparison uses name strings.
    # Compare the compiled names, without changing the shared ORM metadata.
    copied = MetaData(naming_convention=metadata.naming_convention)
    for table in metadata.sorted_tables:
        table.to_metadata(copied)
    for table in copied.tables.values():
        for constraint in table.constraints:
            if isinstance(constraint, CheckConstraint) and constraint.name is not None:
                name = dialect.identifier_preparer.format_constraint(constraint)
                if name is not None:
                    if name.startswith('"'):
                        name = name[1:-1].replace('""', '"')
                    constraint.name = conv(name)
    return copied
