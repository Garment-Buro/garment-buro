"""Add the restricted production administrator role."""

import sqlalchemy as sa
from alembic import op

revision = "20260921_0048"
down_revision = "20260921_0047"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            "INSERT INTO roles (name, description, is_system) "
            "VALUES ('production_supervisor', 'Restricted production administrator', true) "
            "ON CONFLICT (name) DO NOTHING"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT r.id, p.id FROM roles r CROSS JOIN permissions p "
            "WHERE r.name = 'production_supervisor' "
            "AND p.code IN ('production.access', 'production.admin') "
            "ON CONFLICT DO NOTHING"
        )
    )


def downgrade():
    # Preserve role assignments and audit history; revocation is an explicit admin action.
    pass
