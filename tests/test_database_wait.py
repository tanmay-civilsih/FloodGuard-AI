import pytest

from floodguard.common.database_wait import wait_for_database


def test_wait_for_database_accepts_ready_sqlite() -> None:
    wait_for_database("sqlite+pysqlite:///:memory:", attempts=1, delay_seconds=0)


def test_wait_for_database_rejects_invalid_attempt_count() -> None:
    with pytest.raises(ValueError, match="attempts must be at least 1"):
        wait_for_database("sqlite+pysqlite:///:memory:", attempts=0, delay_seconds=0)


def test_wait_for_database_rejects_negative_delay() -> None:
    with pytest.raises(ValueError, match="delay_seconds must be non-negative"):
        wait_for_database("sqlite+pysqlite:///:memory:", attempts=1, delay_seconds=-1)
