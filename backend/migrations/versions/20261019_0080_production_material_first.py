"""Seek the first fabric of a production plan without scanning other plans."""

import sqlalchemy as sa
from alembic import op

revision = "20261019_0080"
down_revision = "20261019_0079"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_crm_fabric_requirement_model_first",
        "crm_garment_fabric_requirements",
        ["garment_model_id", sa.column("is_primary").desc(), "id"],
        postgresql_include=["fabric_id"],
    )
    op.drop_index(
        "ix_crm_garment_fabric_requirements_garment_model_id",
        table_name="crm_garment_fabric_requirements",
    )
    op.create_index(
        "ix_crm_material_reservation_plan_first",
        "crm_material_reservations",
        ["production_plan_revision_id", "id"],
        postgresql_include=["fabric_id"],
    )
    op.drop_index(
        "ix_crm_material_reservations_production_plan_revision_id",
        table_name="crm_material_reservations",
    )


def downgrade() -> None:
    op.create_index(
        "ix_crm_garment_fabric_requirements_garment_model_id",
        "crm_garment_fabric_requirements",
        ["garment_model_id"],
    )
    op.drop_index(
        "ix_crm_fabric_requirement_model_first", table_name="crm_garment_fabric_requirements"
    )
    op.create_index(
        "ix_crm_material_reservations_production_plan_revision_id",
        "crm_material_reservations",
        ["production_plan_revision_id"],
    )
    op.drop_index("ix_crm_material_reservation_plan_first", table_name="crm_material_reservations")
