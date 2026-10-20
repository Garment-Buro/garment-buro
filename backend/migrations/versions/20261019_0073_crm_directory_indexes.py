"""Match model/file keyset ordering and exact pattern-window lookups.

Revision ID: 20261019_0073
Revises: 20261018_0072
"""

import sqlalchemy as sa
from alembic import op

revision = "20261019_0073"
down_revision = "20261018_0072"
branch_labels = None
depends_on = None

ORDER_INDEXES = (
    ("ix_crm_models_directory_name", "crm_garment_models", "name"),
    ("ix_crm_models_directory_code", "crm_garment_models", "code"),
    ("ix_crm_patterns_directory_code", "crm_garment_patterns", "code"),
)


def upgrade() -> None:
    collate = '::text COLLATE "pg_c_utf8"' if op.get_bind().dialect.name == "postgresql" else ""
    for name, table, field in ORDER_INDEXES:
        op.create_index(name, table, [sa.text(f"lower({field}{collate})"), "id"])
    op.create_index(
        "ix_crm_patterns_size_window",
        "crm_garment_patterns",
        ["garment_model_id", "garment_size_id", "width_cm", "length_cm"],
    )


def downgrade() -> None:
    op.drop_index("ix_crm_patterns_size_window", table_name="crm_garment_patterns")
    for name, table, _field in reversed(ORDER_INDEXES):
        op.drop_index(name, table_name=table)
