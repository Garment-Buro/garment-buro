"""Replace browser-clock ordering with opaque cart revisions and exact replay.

Revision ID: 20261017_0068
Revises: 20261017_0067
"""

import sqlalchemy as sa
from alembic import op

revision = "20261017_0068"
down_revision = "20261017_0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("carts") as batch:
        batch.drop_constraint(op.f("ck_carts_cart_client_updated_nonnegative"), type_="check")
        batch.drop_constraint(op.f("ck_carts_cart_version_positive"), type_="check")
        batch.alter_column(
            "client_updated_at_ms",
            new_column_name="updated_at_ms",
            existing_type=sa.BigInteger(),
            nullable=False,
        )
        batch.drop_column("version")
        batch.add_column(sa.Column("revision", sa.String(32), nullable=True))
        batch.add_column(sa.Column("last_operation_id", sa.String(32), nullable=True))
        batch.add_column(sa.Column("last_write_sha256", sa.String(64), nullable=True))
        batch.create_check_constraint("cart_updated_nonnegative", "updated_at_ms >= 0")
        batch.create_check_constraint(
            "cart_revision_length", "revision IS NULL OR length(revision) = 32"
        )
        batch.create_check_constraint(
            "cart_operation_length", "last_operation_id IS NULL OR length(last_operation_id) = 32"
        )
        batch.create_check_constraint(
            "cart_write_digest_length",
            "last_write_sha256 IS NULL OR length(last_write_sha256) = 64",
        )
    random_revision = (
        "replace(gen_random_uuid()::text, '-', '')"
        if op.get_bind().dialect.name == "postgresql"
        else "lower(hex(randomblob(16)))"
    )
    op.execute(sa.text(f"UPDATE carts SET revision = {random_revision}"))


def downgrade() -> None:
    with op.batch_alter_table("carts") as batch:
        for name in [
            "cart_updated_nonnegative",
            "cart_revision_length",
            "cart_operation_length",
            "cart_write_digest_length",
        ]:
            batch.drop_constraint(op.f("ck_carts_" + name), type_="check")
        batch.drop_column("revision")
        batch.drop_column("last_operation_id")
        batch.drop_column("last_write_sha256")
        batch.alter_column(
            "updated_at_ms",
            new_column_name="client_updated_at_ms",
            existing_type=sa.BigInteger(),
            nullable=False,
        )
        batch.add_column(sa.Column("version", sa.Integer(), server_default="1", nullable=False))
        batch.create_check_constraint(
            "cart_client_updated_nonnegative", "client_updated_at_ms >= 0"
        )
        batch.create_check_constraint("cart_version_positive", "version > 0")
