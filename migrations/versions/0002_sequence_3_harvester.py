"""Create Sequence-3 harvester dataset versions and raw object manifests.

Revision ID: 0002_sequence_3_harvester
Revises: 0001_sequence_2_registry
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_sequence_3_harvester"
down_revision: str | None = "0001_sequence_2_registry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "harvest_dataset_versions",
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.String(length=100), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("manifest_object_key", sa.Text(), nullable=True),
        sa.Column("object_count", sa.Integer(), nullable=False),
        sa.Column("total_bytes", sa.Integer(), nullable=False),
        sa.Column("previous_version_id", sa.Uuid(), nullable=True),
        sa.Column("source_snapshot", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("dataset_version_id"),
        sa.UniqueConstraint(
            "source_id",
            "manifest_sha256",
            name="uq_harvest_source_manifest_sha256",
        ),
    )
    op.create_index(
        "ix_harvest_dataset_versions_dataset_id",
        "harvest_dataset_versions",
        ["dataset_id"],
    )
    op.create_index(
        "ix_harvest_dataset_versions_source_id",
        "harvest_dataset_versions",
        ["source_id"],
    )
    op.create_index(
        "ix_harvest_dataset_versions_city_id",
        "harvest_dataset_versions",
        ["city_id"],
    )
    op.create_index(
        "ix_harvest_dataset_versions_status",
        "harvest_dataset_versions",
        ["status"],
    )

    op.create_table(
        "harvest_raw_objects",
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.String(length=300), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=200), nullable=True),
        sa.Column("etag", sa.Text(), nullable=True),
        sa.Column("last_modified", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["harvest_dataset_versions.dataset_version_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("object_id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index(
        "ix_harvest_raw_objects_dataset_version_id",
        "harvest_raw_objects",
        ["dataset_version_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_harvest_raw_objects_dataset_version_id", table_name="harvest_raw_objects")
    op.drop_table("harvest_raw_objects")
    op.drop_index("ix_harvest_dataset_versions_status", table_name="harvest_dataset_versions")
    op.drop_index("ix_harvest_dataset_versions_city_id", table_name="harvest_dataset_versions")
    op.drop_index("ix_harvest_dataset_versions_source_id", table_name="harvest_dataset_versions")
    op.drop_index("ix_harvest_dataset_versions_dataset_id", table_name="harvest_dataset_versions")
    op.drop_table("harvest_dataset_versions")
