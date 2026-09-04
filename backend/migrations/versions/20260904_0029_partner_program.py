"""Add partner attribution, commissions, landings, and payout requests.

Revision ID: 20260904_0029
Revises: 20260904_0028
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260904_0029"
down_revision: str | Sequence[str] | None = "20260904_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    _seed_partner_authorization()

    op.create_table(
        "partner_profiles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'invited'"),
            nullable=False,
        ),
        sa.Column("commission_bps", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "commission_bps >= 0 AND commission_bps <= 10000",
            name=op.f("ck_partner_profiles_partner_profile_commission_bps_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('invited', 'active', 'suspended')",
            name=op.f("ck_partner_profiles_partner_profile_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_partner_profiles_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_profiles")),
        sa.UniqueConstraint("code", name=op.f("uq_partner_profiles_code")),
        sa.UniqueConstraint("user_id", name=op.f("uq_partner_profiles_user_id")),
    )
    op.create_index(op.f("ix_partner_profiles_code"), "partner_profiles", ["code"])
    op.create_index(op.f("ix_partner_profiles_status"), "partner_profiles", ["status"])
    op.create_index(op.f("ix_partner_profiles_user_id"), "partner_profiles", ["user_id"])

    op.create_table(
        "partner_landings",
        sa.Column("partner_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=96), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("eyebrow", sa.String(length=120), nullable=True),
        sa.Column("headline", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("cta_label", sa.String(length=80), nullable=False),
        sa.Column("cta_href", sa.String(length=2048), nullable=False),
        sa.Column("image_url", sa.String(length=4096), nullable=True),
        sa.Column("product_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name=op.f("ck_partner_landings_partner_landing_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["partner_profiles.id"],
            name=op.f("fk_partner_landings_partner_id_partner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_landings")),
        sa.UniqueConstraint("slug", name=op.f("uq_partner_landings_slug")),
    )
    op.create_index(
        op.f("ix_partner_landings_partner_id"), "partner_landings", ["partner_id"]
    )
    op.create_index(op.f("ix_partner_landings_slug"), "partner_landings", ["slug"])
    op.create_index(op.f("ix_partner_landings_status"), "partner_landings", ["status"])

    op.create_table(
        "partner_visits",
        sa.Column("landing_id", sa.Integer(), nullable=False),
        sa.Column("visitor_digest", sa.String(length=64), nullable=False),
        sa.Column("visited_on", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "length(visitor_digest) = 64",
            name=op.f("ck_partner_visits_partner_visit_digest_length"),
        ),
        sa.ForeignKeyConstraint(
            ["landing_id"],
            ["partner_landings.id"],
            name=op.f("fk_partner_visits_landing_id_partner_landings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_visits")),
        sa.UniqueConstraint(
            "landing_id",
            "visitor_digest",
            "visited_on",
            name="uq_partner_visit_daily_visitor",
        ),
    )
    op.create_index(
        "ix_partner_visits_landing_created",
        "partner_visits",
        ["landing_id", "created_at"],
    )
    op.create_index(op.f("ix_partner_visits_landing_id"), "partner_visits", ["landing_id"])

    op.create_table(
        "partner_order_attributions",
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("partner_id", sa.Integer(), nullable=False),
        sa.Column("landing_id", sa.Integer(), nullable=False),
        sa.Column("commission_bps_snapshot", sa.Integer(), nullable=False),
        sa.Column("order_amount_snapshot", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "commission_base_snapshot",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default=sa.text("'RUB'"),
            nullable=False,
        ),
        sa.Column("attributed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "commission_base_snapshot >= 0",
            name=op.f("ck_partner_order_attributions_partner_attribution_commission_base_nonnegative"),
        ),
        sa.CheckConstraint(
            "commission_bps_snapshot >= 0 AND commission_bps_snapshot <= 10000",
            name=op.f("ck_partner_order_attributions_partner_attribution_commission_bps_valid"),
        ),
        sa.CheckConstraint(
            "currency = 'RUB'",
            name=op.f("ck_partner_order_attributions_partner_attribution_currency_rub"),
        ),
        sa.CheckConstraint(
            "order_amount_snapshot >= 0",
            name=op.f("ck_partner_order_attributions_partner_attribution_order_amount_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["landing_id"],
            ["partner_landings.id"],
            name=op.f("fk_partner_order_attributions_landing_id_partner_landings"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_partner_order_attributions_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["partner_profiles.id"],
            name=op.f("fk_partner_order_attributions_partner_id_partner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_order_attributions")),
        sa.UniqueConstraint("order_id", name=op.f("uq_partner_order_attributions_order_id")),
    )
    for column in ("landing_id", "order_id", "partner_id"):
        op.create_index(
            op.f(f"ix_partner_order_attributions_{column}"),
            "partner_order_attributions",
            [column],
        )

    op.create_table(
        "partner_commissions",
        sa.Column("attribution_id", sa.Integer(), nullable=False),
        sa.Column("partner_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default=sa.text("'RUB'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.String(length=128), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "amount >= 0",
            name=op.f("ck_partner_commissions_partner_commission_amount_nonnegative"),
        ),
        sa.CheckConstraint(
            "currency = 'RUB'",
            name=op.f("ck_partner_commissions_partner_commission_currency_rub"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'canceled')",
            name=op.f("ck_partner_commissions_partner_commission_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["attribution_id"],
            ["partner_order_attributions.id"],
            name=op.f("fk_partner_commissions_attribution_id_partner_order_attributions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_partner_commissions_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["partner_profiles.id"],
            name=op.f("fk_partner_commissions_partner_id_partner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_commissions")),
        sa.UniqueConstraint(
            "attribution_id", name=op.f("uq_partner_commissions_attribution_id")
        ),
        sa.UniqueConstraint("order_id", name=op.f("uq_partner_commissions_order_id")),
    )
    for column in ("attribution_id", "available_at", "order_id", "partner_id", "status"):
        op.create_index(
            op.f(f"ix_partner_commissions_{column}"),
            "partner_commissions",
            [column],
        )

    op.create_table(
        "partner_payout_requests",
        sa.Column("partner_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default=sa.text("'RUB'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'requested'"),
            nullable=False,
        ),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "amount > 0",
            name=op.f("ck_partner_payout_requests_partner_payout_amount_positive"),
        ),
        sa.CheckConstraint(
            "currency = 'RUB'",
            name=op.f("ck_partner_payout_requests_partner_payout_currency_rub"),
        ),
        sa.CheckConstraint(
            "status IN ('requested', 'approved', 'paid', 'rejected', 'canceled')",
            name=op.f("ck_partner_payout_requests_partner_payout_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["partner_profiles.id"],
            name=op.f("fk_partner_payout_requests_partner_id_partner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["users.id"],
            name=op.f("fk_partner_payout_requests_reviewed_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_payout_requests")),
    )
    op.create_index(
        op.f("ix_partner_payout_requests_partner_id"),
        "partner_payout_requests",
        ["partner_id"],
    )
    op.create_index(
        op.f("ix_partner_payout_requests_status"),
        "partner_payout_requests",
        ["status"],
    )


def _seed_partner_authorization() -> None:
    op.execute(
        sa.text(
            "INSERT INTO roles (name, description, is_system) "
            "VALUES ('partner', 'Partner cabinet user', true) "
            "ON CONFLICT (name) DO NOTHING"
        )
    )
    for code in ("partners.read_own", "partners.manage"):
        op.execute(
            sa.text(
                "INSERT INTO permissions (code, description) VALUES (:code, :code) "
                "ON CONFLICT (code) DO NOTHING"
            ).bindparams(code=code)
        )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT roles.id, permissions.id FROM roles CROSS JOIN permissions "
            "WHERE roles.name = 'partner' AND permissions.code IN "
            "('profile.read_own', 'profile.write_own', 'orders.read_own', "
            "'partners.read_own') ON CONFLICT DO NOTHING"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT roles.id, permissions.id FROM roles CROSS JOIN permissions "
            "WHERE roles.name = 'manager' AND permissions.code = 'partners.manage' "
            "ON CONFLICT DO NOTHING"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT roles.id, permissions.id FROM roles CROSS JOIN permissions "
            "WHERE roles.name = 'admin' AND permissions.code IN "
            "('partners.read_own', 'partners.manage') ON CONFLICT DO NOTHING"
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_partner_payout_requests_status"), table_name="partner_payout_requests")
    op.drop_index(
        op.f("ix_partner_payout_requests_partner_id"), table_name="partner_payout_requests"
    )
    op.drop_table("partner_payout_requests")
    for column in ("status", "partner_id", "order_id", "available_at", "attribution_id"):
        op.drop_index(
            op.f(f"ix_partner_commissions_{column}"), table_name="partner_commissions"
        )
    op.drop_table("partner_commissions")
    for column in ("partner_id", "order_id", "landing_id"):
        op.drop_index(
            op.f(f"ix_partner_order_attributions_{column}"),
            table_name="partner_order_attributions",
        )
    op.drop_table("partner_order_attributions")
    op.drop_index(op.f("ix_partner_visits_landing_id"), table_name="partner_visits")
    op.drop_index("ix_partner_visits_landing_created", table_name="partner_visits")
    op.drop_table("partner_visits")
    op.drop_index(op.f("ix_partner_landings_status"), table_name="partner_landings")
    op.drop_index(op.f("ix_partner_landings_slug"), table_name="partner_landings")
    op.drop_index(op.f("ix_partner_landings_partner_id"), table_name="partner_landings")
    op.drop_table("partner_landings")
    op.drop_index(op.f("ix_partner_profiles_user_id"), table_name="partner_profiles")
    op.drop_index(op.f("ix_partner_profiles_status"), table_name="partner_profiles")
    op.drop_index(op.f("ix_partner_profiles_code"), table_name="partner_profiles")
    op.drop_table("partner_profiles")

    op.execute(
        "DELETE FROM role_permissions WHERE role_id IN "
        "(SELECT id FROM roles WHERE name = 'partner') OR permission_id IN "
        "(SELECT id FROM permissions WHERE code IN ('partners.read_own', 'partners.manage'))"
    )
    op.execute("DELETE FROM user_roles WHERE role_id IN (SELECT id FROM roles WHERE name = 'partner')")
    op.execute("DELETE FROM roles WHERE name = 'partner'")
    op.execute("DELETE FROM permissions WHERE code IN ('partners.read_own', 'partners.manage')")
