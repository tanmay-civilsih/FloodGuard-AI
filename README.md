# FloodGuard-AI

FloodGuard-AI is a scientifically defensible urban flood digital-twin and 0–3 hour nowcasting platform for a Kolkata pilot catchment.

Development is governed by:

- `docs/Urban_Flood_Digital_Twin_Authoritative_20_Sequence_Plan_FROZEN.md`
- `agent.md`

## Current milestone

**Sequence 5 — Legacy Municipal Drainage Reconstruction (v0.5 release candidate)**

Sequence 5 reconstructs a hash-pinned, authentic KMC/OpenCity Ward 7 drainage PDF into traceable
drain, manhole-candidate, and drainage-label vector features. It inspects native PDF vector/text
content before OCR, uses a versioned four-point affine calibration, assigns confidence, preserves
missing engineering attributes as `NULL`, and exposes an append-only human QA review gate.

The code and automated real-object diagnostics are implemented. The release remains a candidate
until a human inspects `/reconstruction/qa` and records approval. Hydraulically conditioned terrain,
surface classification, and simulation remain later-sequence work.

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

Build the calibrated real Ward 7 reconstruction:

```bash
docker compose exec -T api python -m floodguard.reconstruction.bootstrap --city-id kolkata
```

Then inspect `http://localhost:8000/reconstruction/qa` and record a human review. The formal
Sequence 5 completion gate is:

```bash
python scripts/verify.py --reconstruction-bootstrap
```

The gate intentionally fails while the real reconstruction is `PENDING_REVIEW`.

On container startup, Alembic migrates registry, harvester, spatial, reconstruction, and review
schemas and the audited Kolkata source catalogue is seeded idempotently.

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

## Sequence 5 reconstruction artifacts

The initial real calibration is pinned to the Ward 7 PDF SHA-256 and the 2022 KMC ward-reference
KML SHA-256. Reconstruction artifacts are immutable and deterministic:

```text
reconstruction/{city_id}/{source_id}/{dataset_version_id}/{reconstruction_id}/working.geojson
reconstruction/{city_id}/{source_id}/{dataset_version_id}/{reconstruction_id}/qa.geojson
reconstruction/{city_id}/{source_id}/{dataset_version_id}/{reconstruction_id}/audit.json
```

The working and WGS 84 QA layers preserve feature confidence, extraction method, source object,
dataset version, page, and deterministic IDs. Diameter, invert, flow direction, and material remain
`NULL`; source labels are annotations, not automatically accepted hydraulic parameters.

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

Municipal drainage PDF objects are deliberately skipped by Sequence 4 and preserved in the raw
vault. The Sequence 5 worker reads the calibrated Ward 7 object without modifying it.

## Engineering QA viewer

After the Sequence 4 spatial bootstrap, open:

```text
http://localhost:8000/spatial/qa
```

The spatial MapLibre page displays normalized layers and their CRS/quality metadata. The Sequence 5
review page is:

```text
http://localhost:8000/reconstruction/qa
```

It renders reconstructed drainage, manhole candidates, labels, confidence, counts, source hash,
and georeference error. Both basemaps are visual context only, not hydraulic inputs.

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
| `GET /reconstruction/readiness` | Sequence 5 reconstruction and human-review gate |
| `GET /reconstruction/maps` | list drainage reconstructions and provenance |
| `GET /reconstruction/maps/{reconstruction_id}/geojson` | WGS 84 reconstruction QA layer |
| `GET /reconstruction/maps/{reconstruction_id}/reviews` | append-only review history |
| `POST /reconstruction/maps/{reconstruction_id}/reviews` | record human approval/rejection |
| `GET /reconstruction/qa` | MapLibre drainage reconstruction QA page |

There is intentionally no HTTP endpoint that performs heavy normalization or PDF extraction. The
CLI/worker path owns computation; FastAPI exposes metadata, QA artifacts, and the explicit review
record endpoint.

## Scientific scope boundary

Passing Sequence 5 means one real municipal map is reconstructed, geographically checked within
its declared legacy-map tolerance, provenance-preserving, and human-reviewed. It does **not** mean
the drain network or terrain is hydraulically validated, nor that street-scale forecasts are ready.
Those claims depend on later frozen sequences and their validation gates.
