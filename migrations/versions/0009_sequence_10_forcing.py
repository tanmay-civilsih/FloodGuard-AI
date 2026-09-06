"""Immutable forcing package registry."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_sequence_10_forcing"
down_revision: str | None = "0008_sequence_9_twin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "forcing_packages",
        sa.Column("forcing_package_id", sa.Uuid(), nullable=False),
        sa.Column("twin_id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.String(100), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("forcing_package_id"),
        sa.UniqueConstraint("fingerprint"),
    )
    op.create_index("ix_forcing_packages_city_id", "forcing_packages", ["city_id"])


def downgrade() -> None:
    op.drop_index("ix_forcing_packages_city_id", table_name="forcing_packages")
    op.drop_table("forcing_packages")
