"""Timezone-safe timestamp helpers and Pydantic validation."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator


def ensure_utc(value: datetime) -> datetime:
    """Require a timezone-aware datetime and normalize it to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


UtcDateTime = Annotated[datetime, AfterValidator(ensure_utc)]


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def to_iso8601_utc(value: datetime) -> str:
    """Return a normalized ISO 8601 UTC representation."""
    return ensure_utc(value).isoformat().replace("+00:00", "Z")
