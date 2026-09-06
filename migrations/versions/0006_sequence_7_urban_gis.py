"""Create Sequence-7 urban GIS visual/hydraulic/roof-runoff products.

Revision ID: 0006_sequence_7_urban_gis
Revises: 0005_sequence_6_terrain
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_sequence_7_urban_gis"
down_revision: str | None = "0005_sequence_6_terrain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "urban_gis_products",
        sa.Column("urban_gis_id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.String(length=100), nullable=False),
        sa.Column("pilot_area_id", sa.String(length=160), nullable=False),
        sa.Column("urban_gis_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("pipeline_version", sa.String(length=64), nullable=False),
        sa.Column("working_crs", sa.String(length=100), nullable=False),
        sa.Column("evidence_scope", sa.String(length=64), nullable=False),
        sa.Column("visual_object_key", sa.Text(), nullable=False),
        sa.Column("hydraulic_object_key", sa.Text(), nullable=False),
        sa.Column("roof_runoff_object_key", sa.Text(), nullable=False),
        sa.Column("qa_object_key", sa.Text(), nullable=False),
        sa.Column("audit_object_key", sa.Text(), nullable=False),
        sa.Column("visual_sha256", sa.String(length=64), nullable=False),
        sa.Column("hydraulic_sha256", sa.String(length=64), nullable=False),
        sa.Column("roof_runoff_sha256", sa.String(length=64), nullable=False),
        sa.Column("qa_sha256", sa.String(length=64), nullable=False),
        sa.Column("audit_sha256", sa.String(length=64), nullable=False),
        sa.Column("visual_feature_count", sa.Integer(), nullable=False),
        sa.Column("hydraulic_feature_count", sa.Integer(), nullable=False),
        sa.Column("roof_feature_count", sa.Integer(), nullable=False),
        sa.Column("domain_ownership_complete", sa.Boolean(), nullable=False),
        sa.Column("roof_rules_complete", sa.Boolean(), nullable=False),
        sa.Column("readiness_status", sa.String(length=64), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("urban_gis_id"),
        sa.UniqueConstraint("urban_gis_fingerprint", name="uq_urban_gis_fingerprint"),
        sa.UniqueConstraint("visual_object_key"),
        sa.UniqueConstraint("hydraulic_object_key"),
        sa.UniqueConstraint("roof_runoff_object_key"),
        sa.UniqueConstraint("qa_object_key"),
        sa.UniqueConstraint("audit_object_key"),
    )
    op.create_index("ix_urban_gis_products_city_id", "urban_gis_products", ["city_id"])
    op.create_index(
        "ix_urban_gis_products_pilot_area_id",
        "urban_gis_products",
        ["pilot_area_id"],
    )
    op.create_index(
        "ix_urban_gis_products_pipeline_version",
        "urban_gis_products",
        ["pipeline_version"],
    )
    op.create_index(
        "ix_urban_gis_products_evidence_scope",
        "urban_gis_products",
        ["evidence_scope"],
    )
    op.create_index(
        "ix_urban_gis_products_readiness_status",
        "urban_gis_products",
        ["readiness_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_urban_gis_products_readiness_status", table_name="urban_gis_products")
    op.drop_index("ix_urban_gis_products_evidence_scope", table_name="urban_gis_products")
    op.drop_index("ix_urban_gis_products_pipeline_version", table_name="urban_gis_products")
    op.drop_index("ix_urban_gis_products_pilot_area_id", table_name="urban_gis_products")
    op.drop_index("ix_urban_gis_products_city_id", table_name="urban_gis_products")
    op.drop_table("urban_gis_products")
