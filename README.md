# FloodGuard-AI

FloodGuard-AI is a scientifically defensible urban flood digital-twin and 0–3 hour nowcasting platform for a Kolkata pilot catchment.

Development is governed by:

- `docs/Urban_Flood_Digital_Twin_Authoritative_20_Sequence_Plan_FROZEN.md`
- `agent.md`

## Current milestone

**Sequence 2 — Data Source Registry, Access Governance and Fallback Sources (v0.2)**

Sequence 2 adds an authoritative, version-controlled registry of external datasets and feeds while preserving the Sequence 1 foundation. It still contains no GIS processing, rainfall nowcasting, hydraulic solver, 1D–2D coupling, ML model, or production dashboard.

## Requirements

- Python **3.12.x**
- Docker Engine + Docker Compose v2

## Local setup

```bash
python -m venv .venv
```

Activate the environment and install the pinned dependency set:

```bash
# Linux/macOS
source .venv/bin/activate
python -m pip install -r requirements.lock
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
```

Copy `.env.example` to `.env` if needed. Never commit `.env`, tokens, passwords, or API keys.

## Verify

```bash
python scripts/verify.py
```

Start the complete platform:

```bash
docker compose up -d --build
python scripts/verify.py --services
```

On container startup, Alembic migrates the registry schema and the audited Kolkata source catalogue is seeded idempotently.

## API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | process liveness |
| `GET /ready` | application readiness |
| `GET /version` | software version and active sequence |
| `GET /registry/sources` | list/filter registered data sources |
| `GET /registry/sources/{source_id}` | inspect one source |
| `POST /registry/sources` | add a governed source |
| `PUT /registry/sources/{source_id}` | replace source metadata |
| `GET /registry/readiness` | check catalogue coverage for Kolkata |

The registry stores `credential_ref` values such as `env://EARTHDATA_TOKEN`; it never stores raw credentials.

## Sequence 2 source-governance rules

- Automated acquisition is allowed only when the source's access class permits it.
- Public-view-only or unknown feeds are not scraped automatically.
- OpenStreetMap data are ODbL and must be attributed; public Overpass is for bounded/fair-use queries, with Geofabrik extracts preferred for repeat or larger ingestion.
- Source data, legal/access status, authority level, refresh policy, and fallback strategy remain explicit.
- `AVAILABLE` means the source/product is known and usable subject to its recorded access requirements; it does not mean FloodGuard currently possesses credentials.
- Planned IMD radar/nowcast, LiDAR, SCADA, drain-sensor and CCTV integrations remain explicitly non-operational until approved access exists.

## Scientific scope boundary

Sequence 2 documents data governance. It does **not** make any hydraulic-validity or operational-live-data claim. Spatial normalization begins in later sequences; hydraulics remains subject to the frozen validation gates.
