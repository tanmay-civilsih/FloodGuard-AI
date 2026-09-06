# FloodGuard-AI

FloodGuard-AI is a scientifically defensible urban flood digital-twin and 0–3 hour nowcasting platform for a Kolkata pilot catchment.

Development is governed by:

- `docs/Urban_Flood_Digital_Twin_Authoritative_20_Sequence_Plan_FROZEN.md`
- `docs/validation/final-human-review-policy.md`
- `agent.md`

## Current milestone

**Sequence 10 - Dynamic Forcing Service (v1.0)**

Sequence 10 implements immutable forcing packages bound to an exact twin: interval rainfall stored
as Xarray/Zarr, dynamic stage boundaries, pump controls and explicit antecedent availability.
Replay, synthetic and externally prepared forecast inputs use conservative remapping, declared
interpolation and exact horizon coverage. A short forecast cannot be silently extended. See
`SEQUENCE_10_STATUS.md` and `docs/architecture/sequence-10-forcing.md` for validation and limitations.

The owner explicitly authorized Sequence 10 implementation after the Sequence 9 blocker report.
**Sequence 9 remains NOT_FROZEN:** DATA-08-01 still requires genuine source-bound real drainage
across adjacent wards to a documented destination. Reference forcing does not close that gate.
Sequence 9's prior implementation/assembly validation is retained in `SEQUENCE_9_STATUS.md`.

Sequence 8 is technically frozen on validated source `de6cce9`; see `SEQUENCE_8_STATUS.md`.
Final human engineering acceptance remains pending Sequence 20.

Sequence 7 keeps the visual city representation separate from the simplified hydraulic surface representation. The hydraulic contract supports exactly:

```text
ROAD
ROOF
BUILDING_BARRIER
OPEN_SOIL
PARK
WATER
RAILWAY
OTHER_IMPERVIOUS
```

Every hydraulic feature has an explicit domain owner. Sequence 7 surface features are owned by `SURFACE_2D`; water may also be a `BOUNDARY`. `NETWORK_1D` ownership is reserved for the drainage model introduced in Sequence 8.

Runoff-producing classes use one and only one hydrologic-loss formulation:

```text
SIMPLIFIED_RUNOFF:  Re = Cr R
EXPLICIT_LOSS:      Re = max(0, R - I - L)
```

Every roof has one documented runoff rule pointing to either a versioned receiving geometry or an explicit drain target. Sequence 7 deliberately does **not** assign `surface_cell_ids`; cell binding belongs to a later numerical-grid sequence.

The project-owner policy defers human-only GIS/engineering acceptance to Sequence 20. The deterministic Sequence 7 bootstrap therefore uses a clearly labelled `REFERENCE_FIXTURE` to validate all eight surface classes, both loss modes, roof-volume accounting, immutable artifacts and API/readiness contracts without pretending that synthetic geometry is real Ward 7 evidence.

See `docs/architecture/sequence-07-urban-gis.md`.

## Requirements

- Python **3.12.x**
- Docker Engine + Docker Compose v2
- Node.js where browser-behavior tests require it

## Local setup

```bash
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
python -m pip install -r requirements.lock
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
```

Copy `.env.example` to `.env` if needed. Never commit `.env`, tokens, passwords, API keys or local evidence drafts.

## Verification

Static checks and unit/integration tests:

```bash
python scripts/verify.py
```

Start/rebuild the platform and verify the running services/API:

```bash
docker compose up -d --build
python scripts/verify.py --services
```

Run the Sequence 9 twin assembly and independent recreation bootstrap:

```bash
python scripts/verify.py --services --twin-bootstrap
```

Run the complete Sequence 9 technical-development gate, including the real conditional-storage concurrency probe:

```bash
python scripts/sequence9_development_gate.py --run-checks
```

The Sequence 9 gate records assembly validation separately from technical freeze. A missing genuine
real cross-ward path blocks freeze even when reference assembly and all software checks pass.
The approved human-review policy remains in force, without waiving the real two-ward requirement.

## Sequence 9 twin versions

Inspect `/twins/qa`, `/twins/readiness?city_id=kolkata` and `/twins/products?city_id=kolkata`.
A twin manifest names all twelve static component versions with hashes, software identity, readiness,
vertical-reference status and explicit missing reasons. The API is read-only. Operator build/recreate
commands and exact pilot selections are documented in the Sequence 9 architecture and `docs/examples/`.

## Sequence 8 products

Drain products retain immutable source/input/ward/QA/audit artifacts. Directed models additionally
retain graph, hydraulic parameters/static definitions, physical exchange geometry and readiness
assessment. Source-bound models retain a binding-coverage report. Artifact byte counts and SHA-256
are checked before reuse and HTTP delivery. Inspect them using:

- `/drainage/readiness?city_id=kolkata`
- `/drainage/products?city_id=kolkata`
- `/drainage/products/{product_id}/{kind}`
- `/drainage/qa`

The real Ward 7 draft is VISUAL_ONLY. The scenario-ready cross-ward reference is synthetic and
separately labelled. The API offers read-only inspection; explicit operator CLI commands perform
source import and apply complete binding plans. See the Sequence 8 architecture for commands.

## Sequence 7 immutable products

A valid urban-GIS package produces separate immutable artifacts:

```text
urban-gis/{city_id}/{pilot_area_id}/{urban_gis_id}/visual_city.geojson
urban-gis/{city_id}/{pilot_area_id}/{urban_gis_id}/hydraulic_surface.geojson
urban-gis/{city_id}/{pilot_area_id}/{urban_gis_id}/roof_runoff.json
urban-gis/{city_id}/{pilot_area_id}/{urban_gis_id}/qa.geojson
urban-gis/{city_id}/{pilot_area_id}/{urban_gis_id}/audit.json
```

The database stores the SHA-256 of every artifact. Reads recompute the hash and fail closed on corruption. Rebuilding an identical package is idempotent and does not silently overwrite an existing object.

The roof-runoff artifact explicitly records:

```text
surface_cell_binding = DEFERRED_TO_LATER_SEQUENCE
```

## Earlier immutable products

Raw acquisition remains immutable under:

```text
raw/{city_id}/{source_id}/{dataset_version_id}/objects/...
raw/{city_id}/{source_id}/{dataset_version_id}/manifest.json
```

Spatial normalization remains separate:

```text
normalized/{city_id}/{source_id}/{dataset_version_id}/{normalization_id}/working.json
normalized/{city_id}/{source_id}/{dataset_version_id}/{normalization_id}/qa.geojson
```

Drainage reconstruction remains immutable:

```text
reconstruction/{city_id}/{source_id}/{dataset_version_id}/{reconstruction_id}/working.geojson
reconstruction/{city_id}/{source_id}/{dataset_version_id}/{reconstruction_id}/qa.geojson
reconstruction/{city_id}/{source_id}/{dataset_version_id}/{reconstruction_id}/audit.json
```

Terrain remains split into raw/visual/hydraulic products:

```text
terrain/{city_id}/{source_id}/{dataset_version_id}/{terrain_id}/visual_terrain.json
terrain/{city_id}/{source_id}/{dataset_version_id}/{terrain_id}/hydraulic_terrain.json
terrain/{city_id}/{source_id}/{dataset_version_id}/{terrain_id}/multi_level_structures.json
terrain/{city_id}/{source_id}/{dataset_version_id}/{terrain_id}/qa.geojson
terrain/{city_id}/{source_id}/{dataset_version_id}/{terrain_id}/audit.json
```

## Coordinate and vertical-reference rules

The default Kolkata working CRS is:

```text
EPSG:32645  # WGS 84 / UTM zone 45N
```

It is configurable through `FLOODGUARD_WORKING_CRS`; metric-working-CRS validation is mandatory.

Known source vertical datum/unit metadata do not prove compatibility with future drain invert, river/canal/tide stage or survey elevations. Cross-datum comparisons remain prohibited until references are compatible or explicitly transformed with provenance.

## QA endpoints

```text
http://localhost:8000/spatial/qa
http://localhost:8000/reconstruction/qa
http://localhost:8000/terrain/qa
http://localhost:8000/urban-gis/qa
```

The Sequence 7 QA page exposes the latest urban-GIS package, readiness status and links to the separate visual, hydraulic, roof-runoff, QA and audit artifacts. A `REFERENCE_FIXTURE` is clearly distinguished from real-pilot evidence.

## Main API additions in Sequence 7

| Endpoint | Purpose |
|---|---|
| `GET /urban-gis/readiness` | Sequence 7 automated/final readiness distinction |
| `GET /urban-gis/products` | list immutable urban-GIS products |
| `GET /urban-gis/products/{urban_gis_id}` | inspect one product record |
| `GET /urban-gis/products/{urban_gis_id}/visual` | separate visual-city GeoJSON |
| `GET /urban-gis/products/{urban_gis_id}/hydraulic` | separate hydraulic-surface GeoJSON |
| `GET /urban-gis/products/{urban_gis_id}/roof-runoff` | versioned roof-runoff rules |
| `GET /urban-gis/products/{urban_gis_id}/qa` | combined QA GeoJSON |
| `GET /urban-gis/products/{urban_gis_id}/audit` | immutable lineage/policy audit |
| `GET /urban-gis/qa` | Sequence 7 QA inspector |

## Scientific scope boundary

Passing the automated Sequence 7 gate proves the declared data contracts, hydraulic ownership rules, mutually exclusive loss modes, roof-volume conservation helper, receiving-geometry policy, immutable storage behavior and reference-package execution path.

It does **not** prove that real Kolkata buildings/roads/parks/roofs have been correctly classified, that every real roof target is accepted, or that any hydraulic forecast is validated. Those claims depend on the deferred Sequence 20 human review and later drainage, forcing, hydraulics, validation and forecast sequences.
