"""Create immutable twin version metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_sequence_9_twin"
down_revision: str | None = "0007_sequence_8_drain_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "twin_versions",
        sa.Column("twin_id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.String(100), nullable=False),
        sa.Column("pilot_area_id", sa.String(160), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("pipeline_version", sa.String(64), nullable=False),
        sa.Column("evidence_scope", sa.String(64), nullable=False),
        sa.Column("hydraulic_readiness", sa.String(40), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("audit", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("twin_id"),
        sa.UniqueConstraint("fingerprint"),
    )
    op.create_index("ix_twin_versions_city_id", "twin_versions", ["city_id"])


def downgrade() -> None:
    op.drop_index("ix_twin_versions_city_id", table_name="twin_versions")
    op.drop_table("twin_versions")
