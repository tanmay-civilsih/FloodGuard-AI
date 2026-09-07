"""The new catalogue migration must preserve existing forcing rows and bytes."""

import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_additive_upgrade_and_isolated_downgrade_preserve_old_rows():
    migration = importlib.import_module("migrations.versions.0010_sequence_11_history")
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE legacy_forcing (id TEXT, manifest TEXT)"))
        connection.execute(text("INSERT INTO legacy_forcing VALUES ('known-id', 'retained-bytes')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert set(inspect(connection).get_table_names()) == {
                "legacy_forcing",
                "historical_events",
            }
            assert connection.execute(text("SELECT * FROM legacy_forcing")).one() == (
                "known-id",
                "retained-bytes",
            )
            migration.downgrade()
            assert inspect(connection).get_table_names() == ["legacy_forcing"]
            assert connection.execute(text("SELECT manifest FROM legacy_forcing")).scalar_one() == (
                "retained-bytes"
            )
