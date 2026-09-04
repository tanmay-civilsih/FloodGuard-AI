"""Create Sequence-5 drainage reconstruction and review records.

Revision ID: 0004_sequence_5_reconstruction
Revises: 0003_sequence_4_spatial
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_sequence_5_reconstruction"
down_revision: str | None = "0003_sequence_4_spatial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "drainage_reconstructions",
        sa.Column("reconstruction_id", sa.Uuid(), nullable=False),
        sa.Column("source_dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_object_id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.String(length=100), nullable=False),
        sa.Column("ward_id", sa.String(length=32), nullable=False),
        sa.Column("source_authority", sa.String(length=64), nullable=False),
        sa.Column("source_object_key", sa.Text(), nullable=False),
        sa.Column("source_filename", sa.String(length=300), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("reconstruction_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("pipeline_version", sa.String(length=64), nullable=False),
        sa.Column("calibration_id", sa.String(length=160), nullable=False),
        sa.Column("working_crs", sa.String(length=100), nullable=False),
        sa.Column("georeference_method", sa.String(length=160), nullable=False),
        sa.Column("affine_coefficients", sa.JSON(), nullable=False),
        sa.Column("control_points", sa.JSON(), nullable=False),
        sa.Column("georeference_rmse_m", sa.Float(), nullable=False),
        sa.Column("georeference_max_error_m", sa.Float(), nullable=False),
        sa.Column("georeference_tolerance_m", sa.Float(), nullable=False),
        sa.Column("native_inspection", sa.JSON(), nullable=False),
        sa.Column("working_object_key", sa.Text(), nullable=False),
        sa.Column("qa_object_key", sa.Text(), nullable=False),
        sa.Column("audit_object_key", sa.Text(), nullable=False),
        sa.Column("working_sha256", sa.String(length=64), nullable=False),
        sa.Column("qa_sha256", sa.String(length=64), nullable=False),
        sa.Column("audit_sha256", sa.String(length=64), nullable=False),
        sa.Column("feature_count", sa.Integer(), nullable=False),
        sa.Column("drain_count", sa.Integer(), nullable=False),
        sa.Column("structure_count", sa.Integer(), nullable=False),
        sa.Column("label_count", sa.Integer(), nullable=False),
        sa.Column("bounds_working", sa.JSON(), nullable=False),
        sa.Column("bounds_wgs84", sa.JSON(), nullable=False),
        sa.Column("confidence_summary", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewed_by", sa.String(length=200), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("reconstruction_id"),
        sa.UniqueConstraint("working_object_key"),
        sa.UniqueConstraint("qa_object_key"),
        sa.UniqueConstraint("audit_object_key"),
        sa.UniqueConstraint(
            "reconstruction_fingerprint",
            name="uq_drainage_reconstruction_fingerprint",
        ),
    )
    op.create_index(
        "ix_drainage_reconstructions_source_dataset_version_id",
        "drainage_reconstructions",
        ["source_dataset_version_id"],
    )
    op.create_index(
        "ix_drainage_reconstructions_source_id",
        "drainage_reconstructions",
        ["source_id"],
    )
    op.create_index(
        "ix_drainage_reconstructions_city_id",
        "drainage_reconstructions",
        ["city_id"],
    )
    op.create_index(
        "ix_drainage_reconstructions_ward_id",
        "drainage_reconstructions",
        ["ward_id"],
    )
    op.create_index(
        "ix_drainage_reconstructions_status",
        "drainage_reconstructions",
        ["status"],
    )
    op.create_table(
        "reconstruction_reviews",
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("reconstruction_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reviewer", sa.String(length=200), nullable=False),
        sa.Column("reviewer_type", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("checklist", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["reconstruction_id"],
            ["drainage_reconstructions.reconstruction_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("review_id"),
    )
    op.create_index(
        "ix_reconstruction_reviews_reconstruction_id",
        "reconstruction_reviews",
        ["reconstruction_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reconstruction_reviews_reconstruction_id",
        table_name="reconstruction_reviews",
    )
    op.drop_table("reconstruction_reviews")
    op.drop_index("ix_drainage_reconstructions_status", table_name="drainage_reconstructions")
    op.drop_index("ix_drainage_reconstructions_ward_id", table_name="drainage_reconstructions")
    op.drop_index("ix_drainage_reconstructions_city_id", table_name="drainage_reconstructions")
    op.drop_index("ix_drainage_reconstructions_source_id", table_name="drainage_reconstructions")
    op.drop_index(
        "ix_drainage_reconstructions_source_dataset_version_id",
        table_name="drainage_reconstructions",
    )
    op.drop_table("drainage_reconstructions")

