import pytest

from floodguard.contracts.events import (
    EventEnvelope,
    EventProcessingResult,
    InMemoryIdempotencyStore,
    process_idempotently,
)


def _event() -> EventEnvelope:
    return EventEnvelope(
        event_type="platform.test",
        schema_version="1.0",
        producer="tests",
        entity_id="entity-1",
        entity_version="v1",
        payload={"value": 1},
    )


def test_duplicate_event_does_not_repeat_side_effect() -> None:
    event = _event()
    store = InMemoryIdempotencyStore()
    calls: list[str] = []

    def handler(_: EventEnvelope) -> None:
        calls.append("called")

    assert process_idempotently(event, store, handler) is EventProcessingResult.PROCESSED
    assert process_idempotently(event, store, handler) is EventProcessingResult.DUPLICATE
    assert calls == ["called"]


def test_failed_handler_can_be_retried() -> None:
    event = _event()
    store = InMemoryIdempotencyStore()

    def failing(_: EventEnvelope) -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        process_idempotently(event, store, failing)

    calls: list[str] = []
    result = process_idempotently(event, store, lambda _: calls.append("retry"))
    assert result is EventProcessingResult.PROCESSED
    assert calls == ["retry"]
