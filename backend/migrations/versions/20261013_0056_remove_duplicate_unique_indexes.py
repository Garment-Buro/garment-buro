"""Remove secondary indexes already covered by single-column UNIQUE constraints.

Revision ID: 20261013_0056
Revises: 20260929_0055
"""

from alembic import op

revision = "20261013_0056"
down_revision = "20260929_0055"
branch_labels = None
depends_on = None

# Historical migrations created both a UNIQUE constraint (with its own backing
# index) and a non-unique index on the same column. Preserve all constraints and
# their names; only the redundant non-unique structures are removed.
REDUNDANT_INDEXES = (
    ("carts", "token_digest_sha256"),
    ("cdek_shipments", "client_order_number"),
    ("cdek_shipments", "order_id"),
    ("cdek_shipments", "source_fulfillment_job_id"),
    ("crm_file_attachments", "media_object_id"),
    ("crm_order_projects", "order_id"),
    ("crm_order_projects", "source_fulfillment_job_id"),
    ("legacy_order_imports", "order_id"),
    ("legacy_order_imports", "source_order_id"),
    ("order_creation_requests", "key_digest_sha256"),
    ("order_creation_requests", "order_id"),
    ("order_guest_access", "order_id"),
    ("order_guest_access", "token_digest_sha256"),
    ("partner_commissions", "attribution_id"),
    ("partner_commissions", "order_id"),
    ("partner_landings", "slug"),
    ("partner_order_attributions", "order_id"),
    ("partner_profiles", "code"),
    ("partner_profiles", "user_id"),
    ("partner_requisites", "partner_id"),
    ("production_employees", "user_id"),
    ("refresh_sessions", "session_id"),
    ("users", "email_normalized"),
    ("users", "telegram_id"),
)


def upgrade() -> None:
    for table, column in REDUNDANT_INDEXES:
        op.drop_index(f"ix_{table}_{column}", table_name=table)


def downgrade() -> None:
    for table, column in reversed(REDUNDANT_INDEXES):
        op.create_index(f"ix_{table}_{column}", table, [column], unique=False)
