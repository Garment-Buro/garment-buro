"""Retained constructor file references, independent of presigned URL lifetime.

Revision ID: 20261017_0069
Revises: 20261017_0068
"""

import sqlalchemy as sa
from alembic import op

revision = "20261017_0069"
down_revision = "20261017_0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "design_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "media_object_id",
            sa.Integer(),
            sa.ForeignKey("media_objects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("access_digest_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("length(access_digest_sha256) = 64", name="design_asset_digest_length"),
    )
    op.create_index("ix_design_assets_media_object_id", "design_assets", ["media_object_id"])
    op.create_index("ix_design_assets_expiry", "design_assets", ["expires_at", "id"])
    for name, owner, column in [
        ("cart_design_assets", "carts", "cart_id"),
        ("order_design_assets", "orders", "order_id"),
    ]:
        op.create_table(
            name,
            sa.Column(
                column,
                sa.Integer(),
                sa.ForeignKey(f"{owner}.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "design_asset_id",
                sa.Integer(),
                sa.ForeignKey("design_assets.id", ondelete="RESTRICT"),
                primary_key=True,
            ),
        )
        op.create_index(f"ix_{name}_design_asset_id", name, ["design_asset_id"])


def downgrade() -> None:
    # Reverting the schema must not silently remove retention of accepted designs.
    if op.get_context().dialect.name == "postgresql":
        op.execute("""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM design_assets) THEN
                RAISE EXCEPTION 'Cannot downgrade while design assets are retained';
            END IF;
        END $$""")
    elif op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM design_assets)")):
        raise RuntimeError("Cannot downgrade while design assets are retained")
    for name in ["order_design_assets", "cart_design_assets", "design_assets"]:
        op.drop_table(name)
