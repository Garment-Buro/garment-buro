"""Allow idempotent CRM production planning commands.

Revision ID: 20260812_0027
Revises: 20260812_0026
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260812_0027"
down_revision: str | Sequence[str] | None = "20260812_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT_NAME = "ck_crm_staff_commands_crm_staff_command_type_valid"
PREVIOUS_TYPES = (
    "command_type IN ('project.assign', 'project.transition', 'unit.assign', 'unit.transition')"
)
PLANNING_TYPES = (
    "command_type IN ('project.assign', 'project.transition', "
    "'unit.assign', 'unit.plan', 'unit.transition')"
)


def upgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, "crm_staff_commands", type_="check")
    op.create_check_constraint(CONSTRAINT_NAME, "crm_staff_commands", PLANNING_TYPES)


def downgrade() -> None:
    if not context.is_offline_mode():
        planning_commands = (
            op.get_bind()
            .execute(
                sa.text("SELECT count(*) FROM crm_staff_commands WHERE command_type = 'unit.plan'")
            )
            .scalar_one()
        )
        if planning_commands:
            raise RuntimeError("Cannot downgrade CRM planning command support while receipts exist")
    op.drop_constraint(CONSTRAINT_NAME, "crm_staff_commands", type_="check")
    op.create_check_constraint(CONSTRAINT_NAME, "crm_staff_commands", PREVIOUS_TYPES)
