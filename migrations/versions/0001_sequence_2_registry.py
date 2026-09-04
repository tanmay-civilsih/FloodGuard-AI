"""Create the Sequence-2 data source registry.

Revision ID: 0001_sequence_2_registry
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_sequence_2_registry"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "registry_sources",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=200), nullable=False),
        sa.Column("dataset_name", sa.String(length=300), nullable=False),
        sa.Column("city_id", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("access_method", sa.String(length=64), nullable=False),
        sa.Column("format", sa.String(length=100), nullable=False),
        sa.Column("licence", sa.Text(), nullable=False),
        sa.Column("redistribution_policy", sa.Text(), nullable=False),
        sa.Column("automation_allowed", sa.Boolean(), nullable=False),
        sa.Column("access_class", sa.String(length=64), nullable=False),
        sa.Column("authentication_type", sa.String(length=64), nullable=False),
        sa.Column("credential_ref", sa.Text(), nullable=True),
        sa.Column("authority_level", sa.String(length=64), nullable=False),
        sa.Column("horizontal_crs", sa.String(length=100), nullable=True),
        sa.Column("vertical_datum", sa.String(length=200), nullable=True),
        sa.Column("spatial_resolution", sa.String(length=200), nullable=True),
        sa.Column("temporal_resolution", sa.String(length=200), nullable=True),
        sa.Column("refresh_policy", sa.Text(), nullable=False),
        sa.Column("fallback_source_id", sa.Uuid(), nullable=True),
        sa.Column("fallback_strategy", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("terms_url", sa.Text(), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["fallback_source_id"],
            ["registry_sources.source_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_index("ix_registry_sources_city_id", "registry_sources", ["city_id"])
    op.create_index("ix_registry_sources_category", "registry_sources", ["category"])
    op.create_index("ix_registry_sources_status", "registry_sources", ["status"])


def downgrade() -> None:
    op.drop_index("ix_registry_sources_status", table_name="registry_sources")
    op.drop_index("ix_registry_sources_category", table_name="registry_sources")
    op.drop_index("ix_registry_sources_city_id", table_name="registry_sources")
    op.drop_table("registry_sources")
