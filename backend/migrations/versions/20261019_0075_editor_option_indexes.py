"""Keyset editor options and bounded active model source.

Revision ID: 20261019_0075
Revises: 20261019_0074
"""

from alembic import op

revision = "20261019_0075"
down_revision = "20261019_0074"
branch_labels = None
depends_on = None

INDEXES = (
    ("ix_crm_models_editor_active_id", "crm_garment_models", ["is_active", "id"]),
    ("ix_crm_fabrics_editor_active_id", "crm_fabrics", ["is_active", "id"]),
    (
        "ix_crm_sizes_editor_model_active_id",
        "crm_garment_sizes",
        ["garment_model_id", "is_active", "id"],
    ),
)
SIZE_ORDER = "ix_crm_garment_sizes_model_active_sort"


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)
    op.drop_index(SIZE_ORDER, table_name="crm_garment_sizes")
    op.create_index(
        SIZE_ORDER, "crm_garment_sizes", ["garment_model_id", "is_active", "sort_order", "id"]
    )


def downgrade() -> None:
    op.drop_index(SIZE_ORDER, table_name="crm_garment_sizes")
    op.create_index(
        SIZE_ORDER, "crm_garment_sizes", ["garment_model_id", "is_active", "sort_order"]
    )
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
