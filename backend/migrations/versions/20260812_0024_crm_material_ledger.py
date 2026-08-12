"""Add append-only CRM material ledger and reservations.

Revision ID: 20260812_0024
Revises: 20260812_0023
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260812_0024"
down_revision: str | Sequence[str] | None = "20260812_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "crm_material_balances",
        sa.Column("fabric_id", sa.Integer(), nullable=False),
        sa.Column("on_hand_meters", sa.Numeric(14, 3), server_default="0", nullable=False),
        sa.Column("reserved_meters", sa.Numeric(14, 3), server_default="0", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "on_hand_meters >= 0",
            name=op.f("ck_crm_material_balances_crm_material_balance_on_hand_nonnegative"),
        ),
        sa.CheckConstraint(
            "reserved_meters >= 0",
            name=op.f("ck_crm_material_balances_crm_material_balance_reserved_nonnegative"),
        ),
        sa.CheckConstraint(
            "reserved_meters <= on_hand_meters",
            name=op.f("ck_crm_material_balances_crm_material_balance_reserved_not_above_on_hand"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_crm_material_balances_crm_material_balance_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["fabric_id"],
            ["crm_fabrics.id"],
            name=op.f("fk_crm_material_balances_fabric_id_crm_fabrics"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("fabric_id", name=op.f("pk_crm_material_balances")),
    )

    op.create_table(
        "crm_material_reservations",
        sa.Column("production_plan_revision_id", sa.Integer(), nullable=False),
        sa.Column("fabric_id", sa.Integer(), nullable=False),
        sa.Column("requested_meters", sa.Numeric(14, 3), nullable=False),
        sa.Column("remaining_meters", sa.Numeric(14, 3), nullable=False),
        sa.Column("consumed_meters", sa.Numeric(14, 3), server_default="0", nullable=False),
        sa.Column("released_meters", sa.Numeric(14, 3), server_default="0", nullable=False),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "requested_meters > 0",
            name=op.f("ck_crm_material_reservations_crm_material_reservation_requested_positive"),
        ),
        sa.CheckConstraint(
            "remaining_meters >= 0 AND consumed_meters >= 0 AND released_meters >= 0",
            name=op.f(
                "ck_crm_material_reservations_crm_material_reservation_quantities_nonnegative"
            ),
        ),
        sa.CheckConstraint(
            "requested_meters = remaining_meters + consumed_meters + released_meters",
            name=op.f(
                "ck_crm_material_reservations_crm_material_reservation_accounting_consistent"
            ),
        ),
        sa.CheckConstraint(
            "(status = 'active' AND remaining_meters > 0) OR "
            "(status = 'closed' AND remaining_meters = 0)",
            name=op.f("ck_crm_material_reservations_crm_material_reservation_status_consistent"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_crm_material_reservations_crm_material_reservation_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_crm_material_reservations_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["fabric_id"],
            ["crm_fabrics.id"],
            name=op.f("fk_crm_material_reservations_fabric_id_crm_fabrics"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["production_plan_revision_id"],
            ["crm_production_plan_revisions.id"],
            name=op.f(
                "fk_crm_material_reservations_production_plan_revision_id_crm_production_plan_revisions"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_material_reservations")),
        sa.UniqueConstraint(
            "production_plan_revision_id",
            "fabric_id",
            name="uq_crm_material_reservation_plan_fabric",
        ),
    )
    for column in ("created_by_user_id", "fabric_id", "production_plan_revision_id", "status"):
        op.create_index(
            op.f(f"ix_crm_material_reservations_{column}"),
            "crm_material_reservations",
            [column],
        )

    op.create_table(
        "crm_material_movements",
        sa.Column("fabric_id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=True),
        sa.Column("movement_type", sa.String(24), nullable=False),
        sa.Column("quantity_meters", sa.Numeric(14, 3), nullable=False),
        sa.Column("balance_on_hand_after", sa.Numeric(14, 3), nullable=False),
        sa.Column("balance_reserved_after", sa.Numeric(14, 3), nullable=False),
        sa.Column("idempotency_key_sha256", sa.String(64), nullable=False),
        sa.Column("command_sha256", sa.String(64), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "movement_type IN ('receipt', 'reserve', 'release', 'consume', "
            "'adjustment_in', 'adjustment_out')",
            name=op.f("ck_crm_material_movements_crm_material_movement_type_valid"),
        ),
        sa.CheckConstraint(
            "quantity_meters > 0",
            name=op.f("ck_crm_material_movements_crm_material_movement_quantity_positive"),
        ),
        sa.CheckConstraint(
            "balance_on_hand_after >= 0 AND balance_reserved_after >= 0 "
            "AND balance_reserved_after <= balance_on_hand_after",
            name=op.f("ck_crm_material_movements_crm_material_movement_balance_valid"),
        ),
        sa.CheckConstraint(
            "length(idempotency_key_sha256) = 64 AND length(command_sha256) = 64",
            name=op.f("ck_crm_material_movements_crm_material_movement_digests_valid"),
        ),
        sa.CheckConstraint(
            "(movement_type IN ('reserve', 'release', 'consume') AND reservation_id IS NOT NULL) OR "
            "(movement_type IN ('receipt', 'adjustment_in', 'adjustment_out') AND reservation_id IS NULL)",
            name=op.f("ck_crm_material_movements_crm_material_movement_reservation_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_crm_material_movements_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["fabric_id"],
            ["crm_fabrics.id"],
            name=op.f("fk_crm_material_movements_fabric_id_crm_fabrics"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"],
            ["crm_material_reservations.id"],
            name=op.f("fk_crm_material_movements_reservation_id_crm_material_reservations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_material_movements")),
        sa.UniqueConstraint(
            "fabric_id",
            "idempotency_key_sha256",
            name="uq_crm_material_movement_fabric_key",
        ),
    )
    for column in (
        "actor_user_id",
        "fabric_id",
        "idempotency_key_sha256",
        "movement_type",
        "occurred_at",
        "reservation_id",
    ):
        op.create_index(
            op.f(f"ix_crm_material_movements_{column}"), "crm_material_movements", [column]
        )


def downgrade() -> None:
    if not context.is_offline_mode():
        rows = (
            op.get_bind()
            .execute(
                sa.text(
                    "SELECT (SELECT count(*) FROM crm_material_movements) + "
                    "(SELECT count(*) FROM crm_material_reservations) + "
                    "(SELECT count(*) FROM crm_material_balances)"
                )
            )
            .scalar_one()
        )
        if rows:
            raise RuntimeError("Cannot downgrade CRM material ledger while durable evidence exists")
    for name in (
        "ix_crm_material_movements_reservation_id",
        "ix_crm_material_movements_occurred_at",
        "ix_crm_material_movements_movement_type",
        "ix_crm_material_movements_idempotency_key_sha256",
        "ix_crm_material_movements_fabric_id",
        "ix_crm_material_movements_actor_user_id",
    ):
        op.drop_index(name, table_name="crm_material_movements")
    op.drop_table("crm_material_movements")
    for name in (
        "ix_crm_material_reservations_status",
        "ix_crm_material_reservations_production_plan_revision_id",
        "ix_crm_material_reservations_fabric_id",
        "ix_crm_material_reservations_created_by_user_id",
    ):
        op.drop_index(name, table_name="crm_material_reservations")
    op.drop_table("crm_material_reservations")
    op.drop_table("crm_material_balances")
