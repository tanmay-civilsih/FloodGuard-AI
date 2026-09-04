# Sequence 1 — Platform Foundation

**Release:** v0.1  
**Status:** implementation baseline

## Purpose

Sequence 1 establishes stable technical contracts before any flood-domain computation is introduced.

## Implemented contracts

### Units

Internal scientific quantities use the units frozen in the authoritative plan. No automatic implicit conversion is performed in Sequence 1.

### Time

Naive datetimes are rejected by the canonical UTC validator. Timezone-aware values are normalized to UTC.

### Jobs

Allowed states are:

```text
QUEUED
RUNNING
SUCCEEDED
FAILED
CANCELLED
```

Lifecycle transitions are validated. Failed jobs require an error code; successful jobs require progress `1.0`.

### Events

Every event contains:

```text
event_id
event_type
schema_version
occurred_at
correlation_id
causation_id
producer
entity_id
entity_version
payload
```

`InMemoryIdempotencyStore` is deliberately a Sequence-1 reference implementation. It demonstrates duplicate side-effect suppression and retry after failed handling. Durable Redis/NATS-backed idempotency is a later adapter, not silently implied by the in-memory implementation.

### Correlation IDs

The HTTP API creates a UUID correlation ID when absent, preserves a valid caller-supplied UUID, rejects malformed values, and echoes the ID in the response header.

## Deployment baseline

Docker Compose starts PostgreSQL/PostGIS, Redis, NATS/JetStream, MinIO, Traefik, and the FastAPI application. Each deployable has an explicit health check.

This does not yet mean every infrastructure component is used by domain code. Sequence 1 establishes and verifies the platform boundary; later sequences add adapters only when required.

## Local verification

```bash
python scripts/verify.py
```

checks:

- Python 3.12.x;
- required repository files;
- Ruff;
- mypy;
- pytest.

After:

```bash
docker compose up -d --build
```

run:

```bash
python scripts/verify.py --services
```

to additionally verify Compose configuration, health status for all Sequence-1 services, and the API health endpoint.

## Explicit exclusions

No GIS processing, drainage reconstruction, rainfall forcing, terrain model, SWMM model, surface solver, coupling, forecast, risk engine, routing engine, AI/ML model, or final dashboard is part of Sequence 1.
