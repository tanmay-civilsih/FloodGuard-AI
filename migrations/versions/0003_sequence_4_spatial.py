"""Create Sequence-4 normalized spatial layer metadata.

Revision ID: 0003_sequence_4_spatial
Revises: 0002_sequence_3_harvester
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_sequence_4_spatial"
down_revision: str | None = "0002_sequence_3_harvester"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spatial_layers",
        sa.Column("normalization_id", sa.Uuid(), nullable=False),
        sa.Column("source_dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.String(length=100), nullable=False),
        sa.Column("source_category", sa.String(length=64), nullable=False),
        sa.Column("layer_name", sa.String(length=240), nullable=False),
        sa.Column("variable_kind", sa.String(length=32), nullable=False),
        sa.Column("source_crs", sa.String(length=100), nullable=False),
        sa.Column("working_crs", sa.String(length=100), nullable=False),
        sa.Column("source_object_key", sa.Text(), nullable=False),
        sa.Column("normalized_object_key", sa.Text(), nullable=False),
        sa.Column("qa_object_key", sa.Text(), nullable=False),
        sa.Column("normalized_sha256", sa.String(length=64), nullable=False),
        sa.Column("normalization_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("feature_count", sa.Integer(), nullable=False),
        sa.Column("geometry_types", sa.JSON(), nullable=False),
        sa.Column("bounds_working", sa.JSON(), nullable=False),
        sa.Column("bounds_wgs84", sa.JSON(), nullable=False),
        sa.Column("max_roundtrip_error_m", sa.Float(), nullable=False),
        sa.Column("resampling_policy", sa.String(length=64), nullable=False),
        sa.Column("vertical_datum", sa.Text(), nullable=True),
        sa.Column("vertical_unit", sa.String(length=32), nullable=True),
        sa.Column("vertical_offset_m", sa.Float(), nullable=True),
        sa.Column("datum_transform_status", sa.String(length=32), nullable=False),
        sa.Column("vertical_reference_confidence", sa.String(length=32), nullable=False),
        sa.Column("native_resolution_m", sa.Float(), nullable=True),
        sa.Column("computational_resolution_m", sa.Float(), nullable=True),
        sa.Column("effective_information_resolution_m", sa.Float(), nullable=True),
        sa.Column("source_quality", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("normalization_id"),
        sa.UniqueConstraint("normalized_object_key"),
        sa.UniqueConstraint("qa_object_key"),
        sa.UniqueConstraint(
            "normalization_fingerprint",
            name="uq_spatial_normalization_fingerprint",
        ),
    )
    op.create_index(
        "ix_spatial_layers_source_dataset_version_id",
        "spatial_layers",
        ["source_dataset_version_id"],
    )
    op.create_index("ix_spatial_layers_source_id", "spatial_layers", ["source_id"])
    op.create_index("ix_spatial_layers_city_id", "spatial_layers", ["city_id"])
    op.create_index(
        "ix_spatial_layers_source_category",
        "spatial_layers",
        ["source_category"],
    )
    op.create_index("ix_spatial_layers_working_crs", "spatial_layers", ["working_crs"])


def downgrade() -> None:
    op.drop_index("ix_spatial_layers_working_crs", table_name="spatial_layers")
    op.drop_index("ix_spatial_layers_source_category", table_name="spatial_layers")
    op.drop_index("ix_spatial_layers_city_id", table_name="spatial_layers")
    op.drop_index("ix_spatial_layers_source_id", table_name="spatial_layers")
    op.drop_index("ix_spatial_layers_source_dataset_version_id", table_name="spatial_layers")
    op.drop_table("spatial_layers")
