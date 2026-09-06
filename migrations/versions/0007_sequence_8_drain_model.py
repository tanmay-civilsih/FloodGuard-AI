"""Create immutable Sequence 8 drain products; preserve all predecessor tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_sequence_8_drain_model"
down_revision: str | None = "0006_sequence_7_urban_gis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "drain_model_products",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.String(100), nullable=False),
        sa.Column("pilot_area_id", sa.String(160), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("pipeline_version", sa.String(64), nullable=False),
        sa.Column("product_kind", sa.String(32), nullable=False),
        sa.Column("evidence_scope", sa.String(64), nullable=False),
        sa.Column("working_crs", sa.String(100), nullable=False),
        sa.Column("artifacts", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("product_id"),
        sa.UniqueConstraint("fingerprint"),
    )
    op.create_index("ix_drain_model_products_city_id", "drain_model_products", ["city_id"])


def downgrade() -> None:
    op.drop_index("ix_drain_model_products_city_id", table_name="drain_model_products")
    op.drop_table("drain_model_products")
