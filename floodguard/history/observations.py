"""Provider-neutral explicit interval normalization for future station/file adapters."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from floodguard.history.contracts import ObservationRecord


def rate_mm_h(value: float, units: str, start: datetime, end: datetime) -> float:
    """Convert an explicit interval accumulation/rate without assuming a daily storm profile."""
    seconds = (end - start).total_seconds()
    if seconds <= 0 or start.tzinfo is None or end.tzinfo is None:
        raise ValueError("positive timezone-aware interval required")
    factor = {"mm": 3600 / seconds, "mm/h": 1.0, "mm/day": 1 / 24}.get(units)
    if factor is None or not 0 <= value < float("inf"):
        raise ValueError("unsupported units or invalid rain value")
    return value * factor


def counter_increment(previous: float, current: float, previous_epoch: str, epoch: str) -> float:
    if epoch != previous_epoch or current < previous:
        raise ValueError("counter reset requires a new baseline; increment is unknown")
    if not 0 <= previous <= current < float("inf"):
        raise ValueError("invalid cumulative counter")
    return current - previous


def deduplicate(records: Iterable[ObservationRecord]) -> list[ObservationRecord]:
    """Identical duplicate records coalesce; revisions coexist; conflicting duplicates fail."""
    by_key: dict[tuple[str, str, str, datetime, datetime], ObservationRecord] = {}
    for record in records:
        record = ObservationRecord.model_validate_json(record.model_dump_json())
        key = (
            str(record.source.dataset_version_id),
            record.station_or_geometry_id,
            record.quantity,
            record.interval_start,
            record.interval_end,
        )
        if key in by_key and by_key[key] != record:
            raise ValueError("conflicting duplicate; publish a corrected dataset version")
        by_key[key] = record
    return sorted(by_key.values(), key=lambda r: (r.interval_start, r.observation_id))
