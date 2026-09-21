"""Persistent ticket conversations, keeping existing inbox records intact."""

import sqlalchemy as sa
from alembic import op

revision = "20260921_0046"
down_revision = "20260918_0045"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("admin_inbox_items", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_inbox_creator",
        "admin_inbox_items",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "ticket_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("admin_inbox_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("author_role", sa.String(16), nullable=False),
        sa.Column("visibility", sa.String(16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("visibility IN ('public','internal')", name="ticket_visibility_valid"),
        sa.CheckConstraint(
            "author_role IN ('customer','admin','employee','system')", name="ticket_author_valid"
        ),
    )
    op.create_index("ix_ticket_messages_ticket_id_id", "ticket_messages", ["ticket_id", "id"])


def downgrade():
    op.drop_table("ticket_messages")
    op.drop_constraint("fk_inbox_creator", "admin_inbox_items", type_="foreignkey")
    op.drop_column("admin_inbox_items", "created_by_user_id")
