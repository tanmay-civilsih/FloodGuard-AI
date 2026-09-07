"""Add historical event catalogue without modifying existing product identities."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_sequence_11_history"
down_revision: str | None = "0009_sequence_10_forcing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "historical_events",
        sa.Column("historical_event_id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.String(100), nullable=False),
        sa.Column("event_key", sa.String(2000), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("historical_event_id"),
    )
    op.create_index("ix_historical_events_city_id", "historical_events", ["city_id"])


def downgrade() -> None:
    op.drop_index("ix_historical_events_city_id", table_name="historical_events")
    op.drop_table("historical_events")
