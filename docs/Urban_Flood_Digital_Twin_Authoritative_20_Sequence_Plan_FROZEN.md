# Urban Flood Digital Twin & 0–3 Hour Nowcasting Platform
## Authoritative 20-Sequence Development Specification — Roadmap Revision R2

**Primary demonstrator:** Kolkata, West Bengal, India
**Target:** Smart India Hackathon (SIH) 2026 — Urban Flood Nowcasting
**Primary language:** Python 3.12.x
**Architecture:** API-oriented modular platform with explicit domain boundaries and one in-process coupled hydraulics worker
**Development rule:** Build, validate, freeze, then proceed to the next sequence.
**Revision:** ROADMAP-R2-2026-09-07
**Revision status:** Frozen planning baseline, revised at the owner's explicit request on 7 September 2026. This is the sole active implementation specification; planning approval does not claim implementation or validation.

---

# 0. Scientific Revision Summary

This revision preserves the original 20-sequence architecture while making the following scientific and implementation requirements explicit:

1. **EPA SWMM Dynamic Wave (`DYNWAVE`) is mandatory in coupled mode** because the prototype claims backwater, surcharge, reverse flow, pressurization, pump operation, and downstream-stage influence.
2. **1D–2D exchange is explicitly bidirectional and head-controlled.** Surface-to-drain and drain-to-surface transfer must use a documented weir/orifice-style exchange formulation rather than an undefined exchange function.
3. **SWMM native external ponding is disabled in coupled mode.** The 2D domain is the sole owner of above-ground storage.
4. **The 2D local-inertial solver remains the baseline**, but the system must track an applicability diagnostic and must not imply full shallow-water fidelity where rapidly varied or strongly supercritical flow dominates.
5. **Rainfall remapping must demonstrate numerical conservation** using an explicit area-integrated volume check.
6. **Hydraulic terrain cannot be declared validated from metadata alone.** A vertical-quality gate is required before `HYDRAULIC_VALIDATED` status.
7. **Ensemble exceedance fraction is not automatically a calibrated probability.** Probability language becomes authoritative only after validation/reliability evidence.
8. **Flood-aware routing must be genuinely time dependent.** The baseline SIH implementation should use a time-expanded or otherwise FIFO-safe formulation and evaluate exposure over edge traversal, not at one instant only.
9. **The target service architecture remains modular, but SIH deployment may consolidate logical services** to reduce operational complexity while preserving contracts and ownership boundaries.
10. **Scientific claims are limited to validated spatial and temporal scope.** Numerical grid spacing must never be presented as measurement/data resolution.

## 0.1 R2 authority, current state and wording

The owner explicitly requested redesign of the next ten sequences and modification of this
frozen plan on 7 September 2026. R2 replaces the earlier Sequence 11-20 order and the old rule
that all ML work must wait until after Sequence 19. Sequences 1-10 retain their scientific
requirements and implementation evidence; required extensions are assigned to the new sequences.
Earlier proposals in docs/planning are background only. The exact former plan is archived in
docs/planning/archive/AUTHORITATIVE_PLAN_BEFORE_R2_2026-09-07.txt, never an alternative roadmap.

At revision time the branch is sequence-10-forcing. Sequence 10 implementation/assembly was
verified on 2c39b70; Sequence 9/10 remain NOT_FROZEN because DATA-08-01 lacks the required real
source-bound cross-ward drainage path. Historical checks are evidence for their recorded source,
not a fresh runtime verification by this revision. Human-only reviews remain at Sequence 20.

This request authorizes the planning revision and aligned guidance updates. It does not itself
start sequence implementation, train models, acquire restricted data, purchase compute, deploy
software or declare earlier blockers closed. The next implementation target is revised Sequence 11.

Terms used throughout:

| Term | Exact meaning |
|---|---|
| Implemented | The specified code/artifacts exist; this alone does not mean tested or scientifically accepted |
| Engineering verified | Declared contract, numerical and integration checks passed on identified source |
| Independently evaluated | A frozen configuration was assessed on excluded events; improvement is not implied |
| Supported for declared scope | Evidence supports the stated quantity, geography, horizon and use |
| Frozen plan | The agreed specification; not a completed software release |
| Sequence freeze | Mandatory outputs/tests and applicable prerequisites passed with recorded evidence |
| Recorded replay | Playback of archived data or genuine saved runs; it is not live computation |
| Hydraulic reconstruction | Simulation driven by known event forcing; it is not an issue-time weather forecast |
| Reanalysis hindcast | A historical prediction initialized from retrospective atmospheric reconstruction |
| Issue-time backtest | A historical prediction using only inputs evidenced as available by its issue time |

## 0.2 Revised Sequence 11-20 map

| New sequence | Deliverable | Former work retained |
|---|---|---|
| 11 | Compatibility, historical events, observation data and rainfall preview | New extensions to implemented Sequences 2-10 |
| 12 | 2D local-inertial surface solver and numerical bindings | Former 11 |
| 13 | SWMM drainage engine and operational boundaries | Former 12 |
| 14 | Conservative coupling, initialization and historical reconstruction | Former 13 |
| 15 | Deterministic forecasts and development baseline evaluation | Former 14 plus development portion of 19 |
| 16 | Actual GraphCast inference, rainfall fusion and XGBoost training/evaluation | New required model integration |
| 17 | Risk/scenarios and time-dependent routing | Former 15 and 16, with separate subgates |
| 18 | Full 2D/3D historical replay and forecast-comparison dashboard | Former 17, expanded |
| 19 | Independent validation, connected-catchment scaling and performance | Former 19 audit plus former 18 |
| 20 | Resilience, reproducible demo and final acceptance | Former 20, expanded |

Release targets remain v1.1 through v2.0 for the new sequence numbers; these are planned versions,
not existing deployments. Original hydraulic equations, conservation, routing and validation
requirements remain mandatory in their new homes. Checkpoint B moves to 15 and C moves to 18.

## 0.3 Gate and dependency policy

Every new sequence has entry dependencies, existing-code changes, deliverables, verification,
a visible result and a completion/freeze gate. Inherited component acceptance paragraphs are
necessary tests inside the containing sequence, not independent shortcuts to freeze.

Track engineering_result, data_readiness, scientific_claim_status, inherited_blockers and
freeze_status separately. Mandatory missing data/access/compute is BLOCKED with a concrete
remedy; it is not a passed gate. Conditional feeds may be unavailable only where the sequence
explicitly permits that status. Do not claim their capability from mocks.

Sequence 11 may perform rainfall-only/data preparation while DATA-08-01 remains. Reference
benchmark development after explicit implementation authorization may use labelled fixtures;
real-pilot hydraulic acceptance and dependent sequence freeze cannot waive the inherited gate.
The prior authorization to implement Sequence 10 is not blanket authorization for later work.

Sequence 11's independent data/compatibility gate may freeze when its own mandatory outputs pass,
while the project still records the inherited real-twin blocker. Later numerical component checks
may pass on reference fixtures, but they cannot be used to claim a completed real-pilot dependency.
Report component acceptance and overall dependent readiness separately instead of changing the
meaning of an earlier gate.

Every compatibility change requires old-artifact read/recreation checks, additive migration
or explicit version dispatch, retained source/model/data identity, and affected-scope verification.
Never re-run a job under an old identity after changing its inputs or model. Never rewrite
historical ledgers, hashes or validation receipts to make them appear current.

## 0.4 Minimum deliverables and boundaries

Historical rainfall acquisition, a genuine rainfall preview, conservative deterministic hydraulics,
actual full-resolution pretrained GraphCast inference, actual XGBoost rainfall training/evaluation,
risk/routing, 2D/3D replay and independent validation are planned deliverables. Their completion
depends on the gates below; unavailable mandatory evidence is reported without relabelling it done.

Gauge/radar and live operation are conditional on verified numerical feeds and latency. Coarse
satellite/reanalysis data can support explicitly labelled experiments. Real flood skill requires
independent flood evidence. Full GraphCast retraining/fine-tuning, transformer development and
direct learned flood-depth replacement are not required by this revision.

---

# 1. Project Goal

Build a scientifically defensible urban flood digital twin that can:

1. discover and collect permitted free/open urban datasets;
2. preserve raw data, licences, provenance, versions, and quality information;
3. reconstruct municipal drainage infrastructure from PDF/CAD/GIS sources;
4. harmonize horizontal and vertical spatial references;
5. build a versioned visual city model and a separate hydraulic city model;
6. build and parameterize a directed drainage network;
7. ingest or generate rainfall forcing for the next 0–3 hours;
8. represent time-varying downstream water levels, pumps, and operational controls;
9. simulate 2D surface flooding;
10. simulate 1D drainage hydraulics using EPA SWMM/PySWMM;
11. exchange water conservatively between the 2D surface and 1D drainage system;
12. initialize the hydraulic state at the forecast start time;
13. generate deterministic 0–180 minute flood forecasts;
14. generate probabilistic flood outputs only from valid ensembles;
15. evaluate engineering what-if scenarios separately from probability;
16. project flood forecasts onto roads;
17. calculate time-dependent lower-risk routes;
18. display the city, drainage, rainfall, flooding, risk, and routing in 2D and 3D;
19. validate the meteorological, hydraulic, routing, and reconstruction components;
20. deliver a reproducible and resilient SIH prototype.

---

# 2. Non-Negotiable Engineering Rules

## 2.1 One owner of rainfall-runoff in coupled mode

The primary operational mode is:

```text
COUPLED_2D_1D
```

In this mode:

```text
Rainfall
   ↓
2D Surface Hydrology/Hydraulics
   ↓
Surface runoff and overland flow
   ↓
Defined surface-drain exchange points
   ↓
SWMM drainage network
```

**SWMM subcatchment runoff generation is disabled in `COUPLED_2D_1D` mode.**

This prevents the same rainfall from being converted to runoff twice.

A separate simplified mode may later be implemented:

```text
SWMM_ONLY_FAST
```

In that mode, SWMM may generate runoff from its own subcatchments. The two runoff modes must never operate simultaneously in the same simulation.

## 2.2 One owner of surface ponding

In `COUPLED_2D_1D` mode:

- the 2D surface solver owns all above-ground floodwater storage;
- SWMM owns water inside the drainage network;
- surcharge/overflow is transferred through the explicit exchange module into the 2D surface;
- SWMM native external ponding storage is disabled;
- SWMM must not independently store the same external ponded water already represented in the 2D model.

## 2.3 One hydraulic owner per physical feature

Every hydraulically active feature must declare:

```text
hydraulic_domain
```

Allowed values:

```text
SURFACE_2D
NETWORK_1D
BOUNDARY
VISUAL_ONLY
```

Examples:

```text
Road surface                 → SURFACE_2D
Underground pipe             → NETWORK_1D
Open drain modelled in SWMM  → NETWORK_1D
Hooghly downstream stage     → BOUNDARY
Decorative building roof     → VISUAL_ONLY or mapped to a hydraulic surface rule
```

A physical feature must not store water independently in more than one hydraulic domain unless a defined exchange interface connects those domains.

## 2.4 Numerical modules remain in one hydraulics worker

The following are logical components, not separately network-coupled numerical services:

```text
Hydraulics Worker
├── Surface Solver
├── SWMM Adapter
├── Surface–Drain Exchange Module
├── Time Coordinator
├── Volume Ledger
└── State Initializer/Estimator
```

They communicate in memory inside the worker process.

REST, NATS, Redis, or any external queue must not be used between these components at each numerical timestep.

## 2.5 Missing engineering data are never silently invented

Every important engineering parameter has one status:

```text
MUNICIPAL
MEASURED
GIS_DERIVED
LITERATURE
INFERRED
ASSUMED
CALIBRATED
MISSING
```

A value with status `ASSUMED`, `INFERRED`, or `CALIBRATED` must retain the method, source, bounds, and version used to obtain it.

## 2.6 Numerical resolution must not be presented as data resolution

If a 30 m elevation source is resampled onto a 2 m numerical grid, the underlying terrain information remains approximately 30 m quality unless additional data improve it.

Every raster-based product must record:

```text
native_resolution
computational_resolution
effective_information_resolution
source_quality
```

The same rule applies to terrain, rainfall, land cover, and flood observations.

## 2.7 All water transfers must be volume-conservative

Every rainfall, infiltration, boundary, roof, inlet, surcharge, pump-related, and outflow transfer must be included in a simulation-wide volume ledger.

No subsystem may remove more water than is physically available in the source domain.

## 2.8 Probability and scenario sensitivity are different outputs

**Flood probability** may be calculated only from a defined probabilistic ensemble.

Manually selected what-if cases such as 20%, 40%, and 60% drain blockage are **scenario sensitivity cases**, not probability samples.

Before probabilistic validation, the preferred reported quantity is:

```text
ensemble_exceedance_fraction
probability_status = PROVISIONAL
```

The UI may use the word `probability` only when the method and validation status are displayed clearly.

## 2.9 Internal units and time are fixed

Internal units:

| Quantity | Unit |
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

Internal timestamps:

- UTC;
- ISO 8601;
- timezone-aware only.

User-facing timestamps may be displayed in Asia/Kolkata.

## 2.10 Scientific claim scope

Every forecast or demonstration must expose:

```text
spatial_validation_scope
temporal_validation_scope
model_readiness
limiting_dataset
```

The system must not claim citywide street-scale predictive accuracy from a pilot-area or unvalidated model.

---

# 3. Final Technology Stack

## 3.1 Backend and APIs

- Python 3.12.x
- FastAPI
- Pydantic
- SQLAlchemy
- GeoAlchemy2
- Alembic

## 3.2 GIS and spatial processing

- PostgreSQL + PostGIS
- GeoPandas
- Shapely
- PyProj
- Pyogrio
- Rasterio
- GDAL
- OSMnx

## 3.3 Graph processing

- NetworkX

## 3.4 Scientific computing

- NumPy
- SciPy
- Numba

## 3.5 Drainage hydraulics

- EPA SWMM
- PySWMM
- coupled-mode routing: **Dynamic Wave (`DYNWAVE`)**

## 3.6 Scientific multidimensional data

- Xarray
- Zarr

Optional later for larger workloads:

- Dask

## 3.7 Weather models and local machine learning

- Sequence 16: a pinned pretrained GraphCast variant with its compatible isolated runtime
  (model-specific JAX/Haiku dependencies verified against the selected code revision).
- Sequence 16: XGBoost and supporting feature/evaluation tooling with separate model/data locks.
- PyTorch/PyTorch Geometric remain optional future tools, not requirements for this integration.

Historical data/provenance begins in 11; a conservative engineering baseline and development
evaluation protocol precede learned work in 15; actual GraphCast inference and XGBoost training
occur in 16; final independent evaluation and promotion decisions occur in 19. Rainfall learning
does not replace hydraulic ownership, and no transformer is required. This explicitly supersedes
the former post-Sequence-19-only ML ordering.

## 3.8 Messaging, cache, and storage

Target architecture:

- NATS + JetStream
- Redis
- MinIO
- PostgreSQL/PostGIS

Preserve the existing deployment and add processes only for demonstrated requirements. Scientific correctness takes precedence over service decomposition.

## 3.9 API gateway

- Traefik

## 3.10 Frontend

- React
- TypeScript
- Vite
- TanStack Query
- Zustand
- MapLibre GL JS
- CesiumJS

## 3.11 Testing

- pytest
- Ruff
- mypy
- Playwright

## 3.12 Deployment

- Docker
- Docker Compose

Kubernetes is not required for the SIH prototype.

## 3.13 Dependency locking

The repository must contain a reproducible dependency lock.

AI coding sessions must not upgrade major scientific dependencies unless the active sequence explicitly requires it.

---

# 4. Logical Service Boundaries and SIH Deployment Profile

The target platform contains the following logical domain components.

| Logical unit | Primary responsibility |
|---|---|
| `registry-service` | data source metadata, access policy, source status |
| `harvester-worker` | external data acquisition and raw-data versioning |
| `spatial-worker` | spatial normalization and reference-system harmonization |
| `reconstruction-worker` | municipal drainage-map reconstruction |
| `terrain-worker` | visual and hydraulic terrain preparation |
| `urban-gis-service` | visual city and hydraulic surface preparation |
| `drain-model-service` | drainage graph, parameterization, exchange geometry |
| `twin-service` | immutable digital-twin manifests and readiness |
| `forcing-service` | rainfall/QPE/nowcast/blending, hydraulic boundary series, operational controls, and versioned ForcingPackage creation |
| `hydraulics-worker` | surface solver, SWMM, coupling, state initialization, volume accounting |
| `forecast-service` | forecast orchestration, forecast version/freshness management, FloodCube creation |
| `risk-service` | ensemble aggregation, scenario analysis, decision intelligence |
| `routing-service` | road exposure consumption and time-dependent routing |
| `geospatial-service` | COG/vector/raster/3D publication products |
| `web` | user interface |
| `event/evaluation records` | historical evidence, availability, dataset splits and evaluation |
| `weather-model worker` | isolated GraphCast inference and XGBoost training/inference |

### SIH deployment profile

For the hackathon prototype, logical services may be consolidated into fewer deployable processes, for example:

```text
FloodGuard API
├── registry
├── GIS/twin
├── forcing
├── forecast orchestration
├── risk
└── routing

Hydraulics Worker
├── 2D solver
├── SWMM adapter
├── exchange
├── time coordinator
└── volume ledger

PostGIS + Object Storage
Web UI
```

The logical data contracts and ownership boundaries remain authoritative even when deployment is consolidated.

---

# 5. Service Data Ownership

A service must not directly depend on another service's private database tables.

One PostgreSQL/PostGIS instance may be shared physically, but ownership remains explicit through schemas or equivalent access boundaries.

Example:

```text
registry.*
spatial.*
drain.*
twin.*
forcing.*
forecast.*
routing.*
```

Cross-domain information must move through documented APIs, documented events, immutable object references, or explicitly shared read models.

---

# 6. Secrets and Credentials

The Data Source Registry stores:

```text
credential_ref
```

It must not store raw passwords, tokens, or API keys.

Secrets are supplied through environment secrets, Docker secrets, or a future dedicated secrets manager.

---

# 7. Common Identifiers

The original common identifier names below remain stable where implemented; this list does not assert that every later product already exists:

```text
city_id
source_id
dataset_id
dataset_version_id
ward_id
catchment_id
twin_id
twin_version
drain_node_id
drain_edge_id
exchange_id
exchange_binding_id
road_edge_id
rain_event_id
forcing_package_id
hydraulic_state_id
simulation_id
forecast_id
scenario_id
route_id
job_id
```

---

R2 adds historical_event_id, observation_id, availability_record_id, evaluation_dataset_id, model_artifact_id, training_run_id, weather_run_id, evaluation_report_id and replay_manifest_id in their owning sequences. They reference existing identities rather than replacing them.

# 8. Common Asynchronous Job Contract

Heavy operations run as asynchronous jobs.

Allowed states:

```text
QUEUED
RUNNING
SUCCEEDED
FAILED
CANCELLED
```

Required fields:

```text
job_id
job_type
created_at
started_at
completed_at
progress
correlation_id
heartbeat
retry_count
resource_requirement
error_code
error_message
```

FastAPI submits the job. A worker performs the computation.

Long hydraulic simulations must not execute inside an HTTP request handler.

---

# 9. Common Event Contract

Each event contains:

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

Consumers are idempotent.

A redelivered event must not repeat completed side effects.

---

# 10. Canonical Forecast Inputs

A forecast never consumes rainfall alone. It consumes a versioned:

```text
ForcingPackage
```

The package contains:

```text
forcing_package_id
issue_time
valid_from
valid_to
RainCube reference
HydraulicBoundarySeries reference
OperationalControlSeries reference
AntecedentForcing reference
quality_summary
```

## 10.1 HydraulicBoundarySeries

Represents time-varying hydraulic boundaries such as river stage, canal stage, outfall stage, and tide level.

Required fields include:

```text
boundary_id
time
stage_m
vertical_datum
vertical_unit
vertical_transform_status
interpolation_method
source
quality
```

Baseline interpolation semantics:

- water-level/stage series: `LINEAR` between valid observations/forecast points unless the source explicitly requires another method;
- discontinuities or externally declared step changes: `STEP_HOLD`;
- interpolation behavior must be stored with the series and must never be guessed at runtime.

## 10.2 OperationalControlSeries

Represents time-varying infrastructure operation such as pump availability, pump on/off state, and gate/sluice state where applicable.

Required fields include:

```text
asset_id
time
operating_state
control_value
interpolation_method
source
quality
```

Baseline interpolation semantics:

- discrete pump/gate states: `STEP_HOLD`;
- continuous control values: use the method declared by the source, otherwise `STEP_HOLD` for the prototype.

Operational controls must never be linearly interpolated when the physical control is discrete.

## 10.3 AntecedentForcing

Contains the historical forcing window used to initialize the model before forecast time.

---

# 11. Canonical Hydraulic State

The current model condition at forecast start is represented by:

```text
HydraulicState
```

Required fields:

```text
hydraulic_state_id
created_at
valid_at
state_age_seconds
state_freshness_status
twin_id
surface_depth_reference
surface_velocity_reference
SWMM_hotstart_reference
drain_node_head_reference
drain_flow_reference
loss_model_state_reference
soil_or_infiltration_state_reference
boundary_state_reference
state_source
state_quality
```

Allowed freshness states:

```text
FRESH
AGING
STALE
UNKNOWN
```

The forecast service must reject or explicitly downgrade a stale starting state according to the active operational policy.

Allowed initialization modes:

```text
COLD_START
SPINUP_FROM_ANTECEDENT_FORCING
HOTSTART
OBSERVATION_ASSIMILATED
```

For the SIH prototype, `SPINUP_FROM_ANTECEDENT_FORCING` is the preferred default when sufficient antecedent data are available.

---

# 12. The 20 Development Sequences

# Sequence 1 — Platform Foundation, Contracts, Units, Time, Jobs and Events

**Release target:** v0.1

## Objective

Create the complete technical foundation without domain-specific flood logic.

## Build

- monorepo;
- logical service directories;
- reusable FastAPI/Pydantic templates;
- PostgreSQL/PostGIS;
- object storage;
- optional Redis/NATS adapters behind interfaces;
- Docker Compose;
- canonical SI units;
- UTC timestamp rules;
- job contract;
- event contract;
- idempotency framework;
- structured logging;
- correlation IDs;
- `/health`, `/ready`, `/version`;
- pytest, Ruff, mypy;
- dependency lock;
- local verification command.

## Required local verification

```bash
python scripts/verify.py
```

The command must work without hosted CI.

## Completion gate

A clean environment starts the required prototype infrastructure, health checks pass, idempotent processing is demonstrated where events are enabled, and local verification passes.

## Explicitly excluded

No GIS processing, drainage logic, rainfall model, hydraulic solver, AI, or production dashboard.

---

# Sequence 2 — Data Source Registry, Access Governance and Fallback Sources

**Release target:** v0.2  
**Logical unit:** `registry-service`

## Objective

Create the authoritative catalogue of external datasets and feeds.

## Initial data categories

- KMC/OpenCity drainage maps;
- ward boundaries;
- microwatersheds/catchments;
- water bodies;
- OpenStreetMap;
- elevation products;
- Sentinel imagery;
- rainfall observations;
- historical rainfall products;
- external nowcasts;
- future radar/DWR feeds;
- LiDAR;
- pump SCADA;
- drain sensors;
- CCTV observations;
- traffic feeds.

## Required metadata

```text
source_id
provider
dataset_name
city_id
category
endpoint
access_method
format
licence
redistribution_policy
automation_allowed
authentication_type
credential_ref
authority_level
horizontal_crs
vertical_datum
spatial_resolution
temporal_resolution
refresh_policy
fallback_source_id
status
```

## Access classes

```text
OPEN_AUTOMATED
OPEN_MANUAL
PUBLIC_VIEW_ONLY
AUTHORIZATION_REQUIRED
COMMERCIAL_OPTIONAL
UNKNOWN
```

## Completion gate

Every dataset required by the prototype has a documented acquisition method, legal/access status, authority level, and fallback plan where appropriate.

---

# Sequence 3 — Automatic Data Harvester and Immutable Raw Data Vault

**Release target:** v0.3  
**Logical unit:** `harvester-worker`

## Objective

Automatically retrieve only data whose access conditions permit automated collection.

## Supported acquisition methods

- HTTP;
- CKAN;
- REST;
- STAC;
- WMS/WFS/WMTS where appropriate;
- GeoJSON;
- KML;
- CSV;
- GeoTIFF;
- NetCDF/GRIB;
- OSMnx/Overpass for pilot areas;
- PBF/extract-based OSM ingestion for larger areas.

## OSM rule

Do not bulk-download standard OSM map tiles and do not use the OSM editing API as a bulk data API.

## Raw storage pattern

```text
raw/{city_id}/{source_id}/{dataset_version_id}/...
```

Raw objects are immutable.

## Completion gate

A Kolkata bootstrap job retrieves supported open datasets, computes checksums, detects changes, creates new versions when needed, and never overwrites an earlier raw version.

---

# Sequence 4 — Spatial Normalization, Variable-Specific Resampling and Reference Harmonization

**Release target:** v0.4  
**Logical unit:** `spatial-worker`

## Objective

Create spatially consistent datasets without altering their physical meaning.

## Horizontal reference

Use a configurable metric working CRS appropriate for Kolkata.

## Vertical reference

Every elevation-bearing dataset stores:

```text
vertical_datum
vertical_unit
vertical_offset
datum_transform_status
vertical_reference_confidence
```

Terrain, drain inverts, canal stage, river stage, and tide levels must not be compared until their vertical references are compatible or explicitly transformed.

## Variable-specific resampling policy

Do not apply one generic interpolation method to all data.

### Categorical data

Use categorical/nearest-neighbour-style remapping.

### Elevation

Use a documented elevation-appropriate interpolation/conditioning method and preserve source uncertainty.

### Rainfall

Use area/volume-conservative remapping so that resampling does not change area-integrated rainfall volume beyond a declared numerical tolerance.

For rain rate \(R_{i,t}\) in mm/h over cell area \(A_i\):

\[
V_r = \sum_t \sum_i \frac{R_{i,t}}{1000\times3600} A_i\Delta t
\]

The remapping conservation diagnostic is:

\[
\epsilon_r = \frac{|V_{before}-V_{after}|}{\max(V_{before},\epsilon)}
\]

The accepted tolerance must be versioned in the solver/forcing configuration.

## Engineering QA map

Create a minimal MapLibre QA page supporting overlays for wards, roads, buildings, source map layers, reconstructed drainage when available, and quality/confidence markers.

## Completion gate

Core Kolkata layers align correctly, elevation-bearing datasets carry valid vertical-reference metadata, variable-specific resampling policies are implemented, rainfall remapping passes its conservation test, and the QA viewer can display normalized layers.

---

# Sequence 5 — Legacy Municipal Drainage Reconstruction

**Release target:** v0.5  
**Logical unit:** `reconstruction-worker`

## Objective

Convert real municipal drainage drawings into traceable geospatial drainage features.

## Initial scope

One real KMC/OpenCity ward map.

## Processing order

```text
Source PDF/CAD/map
↓
Inspect native vector/text content
↓
Extract native geometry/text where possible
↓
Georeference
↓
Detect drain lines and structures
↓
Associate labels
↓
Clean geometry
↓
Assign confidence
↓
Human QA review
↓
Persist approved reconstruction
```

## OCR rule

OCR is used only when native vector/text extraction is insufficient.

## Missing engineering attributes

Missing dimensions, invert elevations, flow directions, or materials remain `NULL` at this stage.

## Completion gate

At least one real municipal drainage map is converted into a geographically valid, human-reviewed, provenance-preserving vector layer.

---

# Sequence 6 — Hydraulically Conditioned Terrain and Multi-Level Urban Structures

**Release target:** v0.6  
**Logical unit:** `terrain-worker`

## Objective

Create terrain suitable for hydraulic simulation while preserving known limitations of source elevation data.

## Maintain three products

```text
raw_elevation
visual_terrain
hydraulic_terrain
```

## DSM/DTM rule

If the elevation source contains buildings, vegetation, or infrastructure, do not treat it automatically as bare-earth hydraulic terrain.

## Depression rule

Do not automatically fill every sink. Preserve genuine flood-relevant depressions such as underpasses, road sags, low intersections, and intended storage depressions.

## Multi-level structures

Represent explicitly where they affect hydraulic connectivity:

- flyovers;
- bridges;
- underpasses;
- culverts;
- elevated roads;
- tunnels.

A single-valued terrain elevation alone must not be used to represent overlapping road levels.

## Required resolution metadata

```text
native_horizontal_resolution
computational_resolution
effective_information_resolution
vertical_quality
```

## Terrain validation gate

A terrain cannot support `HYDRAULIC_VALIDATED` readiness solely because CRS and metadata are present. Where observations permit, store:

```text
vertical_validation_method
vertical_rmse_m
control_point_count
road_sag_validation
underpass_validation
drain_rim_elevation_consistency
validation_limitations
```

When adequate vertical validation is unavailable, the twin must remain `HYDRAULIC_SCENARIO_READY` or lower.

## Completion gate

The pilot area has documented visual and hydraulic terrain, genuine depressions are preserved, important multi-level structures are classified correctly, source-resolution limitations are explicit, and terrain readiness is assigned conservatively.

---

# Sequence 7 — Urban GIS Reconstruction, Hydraulic Surface Classes and Roof Runoff Policy

**Release target:** v0.7  
**Logical unit:** `urban-gis-service`

## Objective

Create a detailed visual city and a separate simplified hydraulic surface model.

## Visual model

May include detailed building geometry, building heights/extrusions, roads, wards, rivers, canals, water bodies, parks, and imagery.

## Hydraulic model

Contains simplified hydraulic classes such as:

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

Each hydraulically active feature receives a `hydraulic_domain`.

## Hydrologic loss modes

### Simplified runoff mode

\[
R_e=C_rR
\]

### Explicit-loss mode

\[
R_e=R-I-L
\]

Only one compatible formulation is active for a given surface class.

## Roof runoff policy

For the prototype:

```text
Roof rainfall
↓
calculate roof runoff volume
↓
assign runoff to versioned Roof Runoff Receiving Geometry
↓
later bind receiving geometry to numerical surface cells after the grid exists
```

Sequence 7 defines receiving geometry or explicit drainage targets, not `surface_cell_ids`.

A roof may discharge to adjacent ground/road receiving geometry or a known roof-drain connection to a drainage inlet.

The transferred runoff volume must equal roof-generated runoff volume within declared numerical tolerance.

## Completion gate

The pilot has separate visual and hydraulic city representations, every hydraulic feature has an explicit domain owner, and every roof has a documented runoff rule with versioned receiving geometry or an explicit drain target.

---

# Sequence 8 — Drain Graph, Hydraulic Parameterization, Exchange Geometry and Readiness

**Release target:** v0.8  
**Logical unit:** `drain-model-service`

## Objective

Create the directed drainage model and define the physical locations where water can exchange with the surface.

## Drain graph

\[
G=(V,E)
\]

### Node types

```text
INLET
MANHOLE
JUNCTION
STORAGE
PUMP
OUTFALL
```

### Edge types

```text
PIPE
OPEN_DRAIN
CULVERT
CANAL
```

## Flow-direction priority

1. municipal engineering arrows/labels;
2. invert elevations;
3. known pump/outfall topology;
4. hydraulic/topological inference;
5. surface terrain only as a low-confidence fallback.

## Hydraulic parameterization

Assess and store geometry, length, diameter/width/height, cross-section, invert elevations, slope, roughness, inlet capacity, node storage, pump definition, outfall definition, effective capacity, and condition.

## Exchange Geometry

Sequence 8 defines physical exchange locations, not surface-cell IDs.

Each exchange location stores:

```text
exchange_id
exchange_type
drain_node_id
geometry
x
y
rim_elevation
opening_area
inlet_type
discharge_coefficient
maximum_inlet_capacity
source
confidence
```

Supported exchange types:

```text
POINT_INLET
MANHOLE_SURCHARGE
LINEAR_OVERTOP
```

For the baseline SIH C1 coupling, `POINT_INLET` and `MANHOLE_SURCHARGE` are mandatory. `LINEAR_OVERTOP` is implemented only if the pilot requires distributed open-drain/canal overtopping.

## Readiness classes

```text
VISUAL_ONLY
HYDROLOGIC_READY
HYDRAULIC_SCENARIO_READY
HYDRAULIC_VALIDATED
```

## Two-ward requirement

Before Sequence 9 is completed, demonstrate at least one genuine drainage continuation across two adjacent wards.

## Completion gate

A cross-ward drainage path reaches a defensible downstream destination, hydraulic parameter gaps are explicit, and all potential surface-drain exchange points are stored as geometry.

---

# Sequence 9 — Versioned Urban Digital Twin Builder

**Release target:** v0.9  
**Logical unit:** `twin-service`

## Objective

Freeze approved static city/model components into a reproducible digital-twin version.

## Twin manifest

```text
twin_id
city_id
pilot_area
visual_terrain_version
hydraulic_terrain_version
visual_city_version
hydraulic_surface_version
roof_runoff_geometry_version
drain_graph_version
exchange_geometry_version
hydraulic_parameter_set_version
ward_version
catchment_version
waterbody_version
pump_asset_version
horizontal_crs
vertical_reference_status
hydraulic_readiness
software_version
```

## Rule

A forecast consumes a `twin_id`; it does not assemble loose source files at runtime.

## Checkpoint A

**Versioned Digital Twin Ready**

## Completion gate

The same twin can be recreated from its manifest, and the manifest clearly states whether the twin is visual-only, scenario-ready, or hydraulically validated.

---

# Sequence 10 — Dynamic Forcing Service: Meteorology, Hydraulic Boundaries and Operational Controls

**Release target:** v1.0  
**Logical unit:** `forcing-service`

## Objective

Create the complete versioned time-varying forcing package required for a 0–3 hour hydraulic forecast.

## Meteorological processing stages

```text
Raw meteorological data
↓
Precipitation estimation / QPE when required
↓
Gauge bias correction when data are available
↓
Storm-motion estimation
↓
Radar extrapolation / nowcast when appropriate
↓
Optional radar–NWP blending
↓
RainCube
```

## Supported rainfall modes

1. historical replay;
2. synthetic storm;
3. externally supplied rainfall forecast/nowcast;
4. radar-based nowcast when suitable radar fields are available;
5. radar–NWP blend when both are available.

pySTEPS may be used as an optional baseline framework for radar nowcasting/blending when suitable data exist.

## Lead-time policy

When skillful radar is available, extrapolation may dominate shorter lead times. For longer lead times, particularly toward 90–180 minutes, radar–NWP blending is preferred when an appropriate NWP source is available.

The system must not label a synthetic or persistence extension as a genuine operational 3-hour meteorological forecast.

## IMERG rule

IMERG may be used for development, replay, and ingestion testing. It must not be described as a street-scale radar substitute.

## RainCube

Store as Xarray/Zarr.

Dimensions:

```text
time
y
x
ensemble_member  # optional
```

Variables:

```text
rain_rate
accumulation
quality_flag
```

Required metadata:

```text
issue_time
valid_time
lead_time
source
units
horizontal_crs
native_spatial_resolution
effective_spatial_resolution
grid_transform
ensemble_definition
```

## Dynamic hydraulic boundaries

Create `HydraulicBoundarySeries` for river stage, canal stage, tide level, and outfall stage.

The service must refuse hydraulic use of a boundary series whose vertical reference cannot be made compatible with the active twin.

## Dynamic operational controls

Create `OperationalControlSeries` for pump availability/state/control and gate/sluice state where relevant.

Discrete states use `STEP_HOLD`.

## Forecast-horizon validation

Before a forecast is accepted, the forcing package is classified as:

```text
FULL_COVERAGE
PARTIAL_COVERAGE
BLENDED_EXTENSION
INSUFFICIENT
```

A 90-minute rainfall forecast must never be silently extended to 180 minutes.

## Completion gate

`forcing-service` can create a complete versioned ForcingPackage for replay, synthetic, or available operational data, with compatible vertical references, explicit interpolation rules, explicit horizon coverage, rainfall-volume conservation, and no silent temporal extension.

---

# Sequence 11 — Compatibility, Historical Events and Observation Data

**Release target:** v1.1
**Owners:** registry, harvester, spatial and forcing components; new event/evaluation records
**Purpose:** make the existing platform accept traceable historical evidence without changing the meaning of its retained products.

## Entry dependencies

Read the Sequence 8-10 ledgers and reproduce their affected checks. The current Sequence 9/10
DATA-08-01 blocker remains open until the existing source-bound drainage gate passes. It does
not prevent rainfall-only processing. Real hydraulic use remains blocked where the twin is ineligible.
This sequence is the next implementation target after this planning-only revision.

## Existing implementation modifications

| Existing area | Required work | Compatibility rule |
|---|---|---|
| Sequence 2 registry | Add concrete product/feed records for selected historical rainfall, atmospheric states, gauge/radar and flood observations; retain access evidence and actual authentication requirements | A catalogue entry is not a working feed; never change authorization from a guess |
| Sequence 3 acquisition | Add product/time-window selection, paging/retries where supported, resumable downloads and immutable acquisition receipts | Reuse the raw vault, hashes and credential references |
| Sequence 4 normalization | Decode provider time/units/QC and transform observation geometry | Preserve native support, missingness, CRS and datum |
| Sequences 5-9 static products | Resolve evidence-backed corrections and the cross-ward blocker through their existing workflows | New source/parameter versions create new products and twins |
| Sequence 10 forcing | Add adapters from prepared event windows into the current rainfall contract | Preserve v1 identities/readers; keep the three-hour forecast-window bound |
| Cross-cutting contracts | Add typed event and availability manifests referencing existing products | No unversioned fields silently added to immutable manifests |

First retain representative v1 manifests, requests and blobs with known identities. Prove that
new readers can verify and recreate them. Prefer separate versioned manifests for new metadata.
If a v2 forcing schema is necessary, specify its writer, v1 reader, explicit conversion and
version dispatch. Even optional serialized fields can change hashes. Never rewrite old bytes,
reinterpret an old policy identifier, or perform a destructive database reset.

## Build order

1. Inventory the pilot and candidate storm/dry events before selecting demonstration dates.
2. Define HistoricalEventManifest, ObservationRecord and SourceAvailabilityRecord.
3. Implement one actual historical precipitation adapter and ingest a permitted numerical event.
4. Normalize station/interval data and gridded data through separate adapters.
5. Inventory GraphCast-compatible global atmospheric archives; acquire a bounded initial-state
   bundle if access and compute/storage allow. Execution belongs to Sequence 16.
6. Bind event-date terrain/drainage/boundaries/operations and flood observations where available.
7. Build consecutive Sequence 10 replay windows plus the declared antecedent window.
8. Produce a lightweight rainfall preview and a coverage report from those real artifacts.

## Event and observation contract

HistoricalEventManifest contains a schema version, historical_event_id, catchment_id, event
start/end, UTC timezone policy, exact source/dataset versions, observation references, available
twin/forcing references, evidence gaps, event-date infrastructure assumptions and checksums.
Use historical_event_id for the storm/event; the existing event_id remains the messaging-envelope
identifier. Define any relationship to the existing rain_event_id explicitly.

ObservationRecord contains quantity, value or array reference, units, station/geometry identity,
interval_start, interval_end, observation uncertainty if supplied, QC/missing mask, source/version,
native resolution and support. Flood extent, flood depth, water level and rainfall are distinct
quantities. A water level requires its vertical reference; a depth requires its local reference.

SourceAvailabilityRecord contains source issue time where applicable, observed/valid interval,
provider_available_at where evidenced, availability_evidence, acquired_at, source revision,
and availability_status = VERIFIED / ESTIMATED / UNKNOWN. Store an estimated latency policy
separately. Today's acquisition time and HTTP Last-Modified do not prove historical availability.

The evaluation dataset definition records whole-event TRAIN / TUNE / TEST assignments, geography
and dates, label type/quality, feature/target support and a split hash. Freeze test assignments
before calibration/model selection; do not claim that every acquired event is a training event.

## Source acceptance rules

- ERA5 is a reanalysis candidate. Pin product, variables, levels, grid, units and time convention.
  Local single-level data alone cannot initialize the full GraphCast model.
- IMERG is a coarse satellite-estimate source for replay. Preserve its run/version and latency;
  Final data may be a retrospective target but never a historical real-time input by default.
- IMD AWS/ARG and radar sources require actual numerical samples and provider access evidence.
  Verify rainfall fields, accumulation periods, station coverage and QC. An image or daily total
  does not satisfy a sub-hourly numerical radar/gauge requirement.
- Numerical radar QC, gauge adjustment, storm-motion estimation and rainfall nowcasting belong
  to Sequence 16; this sequence establishes the archived observation and access contracts.
- Missing real gauge/radar archives are recorded as unavailable capabilities. They cannot be
  replaced with synthetic samples labelled as observations. Approved numerical files may be
  imported with the same provenance requirements when automated access is unavailable.
- No universal provider cadence, free-access claim, account scheme or live availability is assumed.

## Preparation and missing-data behavior

Differentiate rates from accumulations, cumulative-counter resets, timezones and interval edges.
Deduplicate by source/station/interval/version and retain corrections as new versions. Preserve
missing data; never fill it with zero rain. Convert only defensible supported intervals into the
finite nonnegative RainInput contract. Unsupported areas/intervals fail or use a separately declared
fallback with changed lineage and coverage. Do not silently patch missing gauge values by radar.

Bind a long historical event to multiple forecast-sized packages with explicit state continuity.
Do not expand the 3-hour runtime forecast contract to hold a multi-year training archive or global
atmospheric fields. Store large training/weather inputs separately as versioned file references.

## Visible result

A small read-only browser page or generated local report shows one actual rainfall event, a
catchment map, interval/accumulation charts, source resolution and missing-data coverage. Simple
play/pause and time selection may be included. It displays rainfall, not simulated flood depth.
This is a bounded data-preview prerequisite; the full product dashboard remains Sequence 18.

## Required verification

Known v1 identities and artifact recreation; additive migration/read compatibility; unit/timezone
and reset examples; duplicates/corrections; unknown availability; missing-data rejection;
source permission failure; geographic/temporal overlap; conservation during remapping; correct
event/package links; no look-ahead in eligible input selection; correctly labelled preview.
Keep the earlier affected-scope checks and document any newly exposed defect in its owning module.

## Completion and freeze gate

Freeze event/observation/availability v1 and adapter interfaces after at least one real numerical
rainfall event produces reproducible replay packages and a correctly labelled preview. Record
the complete candidate-event inventory and blocked feeds. The historical data gate cannot pass
using only synthetic fixtures. Missing flood observations do not prevent rainfall replay, but
do prevent a measured flood-validation claim. Re-run inherited gates without suppressing DATA-08-01.

## Outside this sequence

No hydraulic flood map, GraphCast inference/training, XGBoost fit, live warning, probability or
route recommendation is claimed. No service or model is started by browsing the preview.

# Sequence 12 — Baseline 2D Surface Solver and Numerical Bindings

**Release target:** v1.2
**Owner:** hydraulics-worker
**Entry:** Sequence 11 contracts, exact Sequence 9 twin, Sequence 10 forcing and declared solver configuration.

## Existing implementation modifications

Extend the static-twin consumption layer with separately versioned numerical-grid bindings.
Sequence 7/8 physical geometry remains grid independent. New numerical bindings refer to
exact geometry, grid and twin versions; they do not overwrite earlier physical products.
Resolve documented defects through their owning earlier modules and repeat affected checks.

## Objective

Implement one clearly defined baseline surface-flow solver and freeze its mathematical/numerical contract.

## Baseline formulation

For the SIH prototype, the baseline is:

> **2D local-inertial shallow-water approximation on a structured Cartesian grid.**

Do not substitute a full Saint-Venant solver, cellular automaton, D8 routing model, or another formulation without an explicit revision of this specification.

## Scientific applicability rule

The local-inertial approximation is used as a computationally efficient urban-flood model for predominantly shallow, low-to-moderate Froude-number flow. It must not be described as universally equivalent to the full shallow-water equations.

The solver must expose an applicability diagnostic such as:

```text
LOCAL_INERTIAL_VALID
LOCAL_INERTIAL_CAUTION
OUTSIDE_VALIDATED_RANGE
```

The mathematical specification must define the diagnostic criteria and acknowledge limitations for strongly supercritical flow, hydraulic jumps, rapidly varied flow, steep ramps, and similarly energetic localized conditions.

## Numerical baseline

- structured Cartesian grid;
- explicit/controlled local-inertial update;
- adaptive timestep governed by the selected stability/CFL criterion;
- NumPy/SciPy implementation;
- Numba acceleration where profiling demonstrates benefit.

The exact equations, discretization, boundary treatment, wetting/drying threshold, friction law, stability criterion, applicability diagnostic, and numerical tolerances must be written in a dedicated **Surface Solver Mathematical Specification** before implementation is declared complete.

## Development order

1. flat plane;
2. sloped plane;
3. controlled depression;
4. simple road;
5. road intersection;
6. synthetic urban block;
7. real pilot terrain.

## Inputs

- hydraulic terrain;
- hydraulic surface classes;
- roughness;
- selected loss/infiltration model;
- remapped rainfall;
- external boundaries;
- surface-drain exchange flux.

## Outputs

```text
surface_depth
velocity_x
velocity_y
surface_storage
boundary_outflow
infiltration_or_loss
peak_depth
time_to_peak
solver_applicability
```

## Exchange Binding

Once the numerical grid exists, create an `ExchangeBinding` for each `exchange_id`.

Required fields:

```text
exchange_binding_id
exchange_id
grid_version
surface_cell_ids
cell_weights
binding_method
quality
```

## Roof Runoff Grid Binding

Bind each Sequence 7 Roof Runoff Receiving Geometry to receiving surface cells and conservative weights.

## Scientific tests

- mass conservation;
- flat-plane no-flow case;
- controlled-slope flow;
- depression filling/draining behavior;
- grid sensitivity;
- timestep sensitivity;
- wetting/drying stability;
- applicability-diagnostic tests.

## Inherited component acceptance

The baseline local-inertial surface solver passes declared benchmark and conservation tolerances, limitations are explicit, and every active surface-drain exchange geometry is bound to the numerical grid.

## Additional build and output requirements

Use one and only one selected Sequence 7 runoff/loss rule per surface. For roofs, route runoff
once to the declared recipient using conservative weights, without adding the same rainfall
again at the receiver. Direct-to-drain roof targets are retained as explicit pending transfers
until Sequence 14 connects them to the 1D model; do not silently reroute them.

Declare the solver treatment of boundaries, storage cells, masks, building barriers and road
levels. An unsupported boundary or missing hydraulic terrain fails explicitly. Store initial
conditions, grid_version, timestep diagnostics and the complete SurfaceRunResult provenance.

Document equations in docs/mathematics/surface-solver.md, including SI units, friction,
positivity/wetting-drying, source/sink splitting, stability, stopping rules and test tolerances.
Derive rendering assets from depth/velocity arrays; no visual effect may modify scientific arrays.

## Visible result

Reproducible synthetic surface benchmarks with depth/storage plots and a water-balance report.
Real terrain examples retain their readiness and applicability limitations.

## Completion and freeze gate

The inherited component acceptance plus roof-volume tests, binding uniqueness/conservation,
deterministic recreation, boundary/missingness checks and versioned numerical contracts pass.
This validates a surface component; it does not yet establish coupled or observed-flood accuracy.

# Sequence 13 — SWMM Drainage Engine and Operational Boundaries

**Release target:** v1.3
**Owner:** hydraulics-worker
**Entry:** Sequence 12 surface interface, versioned drain graph/parameters, static assets and forcing boundary/control series.

## Existing implementation modifications

Add an adapter from the accepted Sequence 8 graph and Sequence 9 twin to a reproducible SWMM
model. Consume Sequence 10 stage/control series by exact asset identity. Unsupported gate/sluice
assets remain rejected until an evidenced static contract is implemented and versioned.

## Objective

Use EPA SWMM/PySWMM as the initial 1D drainage hydraulic engine.

## Mandatory coupled-mode configuration

```text
FLOW_ROUTING = DYNWAVE
SWMM subcatchment runoff = OFF
SWMM external ponding storage = OFF
```

Dynamic Wave is mandatory in coupled mode because the platform intends to represent backwater, surcharge, reverse flow, downstream-stage effects, pumps, and pressurized conditions.

## Pipeline

```text
Drain Graph
+
Hydraulic Parameter Set
↓
SWMM Model Generator
↓
EPA SWMM Dynamic Wave
↓
PySWMM Adapter
↓
Canonical Drain Hydraulic State
```

## Coupled-mode rules

When `COUPLED_2D_1D` is active:

1. SWMM hydrologic subcatchment runoff is disabled.
2. SWMM receives surface-derived inflow only through defined exchange nodes.
3. Above-ground ponding is owned by the 2D surface solver.
4. Surface/drain transfer is controlled by the explicit exchange module in Sequence 14.
5. Native SWMM flooding must not be used in a way that bypasses or double-counts the declared exchange formulation.

## Required outputs

```text
node_head
node_depth
edge_discharge
edge_velocity
capacity_utilization
surcharge_state
reverse_flow_state
pump_flow
```

## Validation cases

- single conduit;
- branching network;
- pump;
- outfall;
- backwater;
- surcharge;
- reverse flow;
- generated model vs trusted manually prepared SWMM case.

## Inherited component acceptance

The generated SWMM model reproduces trusted SWMM reference behavior and reports acceptable drainage mass balance.

## Additional implementation requirements

Pin EPA SWMM/PySWMM and their execution environment. Compare generated input with a trusted
manually prepared reference and retain .inp, settings, warnings, output and mass-balance receipts.
Translate source heads/stages only through the accepted vertical transform. Respect discrete
STEP_HOLD pump/control states and documented continuous-series interpolation.

Define tested hooks for node inflow and surcharge extraction. Demonstrate how internal SWMM
flooding and transfers will reconcile with the surface ledger; external ponding OFF alone is
not proof of conservation. Every native loss, outfall discharge and transfer must be accounted.
Provide hotstart serialization and checks for matching model/parameter versions.

## Visible result

Drain head/discharge/pump traces for a reference network, including backwater and reverse flow.

## Completion and freeze gate

The inherited component acceptance, control/tide interpolation, incompatible-datum rejection,
hotstart recreation, native-flooding accounting and missing-parameter rejection all pass.
Freeze the model generator and DrainHydraulicState interface, without claiming coupling is complete.

# Sequence 14 — Conservative Coupling, Initialization and Historical Reconstruction

**Release target:** v1.4
**Owner:** one in-process hydraulics-worker
**Entry:** accepted Sequence 12/13 component interfaces, physical/grid bindings and exact forcing/twin references.

## Existing implementation modifications

Connect the surface, roof and drainage bindings through a versioned HydraulicsRunRequest.
Link historical runs to Sequence 11 event manifests. Keep state generation separate from
Sequence 10 forcing assembly; an absent antecedent window never implies a dry state.

## Objective

Run the surface and drainage models as one conservative coupled simulation and produce a formal HydraulicState at forecast start.

## Canonical Hydraulics Worker Input

```text
HydraulicsRunRequest
├── twin_id
├── forcing_package_id
├── hydraulic_state_id or initialization_request
├── solver_configuration
├── run_mode
└── scenario_parameter_overrides  # optional and explicitly versioned
```

The worker must not assemble unversioned forcing, geometry, or parameter inputs internally.

## Coupling level for the SIH prototype

Use:

```text
C1_LAGGED_HEAD_COUPLING
```

At coupling step `n`, exchange over the next interval uses the current surface hydraulic head and latest synchronized SWMM node head.

Surface head:

\[
H_s = z_s + h_s
\]

Drain/node head:

\[
H_d = H_{SWMM}
\]

Define the head difference:

\[
\Delta H = H_s - H_d
\]

### 14.1 Bidirectional exchange law

The exchange module must implement a documented head-controlled weir/orifice-style formulation with explicit free/submerged behavior where applicable.

A baseline submerged/orifice form is:

\[
Q = C_d A_o\sqrt{2g|\Delta H|}
\]

with sign determined by hydraulic-head direction:

```text
ΔH > 0  → surface to drain
ΔH < 0  → drain to surface
```

For inlet types better represented by a weir relation under free inflow, the model may use a documented form such as:

\[
Q = C_w L H^{3/2}
\]

The exact switching rule between weir and orifice behavior must be specified and tested. The runtime must not guess the exchange regime.

The exchange implementation must define:

```text
sign_convention
free_inlet_rule
submerged_inlet_rule
surcharge_rule
opening_area_or_weir_length
discharge_coefficient_source
capacity_cap
wet_dry_threshold
regime_switch_rule
multiple_cell_weighting
anti_oscillation_or_hysteresis_rule
```

### 14.2 Exchange-volume constraint

For every coupling interval:

\[
|Q|\Delta t_c \leq V_{available}
\]

No domain may transfer more water than is available.

Any inlet capacity cap must also be enforced consistently:

\[
|Q| \le Q_{max}
\]

when `maximum_inlet_capacity` is defined.

### 14.3 Time coordination

Track separately:

```text
dt_surface
dt_SWMM_internal
dt_coupling
```

The surface model may subcycle according to its stability timestep.

SWMM may use its internal Dynamic Wave routing timestep.

The two models synchronize at `dt_coupling` boundaries using transferred **volume**, not only instantaneous flow rate.

### 14.4 Coupling sensitivity

In addition to surface-grid and surface-timestep testing, Sequence 14 must test sensitivity to `dt_coupling` and document the selected operational value.

### 14.5 Volume ledger

Every run reports:

```text
initial_surface_volume
initial_drain_volume
rainfall_volume
boundary_inflow
roof_runoff_transfer
surface_to_drain_volume
drain_to_surface_volume
infiltration_or_loss
boundary_outflow
final_surface_volume
final_drain_volume
numerical_residual
relative_mass_error
```

### 14.6 State initialization

Supported initialization modes:

```text
COLD_START
SPINUP_FROM_ANTECEDENT_FORCING
HOTSTART
OBSERVATION_ASSIMILATED
```

For the prototype, prefer `SPINUP_FROM_ANTECEDENT_FORCING` when antecedent forcing is available.

## Acceptance scenario

Artificially reduce one drain's effective capacity and verify:

- increased node head;
- reduced inlet acceptance when appropriate;
- surcharge/reverse exchange;
- transfer of surcharge water to the surface;
- increased surface depth;
- acceptable total mass error;
- qualitatively correct response to a smaller coupling timestep.

## Inherited component acceptance

C1 lagged-head coupling is numerically stable, exchange physics are explicitly implemented, state initialization is reproducible, coupling-step sensitivity is documented, and the complete water-volume ledger closes within a declared tolerance.

## Historical reconstruction and state contract

Implement documented COLD_START, SPINUP_FROM_ANTECEDENT_FORCING and compatible HOTSTART paths.
Implement OBSERVATION_ASSIMILATED through an explicit, bounded observation-to-state update
specified in the initialization mathematics. Define its observation operator, weighting,
uncertainty, freshness, datum checks and nonnegative-storage constraints. Keep an initialization
ledger for added/removed storage and retain pre/post states; the forecast begins from the
resulting accounted state. Do not conceal observation adjustments as rainfall or infiltration.
Exercise the method with controlled observations before real use. Real assimilation is eligible
only with suitable measured observations and remains unavailable otherwise; an enum is not
implementation evidence. Store soil/loss memory, surface/drain/boundary state, valid_at and provenance.

Coordinate consecutive event windows with an exact end-state/start-state handoff. Check
continuity, version compatibility, gap handling, restart equivalence and state age. Observed
event rainfall/boundaries may drive a reconstruction, which is labelled as such and not scored
as an issue-time rainfall forecast.

The exchange specification at docs/mathematics/surface-drain-exchange.md must explain joint
capacity limits across all exchanges sharing a source, including repeated surface-cell/node
bindings. Apply source-volume limits collectively, not independently per connection. Track
internal transfers once on each side, reconcile SWMM external flooding and pumps, and explain
how roof transfers enter the global balance without double-counting external rainfall.

## Visible result

A recorded coupled benchmark shows rising drain head, reduced inlet acceptance, surcharge,
surface water and recovery together with an auditable volume ledger. A real event reconstruction
is displayed only for an eligible twin and adequately sourced state/forcing conditions.

## Completion and freeze gate

The inherited component acceptance, restart/window continuity, aggregate source-volume caps,
bidirectional/multiple-binding tests, observation-update accounting and missing/invalid-observation
rejection pass. All four initialization methods have implementation evidence; real observation
assimilation remains conditional on suitable source data.
Freeze HydraulicsRunRequest, HydraulicState and coupled output contracts. Retain real-pilot
data blockers and separate numerical benchmark evidence from measured flood agreement.

# Sequence 15 — Deterministic Forecasts and Baseline Historical Evaluation

**Release target:** v1.5
**Owners:** forecast-service and evaluation records
**Entry:** Sequence 14 coupled worker, Sequence 11 event/availability manifests and explicit state/forcing coverage.

## Existing implementation modifications

Wrap existing forcing packages in a forecast/evaluation context rather than repurposing their
issue_time. Add exact event, input-availability and model/state references to new forecast
contracts. Keep legacy forcing readers and package identities intact.

## Objective

Generate a deterministic flood forecast from a versioned twin, forcing package, and hydraulic starting state.

## Forecast input contract

```text
twin_id
forcing_package_id
hydraulic_state_id
forecast_horizon
solver_configuration
scenario_id  # optional deterministic scenario
```

## Standard forecast times

```text
NOW
+15 min
+30 min
+45 min
+60 min
+90 min
+120 min
+180 min
```

## FloodCube

Store scientific output as Xarray/Zarr.

Dimensions:

```text
time
y
x
```

Variables:

```text
depth
velocity_x
velocity_y
```

`hazard_class`, `risk_class`, and policy-dependent warnings are not stored as primary hydraulic variables in FloodCube. They are derived by `risk-service`.

Derived fields:

```text
onset_time
peak_depth
peak_time
duration
```

## Probability rule

A deterministic forecast does not contain flood probability.

It may contain:

```text
data_quality
model_readiness
forcing_coverage
limiting_dataset
solver_applicability
```

## Forecast freshness

Every forecast stores:

```text
forecast_id
forecast_type
forecast_stream_id
forecast_issue_time
forcing_package_id
supersedes_forecast_id
status
```

Allowed `forecast_type` values:

```text
OPERATIONAL
SCENARIO
REPLAY
ENSEMBLE_MEMBER
```

Supersession is allowed only inside the same `forecast_stream_id`.

## Road Surface Geometry

Create routing exposure geometry for each road edge using known road width where available, documented assumed widths where required, and vertical-level information for bridge, flyover, tunnel, and underpass segments.

Do not evaluate road flooding using centerline-only x/y intersection when a multi-level road exists.

## RoadFloodState

Project FloodCube values onto each compatible road surface.

Store:

```text
road_edge_id
time
road_level
maximum_depth
p90_depth
mean_depth
flooded_length
flooded_area_fraction
velocity_metric
data_quality
```

## Inherited component acceptance

A reproducible forcing event produces a complete FloodCube, RoadFloodState time series, and correct stream-scoped forecast freshness metadata.

## Forecast purpose and evidence

Keep forecast_type for orchestration (OPERATIONAL / SCENARIO / REPLAY / ENSEMBLE_MEMBER).
Add a separate evaluation_mode: OBSERVED_REPLAY / HYDRAULIC_RECONSTRUCTION /
REANALYSIS_HINDCAST / ISSUE_TIME_BACKTEST / SYNTHETIC_DEMONSTRATION. Validate permitted
combinations; UI purpose, input provenance and scientific claim are not inferred from one enum.

ISSUE_TIME_BACKTEST selects only inputs evidenced as available by the historical issue time,
including rainfall, boundaries, operational controls and initialization observations. A future
measurement cannot enter a predictor or state initializer. Unknown availability prevents a strict
backtest claim; it may permit a labelled retrospective experiment. Reanalysis hindcasts are separate.

Define explicit issue/valid/lead times and output interpolation. Standard display times do not
create new forcing information. Refuse an unsupported 180-minute horizon or publish a declared
shorter supported run. Long replays consist of successive bounded forecasts/reconstructions.
Preserve stream-scoped supersession so replay/scenario jobs cannot displace live products.

## Baseline evaluation before learned-model work

1. Freeze the whole-event TRAIN / TUNE / TEST split and minimum evidence criteria from the inventory.
2. Perform sensitivity/identifiability analysis on development events before hydraulic calibration.
3. Calibrate only identifiable uncertain parameters within documented physical bounds.
4. Produce a new parameter-set version and mandatory new immutable twin after calibration.
5. Compare development/tuning events using recorded rainfall, simple rainfall forecasts and
   externally supplied forecasts where available. Label each forcing experiment.
6. Report mass error, depth/onset/extent metrics where measured labels exist, and data gaps.
7. Lock the deterministic baseline and evaluation protocol for Sequence 16 comparisons.

The final TEST set remains sealed until Sequence 19. Passing numerical tests and development
evaluation makes an engineering reference available; it is not final independent validation.
If real depth/extent evidence is missing, preserve that limitation. Rainfall correction can later
be evaluated against genuine rainfall labels; direct flood-output learning remains blocked.

## Visible result

One versioned forecast or reconstruction can be replayed with depth/time plots, a baseline
comparison, state/forcing coverage and measured observation markers where available.

## Completion and freeze gate

The inherited component acceptance, strict input cutoff/leakage tests, split isolation, state
freshness, no-probability semantics, multi-level road exposure, baseline sensitivity protocol
and reproducible event reports pass. Freeze forecast/evaluation contracts and declare exactly
which development comparisons are supported; never manufacture missing validation labels.

# Sequence 16 — GraphCast, Local Rainfall Fusion and XGBoost

**Release target:** v1.6
**Owners:** isolated weather-model worker, rainfall processing and model/evaluation records
**Entry:** Sequence 15 engineering baseline/protocol, Sequence 11 source contracts, compatible historical data and measured resource envelope.

## Scope and model responsibilities

This sequence makes GraphCast and XGBoost explicit integration deliverables. GraphCast provides
regional atmospheric forecast context; local rainfall processing supplies appropriately supported
forcing; XGBoost learns a defined rainfall correction. The hydraulic model remains the owner of
surface/drain water movement. There is no transformer dependency.

The baseline is pretrained full-resolution GraphCast inference, with model-specific global
inputs and retained training-history metadata. Training GraphCast from scratch or further
fine-tuning it is a separately scoped future experiment, not a hidden prerequisite or a claimed
achievement of this sequence. A small checkpoint may support development, but does not close
the full-resolution integration gate. Running imported archived GraphCast outputs must be
labelled provider-output ingestion and cannot substitute for our required inference receipt.

## Existing implementation modifications

Add versioned ModelArtifact, FeatureDatasetManifest, WeatherRunManifest, TrainingRunManifest,
RainfallFusionManifest and EvaluationReport. Link them to existing Source/processing_lineage
and forcing packages through exact hashes and references. Existing forcing-service accepts
the resulting prepared interval rates; do not embed global model tensors or training arrays
in its bounded JSON RainInput. Pin the model worker dependencies separately from the API.

ModelArtifact records model family/variant, checkpoint/normalization hashes, code/environment
versions, input schema, training and fine-tuning date/catchment coverage, licence evidence,
supported task/horizon, evaluation status and promotion status. Registry labels distinguish
IMPORTED / TRAINED / EVALUATED / REJECTED / SELECTED; creation does not activate a model.

## 16.1 GraphCast execution

1. Select and pin a supported 0.25-degree variant and its documented initialization contract.
   The official variants differ in pressure levels and initialization; do not combine them.
2. Verify global t and t-minus-6-hour atmospheric states, surface/upper-air variables, levels,
   units, grid ordering, normalization and any required target-time forcings.
3. Record a bounded resource assessment before downloading large archives or launching inference:
   hardware, accelerator, memory, disk, runtime and allowed environment. Paid/external execution
   requires its ordinary execution authorization; this roadmap does not purchase compute.
4. Run actual pretrained inference for at least one eligible historical initialization. Retain
   inputs, checkpoint, diagnostics, full output references and a regional extraction receipt.
5. Audit the checkpoint training/fine-tuning cutoff against evaluation events. Holding an event
   out of XGBoost does not make it independent of the pretrained weather model.
6. Keep reanalysis initialization distinguishable from archived issue-time operational inputs.

Use the [official GraphCast variant documentation](https://github.com/google-deepmind/weathernext/blob/main/docs/weathernext1_graph/README.md)
to verify the selected checkpoint contract; pin the revision actually used in the run.

GraphCast predicts in six-hour steps. Its coarse accumulated precipitation cannot supply the
timing of a local ten-minute storm burst. Conversion/disaggregation must be explicitly versioned,
conserve accumulation and carry the original effective temporal/spatial support. Fine-grid
rendering cannot be reported as fine-resolution atmospheric skill.
[GraphCast input/output description](https://deepmind.google/blog/graphcast-ai-model-for-faster-and-more-accurate-global-weather-forecasting/)

## 16.2 Gauge/radar processing and rainfall baseline

Implement numerical source decoding/QC from accepted Sequence 11 samples, radar rainfall
estimation if required, gauge adjustment and a documented short-range nowcasting baseline
where suitable consecutive radar scans exist. Validate each stage separately. Specify scan
geometry, reflectivity/rain units, clutter/missing masks, geolocation, accumulation periods,
station matching, correction windows and the motion/extrapolation method.

Blend toward an available forecast for longer lead times using documented weights and supported
horizons. Uncertainty in coarse GraphCast timing is not removed by blending. Keep an uncorrected
forecast and simple statistical/nowcast baseline as named competitors.

Live polling/recent observations use the same adapter contracts but are conditional on verified
provider access, timestamps and measured latency. If numeric radar or gauges are unavailable,
record that capability as unavailable and evaluate explicitly sourced alternatives. No screenshot
decoder is promoted as numerical radar without its own validated measurement-reconstruction task.

## 16.3 XGBoost training target and dataset

Required first target: rainfall accumulation in millimetres for a stated geographic support,
valid interval and forecast lead. Pair that target with GraphCast/other forecast features,
recent rainfall and any eligible gauge/radar features. Fit feature transforms only on TRAIN.
Record a finite nonnegative output policy and evaluate any clipping or transformations.

For coarse rainfall labels, train/evaluate on their actual support and label the result an
estimate of that product. Local-gauge accuracy requires held-out gauge evidence. Do not
manufacture street-level labels by resampling a coarse field. A missing predictor uses the
declared feature policy; missing labels are not converted into dry cases.

FeatureDatasetManifest records target/feature definitions, source provenance, availability,
aggregation rules, support, missingness, split hash, event geography and model-history exclusion.
Audit all features against historical issue time, including rolling-window boundaries and
revised archive availability. Split whole storms chronologically and reserve geographic holdouts
where transfer is claimed. Define sufficient event diversity before training; one successful
fit or one showcased storm is not evidence of generalization.

Execute a real XGBoost fit on an eligible dataset, store seed/hyperparameters/environment,
checkpoint and evaluation output, and compare with the frozen baseline on TUNE events.
No automatic activation follows training completion. If correction performs worse, keep the
baseline selected and retain the trained model as REJECTED or research-only.

Direct flood-depth/occurrence XGBoost, hydraulic surrogates and GraphCast fine-tuning are optional
future extensions requiring separate targets and evidence. A surrogate trained on simulations
does not establish measured flood accuracy. ML never edits the conservative FloodCube in place.

## 16.4 Integration, verification and visible result

Produce distinct uncorrected, simple-corrected and XGBoost-corrected forcing packages and run
the same eligible hydraulic configuration for comparisons. Evaluate rainfall accumulation,
bias, intense-event timing/detection, coverage and runtime; evaluate flood quantities only
where observations support them. The final independent TEST set remains sealed.

Required failures: mismatched checkpoint/variables/levels, corrupt model, absent feature,
availability leakage, base-model training overlap, negative/nonfinite rates, wrong accumulation
units, temporal extension, provider outage, accelerator absence and interrupted/retried training.
Training and inference are cancellable/idempotent jobs; the UI shows actual job state.

Visible result: genuine saved GraphCast output, a reproducible XGBoost training receipt, rainfall
comparison charts and traceable downstream flood runs where supported. Clearly show input
support, selected baseline/model and why a candidate was retained or rejected.

## Completion and freeze gate

All four subparts must have explicit results. Required: a real full-resolution GraphCast
inference receipt, a real eligible XGBoost fit/evaluation, end-to-end prepared-forcing integration,
compatibility/leakage tests and baseline comparisons. Numerical gauge/radar/live capabilities
are reported separately and may remain unavailable; they are never claimed from fixture tests.
Missing mandatory data/compute leaves this sequence NOT_FROZEN with a named blocker, even if
adapter/unit tests pass. Positive model improvement is a selection condition, not a fabricated
gate result. No operational accuracy or calibrated probability is claimed before Sequence 19.

# Sequence 17 — Risk, Engineering Scenarios and Time-Dependent Routing

**Release target:** v1.7
**Owners:** risk-service and routing-service
**Entry:** Sequence 15 forecast/exposure contracts and Sequence 16 integration results; active forecast source is explicitly selected.

## Existing implementation modifications

Add derived risk/route products referencing immutable forecasts and policies. Preserve deterministic
FloodCube variables. Introduce no hazard weights into the hydraulic solver or static source geometry.

## Scope and completion rule

Both subparts below are required and have separate verification receipts. Ensemble calculations
require a declared ensemble; a deterministic fallback remains available. Learned rainfall intervals
or arbitrary engineering cases are not automatically spatial-temporal ensemble members.

## 17.A Ensemble risk and engineering scenarios

### Risk objective

Add uncertainty and decision support without mixing statistical probability with manually selected engineering scenarios.

## Ensemble execution ownership

`risk-service` owns EnsembleDefinition, uncertainty model selection, member list/version, aggregation of completed members, and probability/decision products.

`forecast-service` submits each required ensemble-member forecast, and `hydraulics-worker` executes numerical member runs.

## Branch A — Probabilistic ensemble

Valid sources may include meteorological ensemble members, statistically defined parameter uncertainty after calibration, and statistically defined capacity uncertainty.

For an ensemble of `N` members, the raw exceedance estimator is:

\[
\hat p(h>h_c)=\frac{N_{exceed}}{N}
\]

Before reliability/calibration evidence exists, publish this primarily as:

```text
ensemble_exceedance_fraction
probability_status = PROVISIONAL
```

Only after Sequence 19 establishes a defensible probabilistic validation framework may the product be promoted to a calibrated/validated probability label where justified.

## Branch B — Engineering scenario sensitivity

Examples:

- 20% blockage;
- 50% blockage;
- pump unavailable;
- cleaned drain;
- high downstream stage;
- alternative assumed roughness.

These outputs are labeled scenario comparisons, not probabilities.

## Hazard and Road Risk Classification

`risk-service` derives configurable hazard/risk classes from FloodCube and RoadFloodState and publishes versioned `RoadRiskState` products.

## Decision outputs

- road severity;
- critical drain ranking;
- capacity utilization;
- drain-cleaning priority;
- pump criticality;
- critical-infrastructure exposure;
- onset and peak warnings;
- before/after intervention comparison.

## Inherited component acceptance

The system clearly separates deterministic forecast, ensemble exceedance, validated/provisional probability status, engineering scenarios, data confidence, and model readiness.

## 17.B Time-dependent routing

### Routing objective

Calculate lower-risk routes using flood conditions expected while a vehicle traverses each road segment.

## Inputs

```text
Road graph
RoadFloodState
RoadRiskState  # when available
origin
destination
departure_time
vehicle_profile
hazard_thresholds
forecast_id
```

## Prototype travel-time baseline

Calculate baseline edge travel time from OSM-derived road attributes and documented free-flow/default speeds.

If a road lacks a usable speed attribute, apply a road-class default marked `ASSUMED`.

## Vehicle profiles

```text
CAR
BUS
AMBULANCE
FIRE_SERVICE
MUNICIPAL_EMERGENCY
```

Thresholds are configurable and must not be presented as universal safety limits unless supplied by an appropriate authority.

## Routing algorithm requirement

The baseline SIH implementation should use a **time-expanded graph** over forecast intervals, or another rigorously documented FIFO-safe time-dependent algorithm.

A generic static Dijkstra/A* implementation with one flood weight for the entire trip is not acceptable.

For each edge, define entry and exit times:

\[
t_{exit}=t_{enter}+TravelTime_e(t_{enter})
\]

Flood exposure must be evaluated over the traversal interval rather than at one instant only. A conservative baseline is:

\[
Exposure_e = \max_{\tau\in[t_{enter},t_{exit}]} Hazard_e(\tau)
\]

An alternative time-integrated exposure metric may be used if documented and tested.

Edges may become unavailable when configured hazard rules are exceeded.

## Cost concept

\[
Cost_e = TravelTime_e + \lambda \cdot ExposurePenalty_e
\]

where `ExposurePenalty_e` is computed from time-dependent flood state over traversal.

## Output wording

Preferred:

```text
Lower-Risk Recommended Route
Predicted Flood Exposure: LOW/MEDIUM/HIGH
Forecast Confidence: ...
```

Do not claim a guaranteed safe route.

## Required test

A road is dry when the trip departs but becomes hazardous before the vehicle would finish traversing it. The router must choose a lower-risk alternative when one exists.

## Inherited component acceptance

The routing engine demonstrates genuinely time-dependent diversion and lower predicted flood exposure than the static shortest route for at least one controlled scenario.

## Additional verification and visible result

Define the policy for missing/failed ensemble members, member weights and spatial-temporal
coherence; report the actual denominator and retained-member set. Do not present arbitrary
independent pixel quantiles as coherent flood-event samples.

Test route traversal beyond forecast coverage, stale/superseded forecasts, disconnected/no-route
cases, unsafe waiting locations if waiting is allowed, multi-level geometry and unavailable risk
products. Unsupported future segments must not be assumed dry. Every scenario must execute a
real model run or load an exactly matching recorded run; a slider cannot cosmetically alter depth.

Visible result: baseline/intervention comparison plus a trip whose route changes because an edge
floods during traversal. Show forecast identity, departure time, assumptions and coverage.

## Completion and freeze gate

Both inherited component acceptances, missing-member/coverage policies and route failure tests
pass. Freeze EnsembleDefinition, scenario comparison, RoadRiskState and route contracts. Retain
PROVISIONAL probability status until supported by Sequence 19 independent reliability evidence.

# Sequence 18 — Historical Replay and Forecast Comparison Dashboard

**Release target:** v1.8
**Owners:** geospatial-service and web
**Entry:** Sequence 11 preview/event contracts and actual Sequence 15-17 output products.

## Existing implementation modifications

Extend the small rainfall preview into the full browser workflow. Add tile/COG/vector/3D
publication and comparison read APIs referencing immutable scientific artifacts. Keep existing
artifact APIs usable; do not make the browser download global weather fields or full training sets.

## Objective

Expose the already functioning engineering workflow through a complete browser interface.

## 2D operational view

Use MapLibre for rainfall, flood depth, hazard, road exposure, wards/catchments, critical infrastructure, risk, and routing.

## 3D digital twin

Use CesiumJS for terrain, buildings, drainage, pumps, outfalls, rivers/canals, flood surfaces, and underground inspection.

## Publication pipeline

```text
FloodCube / RoadFloodState / RoadRiskState / geometry
↓
geospatial-service
↓
COG / raster tiles / vector tiles / 3D publication assets
↓
MapLibre / Cesium
```

The browser must not directly load large raw scientific Zarr datasets as its primary rendering method.

## Required modes

```text
CITY
DRAINAGE
TERRAIN
RAINFALL
FLOOD
DECISION
ROUTING
```

## Time control

```text
NOW
+15
+30
+45
+60
+90
+120
+180
```

## Inspector

Display only information supported by the active forecast, including deterministic depth, onset, peak, velocity, risk classification when available, drain node state, utilization, surcharge, ensemble/probability status where valid, data quality, model readiness, forcing coverage, solver applicability, and limiting dataset.

## Inherited component acceptance

A user can execute and inspect the entire approved demo workflow through the browser without manually running backend scripts.

## User flow

1. Select an event or current forecast stream. Immediately show date, catchment, mode and coverage.
2. Inspect the 2D catchment map and choose rainfall, terrain, drainage, flood, decision or routing.
3. Play/pause/scrub the event timeline. Map layers, charts and selected-site traces share one clock.
4. Select a historical forecast issue time, then compare the saved forecast with later observations.
5. Compare baseline, simple correction and XGBoost correction using the same event, support,
   hydraulic configuration, units and legend range.
6. Inspect a measurement marker or road/drain asset to see supported values, uncertainty and sources.
7. Switch to 3D without losing event, valid time, selected location or comparison mode.
8. Explicitly request an allowed forecast/scenario job, observe progress/cancellation/failure,
   and inspect completed results. Navigation, playback and selection never start training.

## Detailed interaction contract

| Control | Action | Missing or pending state |
|---|---|---|
| Event selector | Load a versioned event package and supported assets | Explain missing event files and permit available layers |
| Mode selector | Choose observed replay, reconstruction, hindcast, backtest or live view | Show input provenance and eligibility; never relabel cached replay as live |
| Timeline/speed | Change presentation time only | Mark gaps and actual stored timestamps |
| Issue-time selector | Select a forecast run while keeping valid time separate | Display missing horizon/initial-state support |
| Layer toggles | Show corresponding recorded quantity with legend | Explain unsupported depth/radar/probability layers |
| Compare | Synchronize baseline/model and observation panels | Never fill absent observations with model values |
| Site/asset inspector | Show traces and exact product lineage | Display missing labels or datum incompatibility |
| Run scenario/forecast | Submit the explicit documented job | Show queued/running/failed/cancelled states; no fake progress |
| 2D/3D | Change presentation using the same scientific outputs | Fall back to 2D when 3D assets are unavailable |
| Model results | Inspect training/evaluation and selection status | Do not imply a saved model is selected or operational |
| Export/recorded demo | Package permitted assets and exact run references | Report unavailable redistribution/offline assets |

## Visual design

Use a clear map-led layout, restrained basemap, readable text and accessible colour scales.
Keep rainfall, water depth, hazard and confidence visually distinct. Legends carry units and a
consistent comparison scale. Use smooth camera transitions, responsive controls and restrained
animation. A fixed issue-time marker and moving valid-time marker explain forecast lead.

Show measured observation markers separately from a modelled flood surface. Flow arrows require
actual velocity outputs. Display interpolation between stored frames as presentation; it does
not create new observations or finer information. Label vertical exaggeration in 3D. Rainfall
accumulation is never displayed as standing flood depth.

Keep scientific lineage and detailed diagnostics available in an inspector without making
implementation details part of the normal user journey. Display concise limitations that affect
interpretation: source age, missing coverage, provisional probability and unsupported horizon.

## Replay package and offline behavior

Define ReplayManifest with historical_event_id, exact run/model/forecast IDs, available time
frames, layer asset hashes, chart references, observation coverage and redistribution terms.
Precompute genuine model runs and display assets for a dependable demo and label them recorded.
Retain permitted local basemap assets or use a local background for offline presentation.
Demonstrate cached playback without provider access. A missing basemap cannot erase the science.

## Verification and completion gate

The inherited dashboard acceptance plus Playwright/browser checks pass for synchronized time,
layer units, shared legends, observation separation, no automatic job starts, asynchronous jobs,
no-data/outage states, accessibility/keyboard controls, responsive layout and offline replay.
Visually inspect captured 2D and 3D screens using actual available products. UI fixtures are
clearly labelled and excluded from scientific metrics. Freeze publication and ReplayManifest
interfaces. An attractive screen alone cannot close missing model/data gates.

# Sequence 19 — Independent Validation, Catchment Scaling and Performance

**Release target:** v1.9
**Owners:** evaluation, hydraulics, forecast, risk, routing and platform performance
**Entry:** frozen Sequence 15 baseline, Sequence 16 candidates, Sequence 17/18 products and a sealed independent TEST set.

## Existing implementation modifications

Feed evidenced corrections through the original registry/geometry/parameter owners, create new
versions/twins and repeat affected downstream checks. Do not modify old calibration or test
outputs in place. This sequence audits final integrated claims, not only the latest ML component.

## Validation staging

Sequence 15 already owns development sensitivity/calibration; Sequence 16 owns learned-model
training and tuning. The detailed requirements below apply to their final audit and any
documented development-data refit. Freeze all models, features, thresholds and policies before
opening TEST results. Any subsequent tuning consumes that test set as development evidence
and requires a fresh independent test. A demonstration event is not automatically test evidence.

## Objective

Calibrate only identifiable parameters, rebuild approved parameter/twin versions, and validate the integrated system using independent events.

## 19.1 Parameter sensitivity and identifiability

Before calibration:

1. perform sensitivity analysis;
2. identify parameters to which selected observations are meaningfully sensitive;
3. exclude parameters that cannot be identified defensibly from available observations;
4. define physical/calibration bounds.

Potential calibratable parameters include:

- effective drain capacity;
- surface roughness;
- conduit roughness where uncertain;
- inlet discharge coefficient;
- inlet/weir capacity parameters;
- infiltration/loss parameters;
- selected exchange parameters where observations support identifiability.

Geometry must not be arbitrarily distorted merely to force agreement with observations.

## 19.2 Calibration/validation event separation

Where data permit:

```text
Event A → Calibration
Event B → Independent validation
Event C → Optional independent test
```

The same event must not be used as both calibration and validation evidence.

## 19.3 Version feedback loop

```text
Sensitivity analysis
↓
Calibration on Event A
↓
New calibrated parameter-set version
↓
Mandatory new immutable twin version
↓
Re-run deterministic forecast
↓
Re-run probabilistic ensemble where applicable
↓
Validate against Event B
```

## 19.4 Drain-reconstruction validation

Evaluate positional error, precision, recall, topology/connectivity accuracy, and attribute accuracy.

## 19.5 Terrain validation

Evaluate CRS/vertical-reference correctness, control points where available, depression preservation, known resolution limitations, road-sag/underpass representation, and consistency with drainage rim/invert data where available.

## 19.6 Meteorological validation

If the platform generates its own rainfall nowcast, evaluate appropriate metrics such as MAE, RMSE, bias, CSI, FSS, and Brier score/reliability/CRPS where probabilistic outputs are used.

If rainfall forecasts are externally supplied, record that generation is outside the platform and compare forecast rainfall with observations where feasible.

## 19.7 Surface hydraulic validation

Evaluate benchmark behavior, mass conservation, grid convergence, timestep convergence, and applicability diagnostics.

## 19.8 Drainage validation

Evaluate generated SWMM model fidelity, drainage mass balance, surcharge timing, reverse-flow behavior, and downstream-stage response.

## 19.9 Coupled-flood validation

Where reliable observations exist, evaluate flood/no-flood agreement, inundation overlap, depth error, onset-time error, peak-time error, exchange/coupling sensitivity, and total mass balance.

## 19.10 Routing validation

Compare static shortest route, time-dependent flood-aware route, and predicted flood exposure during edge traversal.

## 19.11 Probabilistic validation

Where probability products are claimed, evaluate reliability/calibration and appropriate probabilistic scores. Until this evidence exists, retain `PROVISIONAL` status.

## 19.12 Reproducibility

Every scientific run stores:

```text
twin_id
forcing_package_id
hydraulic_state_id
scenario_id
parameter_set_version
software_version
solver_configuration
random_seed_if_used
result_checksum
```

## Inherited component acceptance

Every major SIH claim has an independent evidence assessment and an explicit support/limitation
status. Listing a limitation does not satisfy a mandatory measured-evidence requirement in the
containing sequence's completion gate.

## 19.13 Learned-model and historical-availability audit

Evaluate the selected baseline, simple correction and XGBoost pipeline on the same independent
events, including rain and dry cases and severe events represented in the dataset. Audit
GraphCast checkpoint training overlap, feature transforms and all issue-time inputs. Report
reanalysis hindcast, strict backtest and hydraulic reconstruction results separately.

Report event counts, spatial/temporal support, missing labels, model-selection history and
uncertainty on aggregate results where defensible. Include rainfall MAE/RMSE/bias, CSI/FSS at
declared thresholds/scales, intense-event timing, flood-depth/onset/extent metrics where observed,
and Brier/reliability/CRPS or interval coverage only for appropriate probability products.

A model can be implemented and independently evaluated yet remain unselected because it does
not improve the baseline. Publish that outcome. No promised accuracy percentage is a completion
criterion. Measured flood validation cannot be closed using only simulated labels.

## 19.14 Connected-catchment scaling

### Scaling objective

Scale the component-tested workflow from a small pilot to one connected Kolkata drainage catchment and verify the forecast can complete within the operational update cycle.

## Scaling order

```text
Synthetic block
→ One ward
→ Two connected wards
→ Several connected wards
→ Complete drainage catchment
→ Multiple catchments
→ Citywide visual twin
```

## Kolkata downstream-boundary scope

For the first prototype:

- represent the Hooghly primarily as a downstream hydraulic boundary series;
- represent relevant local canals/open channels in the appropriate 1D or 2D hydraulic domain;
- do not automatically expand the street-scale 2D solver to the full river domain.

## Performance metadata

Record:

```text
hardware
surface_cell_count
drain_node_count
drain_edge_count
forecast_horizon
ensemble_size
runtime
peak_memory
RainCube_size
FloodCube_size
```

## Operational runtime rule

\[
T_{forecast}<T_{forcing-update}
\]

The declared operational configuration must complete before the next expected forcing update on declared reference hardware.

## Inherited component acceptance

At least one connected Kolkata drainage catchment runs end-to-end within the declared runtime and memory envelope.

## End-to-end runtime and resource budget

Extend the inherited performance metadata with source observation age, ingest/QC latency,
GraphCast runtime, feature/fusion runtime, hydraulic runtime, ensemble cost, publication delay,
browser playback latency, cold start, queue delay and peak memory/disk. Pin reference hardware.
Measure both recorded-demo playback and recomputation; a cached animation is not a forecast
runtime benchmark. Test the same accepted model configurations at each supported scale.

For a live claim, the entire required pipeline must satisfy the declared update/latency budget.
If it cannot, retain replay/research availability and mark the live configuration unsupported.
Benchmark actual GraphCast resources rather than assuming every laptop supports full inference.

Before claiming operational forecast performance, run prospective shadow forecasts with actual
incoming source delays and unchanged model/decision policies. Retain failures, missed updates
and subsequent observations alongside successful events. Historical hindcast skill and cached
playback are not substitutes for this live-path evidence. Public warning/release authority
remains governed by the final supported scope and acceptance record.

## Visible result

A complete validation report and model comparison tied to the displayed events, plus one
connected Kolkata catchment benchmark with declared hardware, runtime and scientific scope.

## Completion and freeze gate

Both inherited validation/scaling acceptances and the learned-model/availability audit pass for
the declared scope. At least one eligible connected real catchment and independent measured
flood evidence are required for a validated flood-prediction claim. Missing mandatory evidence
leaves that acceptance NOT_FROZEN; a report listing limitations does not waive it.

Maintain a claim matrix: IMPLEMENTED, ENGINEERING_VERIFIED, INDEPENDENTLY_EVALUATED,
SUPPORTED_FOR_DECLARED_SCOPE, BLOCKED or UNSUPPORTED, with report references. Probability
promotion is scoped to validated products. Human-only engineering acceptance remains pending
Sequence 20 under the existing review policy; technical validation cannot impersonate it.

# Sequence 20 — Resilience, Reproducible Demo and Final Acceptance

**Release target:** v2.0
**Owners:** platform/package maintainers and existing final review process
**Entry:** Sequence 19 claim/evidence matrix, prior engineering gates and exact candidate artifacts.

## Existing implementation modifications

Complete additive migrations, legacy reader checks, backup/restore and deployment documentation
for the full application. Preserve existing reference packages and historical gate reports.
Re-run affected predecessor gates after all evidence-backed corrections.

## Objective

Create a reproducible, recoverable, and demonstrable final prototype.

## Failure tests

Test at least:

- external source unavailable;
- source timeout;
- corrupt GIS file;
- missing drainage map;
- incomplete hydraulic parameters;
- rainfall feed unavailable;
- incomplete forcing horizon;
- object-store restart;
- optional NATS/Redis restart when enabled;
- PostgreSQL restart;
- worker crash;
- solver timeout;
- duplicate event delivery;
- unavailable terrain publication layer.

## Required behavior

- retry/backoff where appropriate;
- idempotent processing;
- dead-letter handling where messaging is enabled;
- job recovery policy;
- cached-twin fallback;
- explicit degraded-mode status;
- forecast freshness protection;
- no silent replacement of missing scientific data.

## Degraded mode

If live data are unavailable:

- cached digital twins remain inspectable;
- historical replay remains available;
- synthetic scenarios remain available;
- previous forecast products remain inspectable;
- the UI explicitly marks live operation as unavailable or degraded.

## Final package

Include:

- Docker Compose;
- environment template;
- dependency lock;
- database migrations;
- seed/demo data;
- replay/synthetic forcing package;
- one-command startup;
- local verification command;
- OpenAPI documentation;
- architecture documentation;
- Surface Solver Mathematical Specification;
- 1D–2D Exchange Mathematical Specification;
- validation report;
- known limitations;
- backup/restore instructions.

## Checkpoint D release target

**Final Validated SIH Release**, only after the complete technical, measured-evidence and human
acceptance gate below passes.

## Inherited component acceptance

A documented clean environment can start the platform and execute the selected Kolkata end-to-end demonstration without manual backend repair.

## Additional model/data/demo failure cases

Test expired credentials, partial historical downloads, changed provider schema, revised source
files, missing model/checkpoint/normalization assets, model corruption, incompatible feature
schema, missing accelerator, training/inference cancellation, failed ensemble members, event
availability gaps, incompatible hotstart and missing offline chart/tile assets.

Retry only idempotent work; never publish partial model/forecast outputs as complete. Preserve
the selected deterministic baseline when an optional correction cannot run, with an explicit
new run identity and source-selection record. Never silently swap models inside a saved run.

## Final demonstration

Package one repeatable historical event, the comparison outputs actually produced, scientific
and browser-ready assets, source/model licences, model cards, dependency locks, run manifests,
database migrations, backup/restore instructions and a clean-machine walkthrough.

The walkthrough shows rainfall development, forecast issue/valid time, simulated flooding,
available measured comparisons, model performance, scenario/routing behavior and 2D/3D playback.
Clearly label recorded results. Live demonstration is conditional on verified feeds and runtime;
the offline historical path remains usable without claiming it is a live forecast.

## Human acceptance and release labels

Complete the existing human-only review register with real reviewer evidence; do not fabricate
sign-offs or infer them from this planning authorization. DATA-08-01 and inherited scientific
blockers must be resolved through their owning gates. Technical acceptance, human acceptance,
local checkpoint, hosted deployment and final release are separate records.

An engineering/research demonstration may be packaged with explicit limitations, but cannot be
labelled a Final Validated SIH Release while required independent evidence, real-catchment
readiness or final review is missing. Do not silently reduce required GraphCast/XGBoost execution
to placeholders. Any reduced scope needs an explicit revised claim and roadmap disposition.

## Completion and freeze gate

The inherited clean-environment gate, offline replay, model/data failure recovery, backward
compatibility and final claim/review checks pass. Each advertised capability has a matching
evidence receipt. Freeze the actual released interfaces and record exact code/lock/model/data
versions; this plan's frozen status alone never establishes software or scientific completion.

# 13. Project Checkpoints

| Checkpoint | R2 location | Required outcome |
|---|---|---|
| A | After Sequence 9 | Eligible versioned real digital twin, including the original cross-ward requirement; currently blocked by DATA-08-01 |
| A-data | After Sequence 11 | Compatible historical event/observation records, genuine rainfall replay and a bounded data preview |
| B | After Sequence 15 | Conservative coupled deterministic forecast, initialized state, exposure/freshness and development baseline evaluation |
| B-model | After Sequence 16 | Actual GraphCast inference and XGBoost training/evaluation integrated through versioned forcing |
| C | After Sequence 18 | Risk/scenario/routing workflow and complete 2D/3D historical/live-capable comparison viewer |
| C-validation | After Sequence 19 | Independent claim audit and connected-catchment performance evidence |
| D | After Sequence 20 | Reproducible package, resilience, required real evidence and final human acceptance |

These are readiness checkpoints, not automatic release labels. A-data can demonstrate rainfall
while A remains blocked; it cannot promote that twin to hydraulic readiness. All required
dependencies must pass before a later capability is declared complete.

# 14. Development Priority and Scope Control

The next work order is Sequence 11, then 12 through 20. Finish the active sequence's mandatory
contracts/tests before starting a dependent sequence. Inspection and acquisition of needed
inputs may occur as prerequisites; they do not count as later model/feature implementation.

1. Preserve existing products and resolve real-pilot evidence; establish event/availability data.
2. Complete the surface, drainage, coupling and deterministic development reference (12-15).
3. Execute and evaluate the specified weather/learned integration (16).
4. Add risk/routing and the polished replay workflow (17-18).
5. Independently validate, measure connected-catchment performance and package acceptance (19-20).

Validation planning starts in 11, numerical validation occurs in every solver sequence,
development sensitivity/calibration occurs in 15 and final independent evaluation occurs in 19.
Neither data acquisition nor scientific verification is postponed until presentation work.

# 15. Scope Reduction Rule

Reduce geographic extent and supported optional feeds first. Preserve conservation, vertical
references, source truth, time availability, state initialization, independent evaluation and
honest labels. Do not turn arbitrary scenarios into probabilities, use a static route while
claiming time dependence, infer road-level flooding from incompatible surfaces, or present
resampled sources as finer measurements.

The ten sequences are fixed work packages, not a promise of equal duration. Sequences 16, 17
and 19 have explicit subgates because they combine related work. Splitting execution into
smaller tasks is allowed; skipping a mandatory subgate is not.

Full GraphCast retraining, transformer development, direct learned flood-depth replacement,
citywide hydraulic simulation and unsupported live-feed guarantees are outside this revision.
The required pretrained GraphCast and XGBoost rainfall integration remains in Sequence 16.

Preferred final claim, only after matching evidence and review:

> A scientifically validated end-to-end urban flood digital twin demonstrated on one connected
> Kolkata drainage catchment, with independently evaluated rainfall modelling and reproducible
> historical replay, designed for extension to larger city areas.

# 16. Final End-to-End Architecture

~~~text
Permitted urban / atmospheric / rainfall / flood-observation sources
                          |
             Registry + immutable raw vault
                          |
       Spatial/vertical/time/QC normalization
          |               |                      |
   Versioned twin   Historical event +      Global model inputs
   and parameters   availability manifests         |
          |               |                Pinned GraphCast run
          |       Gauge/radar/satellite             |
          |       rainfall preparation <-----------+
          |               |
          |       Baseline / simple correction / trained XGBoost
          |               |
          |       Versioned ForcingPackage + run lineage
          +---------------+
                          |
           State initialization / compatible hotstart
                          |
        One hydraulics worker: 2D + SWMM DYNWAVE
        + bidirectional exchange + time/volume ledger
                          |
          FloodCube + RoadFloodState + freshness
                |                         |
       Risk / scenarios / routing   Independent comparison
                |                   with held-out observations
                +-------------------------+
                          |
        Versioned publication and replay assets
                          |
       Synchronized 2D/3D map, timeline and charts
~~~

Training reads only its permitted dataset splits. Independent observations enter evaluation,
not a predictor's future inputs. Historical manifests reference products; they do not duplicate
ownership of raw data, forcing, hydraulic state or scientific outputs.

# 17. Final Engineering Principle

Build traceable inputs and a conservative reference, define independent evaluation before model
selection, and make the prototype explain actual recorded computations. Maintain numerical,
data, operational, visual and human-acceptance evidence as separate facts. A readable animation
and a successful model fit are useful deliverables; neither substitutes for measured flood skill.

# 18. External Source References for This Revision

These documents inform the integration design; they do not prove access to a Kolkata feed or
successful local execution. Verify product versions, access and schemas when implementing.

- GraphCast variants and pretrained checkpoints: [official model documentation](https://github.com/google-deepmind/weathernext/blob/main/docs/weathernext1_graph/README.md).
- GraphCast temporal/global input context: [DeepMind model description](https://deepmind.google/blog/graphcast-ai-model-for-faster-and-more-accurate-global-weather-forecasting/).
- ERA5 retrospective atmospheric data: [Copernicus catalogue](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=overview).
- IMERG product support and latency: [NASA technical documentation](https://gpm.nasa.gov/resources/documents/imerg-v07-technical-documentation).
- IMD observations and product discovery: [official API reference](https://api.imd.gov.in/public/api_reference.html).
- Numerical radar request route: [IMD radar data request guide](https://radarapi.imd.gov.in/Received_data/dsp_userguide.pdf).
- MOSDAC programmatic archive access: [official download manual](https://mosdac.gov.in/downloadapi-manual).
