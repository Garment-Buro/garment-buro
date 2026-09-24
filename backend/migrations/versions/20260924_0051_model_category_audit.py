"""Allow garment model categories in CRM reference audit events."""

from alembic import op

revision = "20260924_0051"
down_revision = "20260923_0050"
branch_labels = None
depends_on = None

CONSTRAINT = "ck_crm_reference_events_crm_reference_event_entity_type_valid"
OLD_VALUES = "'fabric', 'garment_model', 'catalog_product_link', 'tech_card', 'tech_card_revision'"
NEW_VALUES = (
    "'fabric', 'garment_model_category', 'garment_model', "
    "'catalog_product_link', 'tech_card', 'tech_card_revision'"
)


def _replace(values: str) -> None:
    constraint = op.f(CONSTRAINT)
    op.drop_constraint(constraint, "crm_reference_events", type_="check")
    op.create_check_constraint(
        constraint,
        "crm_reference_events",
        f"entity_type IN ({values})",
    )


def upgrade() -> None:
    _replace(NEW_VALUES)


def downgrade() -> None:
    _replace(OLD_VALUES)
