from datetime import UTC, datetime, timedelta, timezone

import pytest

from floodguard.contracts.time import ensure_utc, to_iso8601_utc


def test_ensure_utc_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ensure_utc(datetime(2026, 9, 4, 12, 0))


def test_ensure_utc_normalizes_offset_datetime() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    value = datetime(2026, 9, 4, 17, 30, tzinfo=ist)
    assert ensure_utc(value) == datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def test_iso8601_utc_uses_z_suffix() -> None:
    value = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
    assert to_iso8601_utc(value) == "2026-09-04T12:00:00Z"
