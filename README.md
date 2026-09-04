# FloodGuard-AI

FloodGuard-AI is a scientifically defensible urban flood digital-twin and 0–3 hour nowcasting platform for a Kolkata pilot catchment.

Development is governed by:

- `docs/Urban_Flood_Digital_Twin_Authoritative_20_Sequence_Plan_FROZEN.md`
- `agent.md`

## Current milestone

**Sequence 4 — Spatial Normalization, Variable-Specific Resampling and Reference Harmonization (v0.4)**

Sequence 4 preserves the immutable Sequence 3 raw vault and creates traceable normalized spatial products in a separate object-store bucket. It adds configurable metric CRS harmonization, explicit vertical-reference contracts, variable-specific categorical/elevation/rainfall resampling policies, rainfall volume-conservation diagnostics, and a minimal MapLibre engineering QA viewer.

Drainage PDF reconstruction, hydraulic terrain conditioning, hydraulic surface classification, and hydraulic simulation remain later-sequence work.

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

If a clean environment has no real Kolkata raw versions yet, first run the frozen Sequence 3 acquisition gate:

```bash
python scripts/verify.py --bootstrap
```

The explicit Sequence 4 completion gate is:

```bash
python scripts/verify.py --spatial-bootstrap
```

`--spatial-bootstrap` does not redownload public source data. It consumes the latest COMPLETE immutable raw versions already present in the Sequence 3 vault, normalizes supported vector layers, checks metric alignment and rainfall conservation, validates vertical metadata policy, and verifies the QA viewer.

On container startup, Alembic migrates registry, harvester, and spatial schemas and the audited Kolkata source catalogue is seeded idempotently.

## Sequence 3 immutable raw vault

Raw data remain unchanged under:

```text
raw/{city_id}/{source_id}/{dataset_version_id}/objects/...
raw/{city_id}/{source_id}/{dataset_version_id}/manifest.json
```

Sequence 4 never edits these raw objects.

## Sequence 4 normalized spatial vault

Normalized products use a separate immutable bucket and deterministic lineage:

```text
normalized/{city_id}/{source_id}/{dataset_version_id}/{normalization_id}/working.json
normalized/{city_id}/{source_id}/{dataset_version_id}/{normalization_id}/qa.geojson
```

The working representation uses the configured metric CRS. The QA derivative is WGS 84 GeoJSON for MapLibre display. Every record preserves the source dataset version, source raw-object key, source SHA-256 lineage, CRS metadata, geometry statistics, numerical round-trip error, resampling policy, vertical-reference metadata, and resolution/information-quality fields.

Rerunning the same normalization reuses the existing deterministic result. Spatial object keys are never silently overwritten.

## Horizontal reference

The default Kolkata working CRS is:

```text
EPSG:32645  # WGS 84 / UTM zone 45N
```

It is configurable through `FLOODGUARD_WORKING_CRS`. Startup validation requires a projected CRS whose axes use metres.

## Vertical-reference rule

Every elevation-bearing dataset must explicitly carry:

```text
vertical_datum
vertical_unit
vertical_offset_m
datum_transform_status
vertical_reference_confidence
```

Elevation data are rejected by the vertical-reference gate if their datum is unresolved. FloodGuard does not silently compare terrain, drainage inverts, river/canal stage, or tide levels that use incompatible vertical references.

The current Sequence 4 Kolkata bootstrap normalizes the real non-elevation vector layers harvested in Sequence 3. Elevation products that require credentials remain outside this real bootstrap until approved access is available.

## Variable-specific resampling

Sequence 4 does not use one generic interpolation policy:

- **categorical:** nearest-neighbour by source cell centre;
- **elevation:** rectilinear bilinear interpolation with source uncertainty retained;
- **rainfall:** area-overlap conservative remapping.

Rainfall conservation uses the frozen volume definition:

```text
V = sum_t sum_i [R_i,t / (1000 * 3600)] * A_i * dt
```

and checks:

```text
relative_error = abs(V_before - V_after) / max(abs(V_before), numerical_epsilon)
```

The accepted tolerance is configured by `FLOODGUARD_RAINFALL_CONSERVATION_TOLERANCE`.

Resolution metadata keep native, computational, and effective information resolution separate. Resampling a coarse dataset onto a finer numerical grid never upgrades its claimed information resolution.

## Kolkata spatial bootstrap

Run directly inside the API container if desired:

```bash
docker compose exec -T api python -m floodguard.spatial.bootstrap --city-id kolkata
```

The core real-data categories are:

```text
WARD_BOUNDARY
CATCHMENT
WATER_BODY
```

Municipal drainage PDF objects are deliberately skipped here and preserved in the raw vault. Their reconstruction begins in Sequence 5 rather than being guessed or rasterized in Sequence 4.

## Engineering QA viewer

After the Sequence 4 spatial bootstrap, open:

```text
http://localhost:8000/spatial/qa
```

The MapLibre QA page displays normalized FloodGuard layers and their CRS/quality metadata. Its background basemap is visual context only, not a hydraulic input. Current real overlays include normalized ward, catchment, and water-body layers; future normalized roads/buildings, source-map derivatives, reconstructed drainage, and confidence markers use the same viewer contract.

## API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | process liveness |
| `GET /ready` | application readiness |
| `GET /version` | software version and active sequence |
| `GET /registry/sources` | list/filter governed data sources |
| `GET /registry/readiness` | source-catalogue readiness |
| `GET /harvester/readiness` | immutable raw-vault readiness |
| `GET /harvester/sources/{source_id}/versions` | list immutable raw versions |
| `GET /harvester/versions/{dataset_version_id}` | inspect one raw version |
| `GET /spatial/readiness` | reference/resampling/normalization readiness |
| `GET /spatial/layers` | list normalized spatial layers |
| `GET /spatial/layers/{normalization_id}` | inspect one normalized layer |
| `GET /spatial/layers/{normalization_id}/geojson` | QA-display GeoJSON |
| `GET /spatial/qa` | MapLibre engineering QA page |

There is intentionally no HTTP endpoint that performs heavy normalization. The CLI/worker path owns computation; FastAPI exposes read-only spatial metadata and QA artifacts.

## Scientific scope boundary

Passing Sequence 4 means the current core Kolkata layers are reference-harmonized and the resampling/QA rules are implemented. It does **not** mean the terrain is hydraulically validated, municipal drains have been reconstructed, or street-scale flood forecasts are ready. Those claims depend on later frozen sequences and their validation gates.
