"""Dedicated terminal administrator role; floor staff receive no new privileges."""

import sqlalchemy as sa
from alembic import op

revision = "20260909_0037"
down_revision = "20260909_0036"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            "INSERT INTO permissions (code, description) VALUES ('production.admin', 'Production administration') ON CONFLICT (code) DO NOTHING"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO roles (name, description, is_system) VALUES ('production_admin', 'Production administrator', true) ON CONFLICT (name) DO NOTHING"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) SELECT r.id, p.id FROM roles r CROSS JOIN permissions p WHERE (r.name = 'production_admin' AND p.code IN ('production.access', 'production.admin')) OR (r.name = 'admin' AND p.code = 'production.admin') ON CONFLICT DO NOTHING"
        )
    )


def downgrade():
    # Preserve assignments and audit history; disable access explicitly before rollback.
    pass
