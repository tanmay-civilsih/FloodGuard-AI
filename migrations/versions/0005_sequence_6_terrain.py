"""Create Sequence-6 conditioned terrain and multi-level structure products.

Revision ID: 0005_sequence_6_terrain
Revises: 0004_sequence_5_reconstruction
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_sequence_6_terrain"
down_revision: str | None = "0004_sequence_5_reconstruction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "terrain_products",
        sa.Column("terrain_id", sa.Uuid(), nullable=False),
        sa.Column("source_dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_object_id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.String(length=100), nullable=False),
        sa.Column("pilot_area_id", sa.String(length=160), nullable=False),
        sa.Column("source_object_key", sa.Text(), nullable=False),
        sa.Column("source_filename", sa.String(length=300), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("terrain_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("pipeline_version", sa.String(length=64), nullable=False),
        sa.Column("working_crs", sa.String(length=100), nullable=False),
        sa.Column("source_surface_type", sa.String(length=32), nullable=False),
        sa.Column("raw_elevation_object_key", sa.Text(), nullable=False),
        sa.Column("visual_terrain_object_key", sa.Text(), nullable=False),
        sa.Column("hydraulic_terrain_object_key", sa.Text(), nullable=False),
        sa.Column("multi_level_object_key", sa.Text(), nullable=False),
        sa.Column("qa_object_key", sa.Text(), nullable=False),
        sa.Column("audit_object_key", sa.Text(), nullable=False),
        sa.Column("raw_elevation_sha256", sa.String(length=64), nullable=False),
        sa.Column("visual_terrain_sha256", sa.String(length=64), nullable=False),
        sa.Column("hydraulic_terrain_sha256", sa.String(length=64), nullable=False),
        sa.Column("multi_level_sha256", sa.String(length=64), nullable=False),
        sa.Column("qa_sha256", sa.String(length=64), nullable=False),
        sa.Column("audit_sha256", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("bounds_working", sa.JSON(), nullable=False),
        sa.Column("native_horizontal_resolution_m", sa.Float(), nullable=False),
        sa.Column("computational_resolution_m", sa.Float(), nullable=False),
        sa.Column("effective_information_resolution_m", sa.Float(), nullable=False),
        sa.Column("vertical_quality", sa.String(length=64), nullable=False),
        sa.Column("vertical_datum", sa.Text(), nullable=True),
        sa.Column("vertical_unit", sa.String(length=32), nullable=True),
        sa.Column("datum_transform_status", sa.String(length=32), nullable=False),
        sa.Column("vertical_validation_method", sa.Text(), nullable=True),
        sa.Column("vertical_rmse_m", sa.Float(), nullable=True),
        sa.Column("control_point_count", sa.Integer(), nullable=False),
        sa.Column("road_sag_validation", sa.String(length=32), nullable=False),
        sa.Column("underpass_validation", sa.String(length=32), nullable=False),
        sa.Column("drain_rim_elevation_consistency", sa.String(length=32), nullable=False),
        sa.Column("validation_limitations", sa.JSON(), nullable=False),
        sa.Column("depression_assessment", sa.String(length=32), nullable=False),
        sa.Column("multi_level_assessment", sa.String(length=32), nullable=False),
        sa.Column("preserved_depression_count", sa.Integer(), nullable=False),
        sa.Column("filled_artifact_count", sa.Integer(), nullable=False),
        sa.Column("removed_obstruction_count", sa.Integer(), nullable=False),
        sa.Column("multi_level_structure_count", sa.Integer(), nullable=False),
        sa.Column("max_conditioning_adjustment_m", sa.Float(), nullable=False),
        sa.Column("readiness_status", sa.String(length=64), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("terrain_id"),
        sa.UniqueConstraint("terrain_fingerprint", name="uq_terrain_fingerprint"),
        sa.UniqueConstraint("visual_terrain_object_key"),
        sa.UniqueConstraint("hydraulic_terrain_object_key"),
        sa.UniqueConstraint("multi_level_object_key"),
        sa.UniqueConstraint("qa_object_key"),
        sa.UniqueConstraint("audit_object_key"),
    )
    op.create_index(
        "ix_terrain_products_source_dataset_version_id",
        "terrain_products",
        ["source_dataset_version_id"],
    )
    op.create_index("ix_terrain_products_source_id", "terrain_products", ["source_id"])
    op.create_index(
        "ix_terrain_products_source_object_id",
        "terrain_products",
        ["source_object_id"],
    )
    op.create_index("ix_terrain_products_city_id", "terrain_products", ["city_id"])
    op.create_index("ix_terrain_products_pilot_area_id", "terrain_products", ["pilot_area_id"])
    op.create_index(
        "ix_terrain_products_readiness_status",
        "terrain_products",
        ["readiness_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_terrain_products_readiness_status", table_name="terrain_products")
    op.drop_index("ix_terrain_products_pilot_area_id", table_name="terrain_products")
    op.drop_index("ix_terrain_products_city_id", table_name="terrain_products")
    op.drop_index("ix_terrain_products_source_object_id", table_name="terrain_products")
    op.drop_index("ix_terrain_products_source_id", table_name="terrain_products")
    op.drop_index(
        "ix_terrain_products_source_dataset_version_id",
        table_name="terrain_products",
    )
    op.drop_table("terrain_products")
