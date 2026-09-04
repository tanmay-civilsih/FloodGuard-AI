# FloodGuard-AI

FloodGuard-AI is a scientifically defensible urban flood digital-twin and 0–3 hour nowcasting platform for a Kolkata pilot catchment.

Development is governed by:

- `docs/Urban_Flood_Digital_Twin_Authoritative_20_Sequence_Plan_FROZEN.md`
- `agent.md`

## Current milestone

**Sequence 1 — Platform Foundation, Contracts, Units, Time, Jobs and Events (v0.1)**

Sequence 1 establishes the reproducible software foundation only. It intentionally contains no GIS processing, rainfall model, drainage hydraulics, 2D hydraulic solver, 1D–2D coupling, AI/ML, or production dashboard.

## Requirements

- Python **3.12.x**
- Docker Engine + Docker Compose v2

## Local setup

```bash
python -m venv .venv
```

Activate the environment:

```bash
# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install the pinned Sequence 1 dependency set:

```bash
python -m pip install -r requirements.lock
```

Optionally copy the development environment template:

```bash
cp .env.example .env
```

Do not commit `.env` or credentials.

## Verify code and contracts

```bash
python scripts/verify.py
```

This runs Ruff, mypy, and pytest after checking the Python version and required repository files.

## Start the complete Sequence 1 platform

```bash
docker compose up -d --build
python scripts/verify.py --services
```

The compose platform includes:

- PostgreSQL + PostGIS
- Redis
- NATS + JetStream
- MinIO
- Traefik
- FloodGuard FastAPI application

Stop it with:

```bash
docker compose down
```

## API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | process liveness |
| `GET /ready` | application readiness |
| `GET /version` | software version and active development sequence |

Requests receive an `X-Correlation-ID` response header. A supplied correlation ID must be a valid UUID and is preserved end-to-end at the HTTP boundary.

## Canonical scientific units

| Quantity | Internal unit |
|---|---|
| Distance | m |
| Elevation | m |
| Water depth | m |
| Velocity | m/s |
| Discharge | m³/s |
| Area | m² |
| Volume | m³ |
| Simulation time | s |
| Rain rate | mm/h |

All internal timestamps are timezone-aware UTC values. Asia/Kolkata conversion is presentation-only.

## Sequence 1 scope boundary

Do not infer hydraulic validity from this release. Scientific hydraulics begins only in later sequences and remains subject to the frozen validation gates.
