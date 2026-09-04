"""Canonical event envelope and a Sequence-1 idempotency reference implementation."""

from collections.abc import Callable, Mapping
from enum import StrEnum
from threading import Lock
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from floodguard.contracts.time import UtcDateTime, utc_now


class EventProcessingResult(StrEnum):
    PROCESSED = "PROCESSED"
    DUPLICATE = "DUPLICATE"


class EventEnvelope(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    occurred_at: UtcDateTime = Field(default_factory=utc_now)
    correlation_id: UUID = Field(default_factory=uuid4)
    causation_id: UUID | None = None
    producer: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    entity_version: str = Field(min_length=1)
    payload: Mapping[str, Any] = Field(default_factory=dict)


class InMemoryIdempotencyStore:
    """Thread-safe reference store; a durable adapter is required for production workers."""

    def __init__(self) -> None:
        self._completed: set[UUID] = set()
        self._in_progress: set[UUID] = set()
        self._lock = Lock()

    def begin(self, event_id: UUID) -> bool:
        with self._lock:
            if event_id in self._completed or event_id in self._in_progress:
                return False
            self._in_progress.add(event_id)
            return True

    def complete(self, event_id: UUID) -> None:
        with self._lock:
            self._in_progress.discard(event_id)
            self._completed.add(event_id)

    def abandon(self, event_id: UUID) -> None:
        with self._lock:
            self._in_progress.discard(event_id)


def process_idempotently(
    event: EventEnvelope,
    store: InMemoryIdempotencyStore,
    handler: Callable[[EventEnvelope], None],
) -> EventProcessingResult:
    """Execute a handler at most once after successful completion in this reference process."""
    if not store.begin(event.event_id):
        return EventProcessingResult.DUPLICATE
    try:
        handler(event)
    except Exception:
        store.abandon(event.event_id)
        raise
    store.complete(event.event_id)
    return EventProcessingResult.PROCESSED
