# Urban Flood Digital Twin & 0–3 Hour Nowcasting Platform
## Authoritative 20-Sequence Development Specification — Scientifically Revised

**Primary demonstrator:** Kolkata, West Bengal, India  
**Target:** Smart India Hackathon (SIH) 2026 — Urban Flood Nowcasting  
**Primary language:** Python 3.12.x  
**Architecture:** API-oriented modular platform with explicit domain boundaries and one in-process coupled hydraulics worker  
**Development rule:** Build, validate, freeze, then proceed to the next sequence.  
**Revision status:** Scientific audit incorporated; this file is the authoritative implementation specification.

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

## 3.7 AI/ML — post-validation extension, not a baseline SIH dependency

- PyTorch
- PyTorch Geometric
- scikit-learn

The baseline 20-sequence prototype does not require ML to produce a valid flood forecast. ML/GNN work begins only after Sequence 19 has produced a validated deterministic reference model and reproducible simulation dataset.

## 3.8 Messaging, cache, and storage

Target architecture:

- NATS + JetStream
- Redis
- MinIO
- PostgreSQL/PostGIS

These are not all required on day one. Scientific correctness takes precedence over service decomposition.

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

The following identifiers are defined from Sequence 1 and must remain stable:

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

# Sequence 11 — Baseline 2D Surface Hydraulic Solver and Numerical Grid

**Release target:** v1.1  
**Logical component inside:** `hydraulics-worker`

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

## Completion gate

The baseline local-inertial surface solver passes declared benchmark and conservation tolerances, limitations are explicit, and every active surface-drain exchange geometry is bound to the numerical grid.

---

# Sequence 12 — SWMM-Backed Drainage Hydraulic Engine

**Release target:** v1.2  
**Logical component inside:** `hydraulics-worker`

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
4. Surface/drain transfer is controlled by the explicit exchange module in Sequence 13.
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

## Completion gate

The generated SWMM model reproduces trusted SWMM reference behavior and reports acceptable drainage mass balance.

---

# Sequence 13 — Coupled Hydraulics, State Initialization, Time Synchronization and Volume Accounting

**Release target:** v1.3  
**Deployable unit:** `hydraulics-worker`

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

### 13.1 Bidirectional exchange law

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

### 13.2 Exchange-volume constraint

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

### 13.3 Time coordination

Track separately:

```text
dt_surface
dt_SWMM_internal
dt_coupling
```

The surface model may subcycle according to its stability timestep.

SWMM may use its internal Dynamic Wave routing timestep.

The two models synchronize at `dt_coupling` boundaries using transferred **volume**, not only instantaneous flow rate.

### 13.4 Coupling sensitivity

In addition to surface-grid and surface-timestep testing, Sequence 13 must test sensitivity to `dt_coupling` and document the selected operational value.

### 13.5 Volume ledger

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

### 13.6 State initialization

Supported modes:

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

## Completion gate

C1 lagged-head coupling is numerically stable, exchange physics are explicitly implemented, state initialization is reproducible, coupling-step sensitivity is documented, and the complete water-volume ledger closes within a declared tolerance.

---

# Sequence 14 — Deterministic 0–3 Hour Flood Forecast, Forecast Freshness and Road Exposure Projection

**Release target:** v1.4  
**Logical unit:** `forecast-service`

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

## Completion gate

A reproducible forcing event produces a complete FloodCube, RoadFloodState time series, and correct stream-scoped forecast freshness metadata.

---

# Sequence 15 — Ensemble Probability, Scenario Sensitivity and Decision Intelligence

**Release target:** v1.5  
**Logical unit:** `risk-service`

## Objective

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

## Completion gate

The system clearly separates deterministic forecast, ensemble exceedance, validated/provisional probability status, engineering scenarios, data confidence, and model readiness.

---

# Sequence 16 — Time-Dependent Flood-Aware Routing

**Release target:** v1.6  
**Logical unit:** `routing-service`

## Objective

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

## Completion gate

The routing engine demonstrates genuinely time-dependent diversion and lower predicted flood exposure than the static shortest route for at least one controlled scenario.

---

# Sequence 17 — Full 2D/3D Operational Dashboard

**Release target:** v1.7  
**Logical units:** `geospatial-service` + `web`

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

## Completion gate

A user can execute and inspect the entire approved demo workflow through the browser without manually running backend scripts.

---

# Sequence 18 — Connected-Catchment Scaling and Performance Engineering

**Release target:** v1.8

## Objective

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

## Completion gate

At least one connected Kolkata drainage catchment runs end-to-end within the declared runtime and memory envelope.

---

# Sequence 19 — Sensitivity, Calibration, Independent Validation and Reproducibility

**Release target:** v1.9

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

## Completion gate

Every major SIH claim is supported by independent validation evidence or is explicitly labelled as a prototype limitation.

---

# Sequence 20 — Resilience, Packaging and Final SIH Release

**Release target:** v2.0

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

## Checkpoint D

**Final Validated SIH Release**

## Completion gate

A documented clean environment can start the platform and execute the selected Kolkata end-to-end demonstration without manual backend repair.

---

# 13. Project Checkpoints

## Checkpoint A — After Sequence 9

**Versioned Digital Twin Ready**

Must include normalized city data, visual/hydraulic terrain, visual/hydraulic city representations, cross-ward drainage graph, hydraulic parameter readiness, Roof Runoff Receiving Geometry, Exchange Geometry, and immutable twin manifest.

## Checkpoint B — After Sequence 14

**Deterministic Coupled Flood Forecast Ready**

Must include ForcingPackage, HydraulicState, local-inertial 2D surface solver, SWMM Dynamic Wave drainage hydraulics, ExchangeBinding, Roof Runoff Grid Binding, C1 lagged-head coupling, explicit bidirectional exchange physics, volume ledger, FloodCube, RoadFloodState, and forecast freshness control.

## Checkpoint C — After Sequence 17

**Feature-Complete SIH Prototype**

Must include deterministic forecast, provisional/validated ensemble risk where supported, engineering scenario analysis, decision intelligence, time-dependent flood-aware routing, and complete 2D/3D dashboard.

## Checkpoint D — After Sequence 20

**Final Validated SIH Release**

Must additionally include connected-catchment scaling, runtime benchmarks, sensitivity analysis, calibration and independent validation, meteorological validation where applicable, reproducible packaging, and resilience/degraded-mode behavior.

---

# 14. Development Priority if Time Becomes Limited

## Priority 1 — Sequences 1–14

These create the core scientific product:

```text
Data
→ Digital Twin
→ Dynamic Forcing
→ State Initialization
→ 2D Surface Hydraulics
↕
1D SWMM Dynamic Wave Drainage
→ Deterministic Flood Forecast
→ Road Exposure
```

## Priority 2 — Sequences 15–17

These add uncertainty/risk, scenario analysis, decision support, routing, and polished visualization.

## Priority 3 — Sequences 18–20

These add catchment-scale performance, calibration, independent validation, operational resilience, and final packaging.

---

# 15. Scope Reduction Rule

If the project becomes too large, reduce geographic extent first.

Do not respond to schedule pressure by:

- removing conservation tests;
- skipping drainage validation;
- inventing missing engineering values;
- presenting computational resolution as source-data resolution;
- turning arbitrary scenarios into probability;
- claiming guaranteed route safety;
- claiming citywide centimetre-level accuracy without supporting data;
- replacing the declared exchange physics with an undocumented shortcut;
- replacing Dynamic Wave with a routing mode unable to represent the claimed sewer behavior.

Preferred final claim:

> **A scientifically validated end-to-end urban flood digital twin demonstrated on one connected Kolkata drainage catchment, with architecture designed for extension to larger city areas.**

---

# 16. Final End-to-End Architecture

```text
DATA SOURCES
    ↓
Data Source Registry
    ↓
Automatic Harvester
    ↓
Immutable Raw Data Vault
    ↓
Spatial + Vertical Harmonization
    ↓
 ┌─────────────────────┬─────────────────────┬──────────────────────┐
 ↓                     ↓                     ↓
Terrain Preparation    Urban GIS             Drain Reconstruction
 ↓                     ↓                     ↓
Hydraulic Terrain      Hydraulic Surface     Drain Graph + Parameters
                                               ↓
                                        Exchange Geometry
           \                 |                 /
            \                |                /
             └────── Versioned Digital Twin ─┘
                              ↓
                   Dynamic Forcing Package
                    ├── RainCube
                    ├── Hydraulic Boundary Series
                    ├── Operational Control Series
                    └── Antecedent Forcing
                              ↓
                     State Initialization
                              ↓
                       HydraulicState
                              ↓
                      Hydraulics Worker
                    ┌─────────┼──────────┐
                    ↓         ↓          ↓
                2D Surface   SWMM     Bidirectional
                  Solver    DYNWAVE   Exchange/Time
                    \         |          /
                     \        |         /
                       Volume Ledger
                            ↓
                         FloodCube
                            ↓
                  Road Exposure Projector
                            ↓
                      RoadFloodState
                            ↓
              ┌─────────────┼─────────────┐
              ↓             ↓             ↓
          Ensemble       Decision      Time-Dependent
          Analysis       Intelligence  Routing
              \             |             /
               \            |            /
                   2D / 3D Dashboard
```

---

# 17. Final Engineering Principle

> **Build the smallest scientifically valid system first. Freeze its contracts. Verify water, space, time, provenance, exchange physics, and numerical stability. Calibrate only identifiable parameters. Validate on independent data. Then scale geography, ensembles, AI, and visualization.**

A validated connected drainage catchment is a stronger final prototype than an unvalidated whole-city animation.
