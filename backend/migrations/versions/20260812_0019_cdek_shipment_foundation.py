"""Add immutable CDEK request and shipment foundation.

Revision ID: 20260812_0019
Revises: 20260812_0018
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260812_0019"
down_revision: str | Sequence[str] | None = "20260812_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "order_items",
        sa.Column("delivery_weight_kg_snapshot", sa.Numeric(precision=10, scale=3)),
    )
    op.add_column(
        "order_items",
        sa.Column("delivery_height_cm_snapshot", sa.Numeric(precision=10, scale=2)),
    )
    op.add_column(
        "order_items",
        sa.Column("delivery_width_cm_snapshot", sa.Numeric(precision=10, scale=2)),
    )
    op.add_column(
        "order_items",
        sa.Column("delivery_length_cm_snapshot", sa.Numeric(precision=10, scale=2)),
    )
    op.create_check_constraint(
        op.f("ck_order_items_order_item_delivery_measurements_complete"),
        "order_items",
        "(delivery_weight_kg_snapshot IS NULL "
        "AND delivery_height_cm_snapshot IS NULL "
        "AND delivery_width_cm_snapshot IS NULL "
        "AND delivery_length_cm_snapshot IS NULL) OR "
        "(delivery_weight_kg_snapshot > 0 "
        "AND delivery_height_cm_snapshot > 0 "
        "AND delivery_width_cm_snapshot > 0 "
        "AND delivery_length_cm_snapshot > 0)",
    )

    op.create_table(
        "cdek_shipments",
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("source_fulfillment_job_id", sa.Integer(), nullable=False),
        sa.Column("source_payment_attempt_id", sa.Integer(), nullable=False),
        sa.Column("client_order_number", sa.String(length=64), nullable=False),
        sa.Column("request_sha256", sa.String(length=64), nullable=False),
        sa.Column("request_schema_version", sa.Integer(), nullable=False),
        sa.Column("request_ciphertext", sa.Text(), nullable=False),
        sa.Column("request_nonce", sa.String(length=64), nullable=False),
        sa.Column("request_tag", sa.String(length=64), nullable=False),
        sa.Column("encryption_key_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("attempts_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("creation_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("creation_last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_uuid", sa.String(length=64), nullable=True),
        sa.Column("provider_cdek_number", sa.String(length=64), nullable=True),
        sa.Column("provider_status_code", sa.String(length=64), nullable=True),
        sa.Column("provider_status_name", sa.String(length=255), nullable=True),
        sa.Column("provider_status_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempts_count >= 0 AND attempts_count <= max_attempts",
            name=op.f("ck_cdek_shipments_cdek_shipment_attempts_valid"),
        ),
        sa.CheckConstraint(
            "(status = 'created' AND provider_uuid IS NOT NULL "
            "AND provider_created_at IS NOT NULL) OR "
            "(status <> 'created' AND provider_created_at IS NULL)",
            name=op.f("ck_cdek_shipments_cdek_shipment_created_evidence_consistent"),
        ),
        sa.CheckConstraint(
            "(status = 'processing' AND locked_at IS NOT NULL AND locked_by IS NOT NULL) OR "
            "(status <> 'processing' AND locked_at IS NULL AND locked_by IS NULL)",
            name=op.f("ck_cdek_shipments_cdek_shipment_lock_consistent"),
        ),
        sa.CheckConstraint(
            "max_attempts > 0 AND max_attempts <= 20",
            name=op.f("ck_cdek_shipments_cdek_shipment_max_attempts_valid"),
        ),
        sa.CheckConstraint(
            "length(request_sha256) = 64",
            name=op.f("ck_cdek_shipments_cdek_shipment_request_digest_length"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'unknown', 'retry', 'created', 'dead')",
            name=op.f("ck_cdek_shipments_cdek_shipment_status_valid"),
        ),
        sa.CheckConstraint(
            "request_schema_version > 0 AND encryption_key_version > 0",
            name=op.f("ck_cdek_shipments_cdek_shipment_versions_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_cdek_shipments_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_fulfillment_job_id"],
            ["fulfillment_jobs.id"],
            name=op.f("fk_cdek_shipments_source_fulfillment_job_id_fulfillment_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_payment_attempt_id"],
            ["payment_attempts.id"],
            name=op.f("fk_cdek_shipments_source_payment_attempt_id_payment_attempts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cdek_shipments")),
        sa.UniqueConstraint(
            "client_order_number", name=op.f("uq_cdek_shipments_client_order_number")
        ),
        sa.UniqueConstraint("order_id", name=op.f("uq_cdek_shipments_order_id")),
        sa.UniqueConstraint(
            "provider_cdek_number", name=op.f("uq_cdek_shipments_provider_cdek_number")
        ),
        sa.UniqueConstraint("provider_uuid", name=op.f("uq_cdek_shipments_provider_uuid")),
        sa.UniqueConstraint(
            "source_fulfillment_job_id",
            name=op.f("uq_cdek_shipments_source_fulfillment_job_id"),
        ),
    )
    op.create_index(
        "ix_cdek_shipments_dispatch",
        "cdek_shipments",
        ["status", "available_at"],
    )
    for column in (
        "available_at",
        "client_order_number",
        "order_id",
        "source_fulfillment_job_id",
        "source_payment_attempt_id",
        "status",
    ):
        op.create_index(op.f(f"ix_cdek_shipments_{column}"), "cdek_shipments", [column])

    op.create_table(
        "cdek_shipment_events",
        sa.Column("shipment_id", sa.Integer(), nullable=False),
        sa.Column("event_key", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("provider_status_code", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('prepared', 'create_started', 'create_unknown', "
            "'create_retry', 'created', 'create_dead', 'status_observed')",
            name=op.f("ck_cdek_shipment_events_cdek_shipment_event_type_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["shipment_id"],
            ["cdek_shipments.id"],
            name=op.f("fk_cdek_shipment_events_shipment_id_cdek_shipments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cdek_shipment_events")),
        sa.UniqueConstraint("event_key", name="uq_cdek_shipment_event_key"),
    )
    op.create_index(
        op.f("ix_cdek_shipment_events_event_type"),
        "cdek_shipment_events",
        ["event_type"],
    )
    op.create_index(
        op.f("ix_cdek_shipment_events_occurred_at"),
        "cdek_shipment_events",
        ["occurred_at"],
    )
    op.create_index(
        op.f("ix_cdek_shipment_events_shipment_id"),
        "cdek_shipment_events",
        ["shipment_id"],
    )


def downgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        shipments = bind.execute(sa.text("SELECT count(*) FROM cdek_shipments")).scalar_one()
        snapshots = bind.execute(
            sa.text(
                "SELECT count(*) FROM order_items "
                "WHERE delivery_weight_kg_snapshot IS NOT NULL "
                "OR delivery_height_cm_snapshot IS NOT NULL "
                "OR delivery_width_cm_snapshot IS NOT NULL "
                "OR delivery_length_cm_snapshot IS NOT NULL"
            )
        ).scalar_one()
        if shipments or snapshots:
            raise RuntimeError("Cannot downgrade CDEK foundation while durable evidence exists")

    op.drop_index(op.f("ix_cdek_shipment_events_shipment_id"), table_name="cdek_shipment_events")
    op.drop_index(op.f("ix_cdek_shipment_events_occurred_at"), table_name="cdek_shipment_events")
    op.drop_index(op.f("ix_cdek_shipment_events_event_type"), table_name="cdek_shipment_events")
    op.drop_table("cdek_shipment_events")
    for index_name in (
        "ix_cdek_shipments_status",
        "ix_cdek_shipments_source_payment_attempt_id",
        "ix_cdek_shipments_source_fulfillment_job_id",
        "ix_cdek_shipments_order_id",
        "ix_cdek_shipments_client_order_number",
        "ix_cdek_shipments_available_at",
        "ix_cdek_shipments_dispatch",
    ):
        op.drop_index(index_name, table_name="cdek_shipments")
    op.drop_table("cdek_shipments")

    op.drop_constraint(
        op.f("ck_order_items_order_item_delivery_measurements_complete"),
        "order_items",
        type_="check",
    )
    op.drop_column("order_items", "delivery_length_cm_snapshot")
    op.drop_column("order_items", "delivery_width_cm_snapshot")
    op.drop_column("order_items", "delivery_height_cm_snapshot")
    op.drop_column("order_items", "delivery_weight_kg_snapshot")
