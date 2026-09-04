# FloodGuard-AI

FloodGuard-AI is a scientifically defensible urban flood digital-twin and 0–3 hour nowcasting platform for a Kolkata pilot catchment.

Development is governed by:

- `docs/Urban_Flood_Digital_Twin_Authoritative_20_Sequence_Plan_FROZEN.md`
- `agent.md`

## Current milestone

**Sequence 3 — Automatic Data Harvester and Immutable Raw Data Vault (v0.3)**

Sequence 3 adds governed external acquisition, SHA-256 change detection, immutable raw-object versioning in MinIO, dataset-version metadata in PostgreSQL, and a Kolkata bootstrap worker. It does not normalize, reproject, resample, or otherwise alter scientific source content; spatial harmonization begins in Sequence 4.

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

Static checks and unit tests:

```bash
python scripts/verify.py
```

Start/rebuild the complete platform and verify services:

```bash
docker compose up -d --build
python scripts/verify.py --services
```

The explicit networked Sequence 3 completion gate is:

```bash
python scripts/verify.py --bootstrap
```

`--bootstrap` intentionally performs external downloads. Large PBF extracts are disabled by default, Overpass requires an explicit bounded query, and authorization-required sources are skipped unless explicitly enabled with approved credentials.

On container startup, Alembic migrates both registry and harvester schemas and the audited Kolkata source catalogue is seeded idempotently.

## Immutable raw vault

Raw data use the frozen object-key pattern:

```text
raw/{city_id}/{source_id}/{dataset_version_id}/objects/...
raw/{city_id}/{source_id}/{dataset_version_id}/manifest.json
```

Each downloaded object records its SHA-256 digest, byte size, source URL, content type, ETag/Last-Modified where available, and immutable object key. The dataset-version manifest snapshots the source-governance metadata that applied at acquisition time.

If the complete upstream object manifest is unchanged, a new dataset version is **not** created. If any raw bytes change, a new `dataset_version_id` and a new raw prefix are created; prior raw keys are never overwritten by the FloodGuard application. MinIO bucket versioning is enabled as an additional development safeguard.

Application-level immutability does not replace infrastructure retention policy: an object-store administrator can still delete data unless deployment-level retention/object-lock controls are configured.

## Kolkata bootstrap worker

Run the safe default bootstrap inside the API container:

```bash
docker compose exec api python -m floodguard.harvester.bootstrap --city-id kolkata
```

Optional deliberate modes:

```bash
# Allow the large regional PBF source, still subject to configured byte limits.
docker compose exec api python -m floodguard.harvester.bootstrap --city-id kolkata --include-pbf

# Use Overpass only with an explicit bounded query.
docker compose exec api python -m floodguard.harvester.bootstrap --city-id kolkata --overpass-query "<bounded Overpass QL>"
```

Authorization-required acquisition is off by default. `credential_ref` values such as `env://EARTHDATA_TOKEN` are resolved only at runtime; raw credentials are never persisted in registry or harvester tables.

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
| `GET /harvester/readiness` | raw-vault/versioning readiness summary |
| `GET /harvester/sources/{source_id}/versions` | list immutable versions for a source |
| `GET /harvester/versions/{dataset_version_id}` | inspect one version and its raw objects |

There is intentionally no HTTP endpoint that performs a long download. Acquisition runs in the worker/CLI path rather than inside a FastAPI request handler.

## Sequence 3 acquisition rules

- The harvester refuses sources whose registry policy does not permit automation.
- `OPEN_AUTOMATED` sources may be collected automatically when an adapter exists.
- `AUTHORIZATION_REQUIRED` sources require an explicit opt-in and a resolvable credential reference.
- `OPEN_MANUAL`, `PUBLIC_VIEW_ONLY`, `COMMERCIAL_OPTIONAL`, and `UNKNOWN` are not automatically harvested by the default worker.
- CKAN resources, direct HTTP/REST resources, STAC Item assets, bounded Overpass requests, WMS/WFS/WMTS requests with explicit query parameters, and opt-in PBF extracts are represented by acquisition adapters.
- Standard OSM map tiles and the OSM editing API are never used as bulk data sources.
- Per-object, per-source-total, and resource-count limits are enforced before raw data are admitted to the vault.

## Scientific scope boundary

Sequence 3 preserves source bytes and provenance. A successful harvest does **not** imply that CRS, vertical datum, spatial resolution, or hydraulic suitability has been validated. Those gates start in Sequence 4 and later sequences.
