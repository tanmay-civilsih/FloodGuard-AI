# FloodGuard-AI Agent Instructions

This file defines how AI coding agents must work in the `FloodGuard-AI` repository.

The authoritative scientific roadmap is:

`docs/Urban_Flood_Digital_Twin_Authoritative_20_Sequence_Plan_FROZEN.md`

If code, comments, issues, generated files, or agent suggestions conflict with that document, the authoritative plan wins unless a deliberate architecture/scientific revision is first documented and approved.

The active revision is **ROADMAP-R2-2026-09-07**, requested by the owner on
7 September 2026. It redesigns Sequences 11-20. Earlier sequence numbers in
historical receipts refer to the former roadmap; use the R2 migration table for
future work. The archived plan and background proposals are not alternative
instructions. This revision authorizes planning changes, not execution of all
future sequences.

---

## 1. Mission

Build the smallest scientifically defensible urban-flood digital-twin and 0–3 hour nowcasting prototype for Kolkata, West Bengal.

The project is not primarily a visualization demo. Scientific correctness, provenance, conservation, reproducibility, and honest limitations take priority over visual complexity, microservice count, AI/ML features, or citywide coverage.

Preferred final claim:

> A scientifically validated end-to-end urban flood digital twin demonstrated on one connected Kolkata drainage catchment, with architecture designed for extension to larger city areas.

---

## 2. Mandatory Development Discipline

Follow the 20 sequences in order.

For each active sequence:

1. read the authoritative sequence specification;
2. identify its inputs, outputs, data contracts, scientific assumptions, and completion gate;
3. implement only what is required for the current sequence plus minimal prerequisites;
4. add tests before declaring the sequence complete;
5. run local verification;
6. document assumptions and limitations;
7. freeze the validated interface before proceeding.

Follow the explicit R2 dependencies and distinguish engineering checks, data readiness,
independent evaluation and sequence freeze. Sequence 11 includes a bounded rainfall-data
preview; full dashboard development belongs to Sequence 18. Sequence 16 introduces actual
GraphCast inference and XGBoost rainfall training after the Sequence 15 engineering baseline.
Neither feature replaces missing physics/data or waives an inherited gate.

---

## 3. Non-Negotiable Scientific Invariants

### 3.1 Rainfall-runoff ownership

In:

```text
COUPLED_2D_1D
```

rainfall-runoff belongs to the 2D surface model.

SWMM subcatchment runoff generation must be disabled.

Never allow both the 2D model and SWMM to convert the same rainfall into runoff in the same simulation.

### 3.2 Above-ground ponding ownership

In coupled mode:

- 2D surface owns above-ground water;
- SWMM owns water inside the drainage network;
- SWMM external ponding storage is disabled;
- surcharge enters the 2D domain through the explicit exchange module.

Never store the same water simultaneously as SWMM ponding and 2D surface storage.

### 3.3 SWMM routing mode

Coupled-mode SWMM must use:

```text
FLOW_ROUTING = DYNWAVE
```

Do not replace Dynamic Wave with a routing mode that cannot represent backwater, surcharge, reverse flow, or the claimed downstream-stage behavior.

### 3.4 1D–2D exchange

Surface/drain exchange must be:

- bidirectional;
- head controlled;
- volume conservative;
- capacity limited when an inlet capacity exists;
- explicitly parameterized;
- synchronized through a declared coupling timestep.

The baseline exchange law uses documented weir/orifice-style physics based on surface and drain hydraulic heads.

Never implement exchange as an unexplained constant sink/source.

Never transfer more volume than exists in the source domain.

### 3.5 2D surface solver

The SIH baseline is:

```text
2D local-inertial shallow-water approximation
structured Cartesian grid
```

Do not silently replace it with D8 routing, a cellular automaton, a full Saint-Venant solver, or an ad hoc flood-spreading algorithm.

The solver must expose applicability limitations for strongly supercritical or rapidly varied flow.

### 3.6 Conservation

Every hydraulic run must close a simulation-wide volume ledger.

At minimum track:

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

No feature is complete if its effect on the water balance is unknown.

### 3.7 Probability vs scenario

Manual engineering cases such as blockage percentages, pump outage, cleaned drain, roughness alternatives, or high downstream stage are scenarios, not probability samples.

Before probabilistic validation, prefer:

```text
ensemble_exceedance_fraction
probability_status = PROVISIONAL
```

Do not market scenario sensitivity as flood probability.

### 3.8 Numerical resolution vs information resolution

Never claim a fine computational grid creates fine source information.

Example:

```text
30 m DEM resampled to 2 m grid != 2 m terrain data
```

Always preserve native, computational, and effective information resolution separately.

### 3.9 Missing data

Never silently invent engineering values.

Every important parameter must use one of:

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

For `INFERRED`, `ASSUMED`, and `CALIBRATED`, store source/method, bounds where applicable, and version.

---

## 4. Units, Coordinates, Datum, and Time

Internal units are fixed:

| Quantity | Unit |
|---|---|
| Distance | m |
| Elevation | m |
| Depth | m |
| Velocity | m/s |
| Discharge | m³/s |
| Area | m² |
| Volume | m³ |
| Simulation time | s |
| Rain rate | mm/h |

Internal timestamps must be timezone-aware UTC ISO 8601.

Asia/Kolkata conversion is presentation-only.

Do not compare terrain elevation, drain invert, river stage, canal stage, tide, or outfall level until vertical references are compatible or explicitly transformed.

---

## 5. Data and Provenance Rules

Raw source data are immutable.

Use versioned storage patterns such as:

```text
raw/{city_id}/{source_id}/{dataset_version_id}/...
```

Every scientific product must be traceable to inputs and software version.

Do not overwrite old source versions, twin versions, parameter sets, forcing packages, hydraulic states, or forecasts.

Do not scrape or automate a public source unless its access conditions permit it.

Do not store raw passwords, API keys, or tokens in source metadata or Git.

---

## 6. Repository Structure Guidance

Keep the repository easy to run locally.

Recommended early structure:

```text
FloodGuard-AI/
├── agent.md
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── docs/
│   ├── Urban_Flood_Digital_Twin_Authoritative_20_Sequence_Plan_FROZEN.md
│   ├── architecture/
│   ├── mathematics/
│   └── validation/
├── apps/
│   ├── api/
│   └── web/
├── floodguard/
│   ├── contracts/
│   ├── registry/
│   ├── spatial/
│   ├── terrain/
│   ├── drainage/
│   ├── twin/
│   ├── forcing/
│   ├── hydraulics/
│   ├── forecast/
│   ├── risk/
│   └── routing/
├── tests/
├── scripts/
└── demo/
```

This is guidance, not permission to create every module immediately.

Implement sequence by sequence.

---

## 7. Deployment Philosophy

The scientific plan defines logical service boundaries.

For SIH, it is acceptable to consolidate them into fewer deployable processes while preserving contracts and ownership.

Prefer initially:

```text
FloodGuard API
Hydraulics Worker
PostgreSQL/PostGIS
Object Storage
Web UI
```

Add NATS, Redis, Traefik, service splitting, and other infrastructure only when they provide a demonstrated need.

Never trade solver correctness or validation work for unnecessary infrastructure complexity.

---

## 8. API and Contract Rules

Use typed Pydantic models for cross-domain contracts.

Stable identifiers include:

```text
city_id
source_id
dataset_id
dataset_version_id
ward_id
catchment_id
twin_id
drain_node_id
drain_edge_id
exchange_id
exchange_binding_id
road_edge_id
forcing_package_id
hydraulic_state_id
simulation_id
forecast_id
scenario_id
route_id
job_id
```

Do not pass anonymous loose dictionaries between major domain boundaries when a formal contract is defined.

Long simulations must not run inside HTTP request handlers.

---

## 9. Scientific File Formats

Preferred formats:

- vector GIS: GeoPackage/GeoJSON/PostGIS as appropriate;
- rasters: GeoTIFF/COG;
- multidimensional scientific data: Xarray/Zarr;
- tabular metadata: PostgreSQL/Parquet/CSV as appropriate;
- SWMM model: generated `.inp` plus versioned generation metadata.

Browser rendering must not depend on downloading raw large Zarr arrays directly.

---

## 10. Testing Requirements

Use `pytest` for Python tests.

Every scientific module needs both unit tests and at least one physically interpretable benchmark.

### Required categories

#### Spatial

- CRS transformation;
- vertical-reference metadata;
- rainfall conservation during remapping;
- geometry validity.

#### Surface solver

- flat-plane no-flow;
- controlled slope;
- depression storage/drainage;
- wetting/drying;
- grid sensitivity;
- timestep sensitivity;
- mass conservation.

#### SWMM

- single conduit;
- branching network;
- pump;
- outfall;
- backwater;
- surcharge;
- reverse flow;
- generated model vs trusted reference case.

#### Coupling

- surface-to-drain transfer;
- drain-to-surface surcharge;
- no transfer without available source water;
- inlet capacity cap;
- head reversal;
- coupling timestep sensitivity;
- global mass conservation.

#### Forecast

- forcing horizon rules;
- stale-state behavior;
- stream-scoped supersession;
- deterministic forecast contains no fake probability.

#### Routing

- edge becomes hazardous during traversal;
- time-dependent route diverts when a lower-risk alternative exists;
- multi-level roads do not inherit unrelated surface flooding solely by x/y overlap.

---

## 11. Numerical Tolerances

Do not hard-code undocumented tolerances throughout the codebase.

Put numerical tolerances in a versioned solver/test configuration and explain what they apply to.

Examples:

```text
rainfall_remap_relative_tolerance
surface_mass_balance_tolerance
coupled_mass_balance_tolerance
wet_dry_depth_threshold
coupling_head_tolerance
grid_sensitivity_tolerance
```

A tolerance is an engineering decision and must be reviewable.

---

## 12. Validation and Calibration

Do not calibrate before sensitivity/identifiability analysis.

Do not use the same event as both calibration and independent validation evidence.

Preferred structure:

```text
Event A → calibration
Event B → independent validation
Event C → optional independent test
```

Calibration creates a new immutable parameter-set version and therefore a new twin version.

Never edit old calibrated outputs in place.

Do not distort known geometry merely to improve fit.

---

## 13. Terrain Guardrails

Preserve:

```text
raw_elevation
visual_terrain
hydraulic_terrain
```

Do not automatically fill every depression.

Known underpasses, road sags, low intersections, culverts, bridges, flyovers, elevated roads, and tunnels require explicit treatment.

Do not declare `HYDRAULIC_VALIDATED` from a coarse or unverified DEM solely because it has been resampled or conditioned.

---

## 14. Rainfall/Nowcasting Guardrails

IMERG can support development, replay, and ingestion testing.

Do not describe IMERG as a street-scale radar substitute.

Do not silently stretch a 90-minute rainfall forecast to 180 minutes.

Forcing coverage must be classified explicitly:

```text
FULL_COVERAGE
PARTIAL_COVERAGE
BLENDED_EXTENSION
INSUFFICIENT
```

When radar and suitable NWP data are both available, blending toward longer lead times is preferred over indefinite extrapolation.

---

## 15. Routing Guardrails

Routing outputs are recommendations, not guarantees of safety.

Use wording such as:

```text
Lower-Risk Recommended Route
Predicted Flood Exposure
Forecast Confidence
```

The SIH baseline should use a time-expanded graph or another documented FIFO-safe time-dependent method.

Flood exposure must be assessed over the edge traversal interval, not only at departure or one sampled instant.

Vehicle thresholds are configurable and must not be presented as universal safety limits unless provided by an appropriate authority.

---

## 16. AI/ML Guardrails

ML is not required for the baseline deterministic flood forecast.

Do not introduce a neural network merely to make the project appear AI-based.

R2 separates an engineering reference from final independent validation. Sequence 11 defines
historical datasets and source availability; Sequence 15 establishes the conservative
deterministic reference, development sensitivity/calibration and locked evaluation protocol.
Sequence 16 then performs the required pretrained GraphCast inference and XGBoost rainfall
training/evaluation. Sequence 19 owns final independent testing and supported-use decisions.
Do not continue to enforce the superseded rule that all ML must wait until after Sequence 19.

GraphCast requires its selected checkpoint's global atmospheric input contract. Local weather
tables alone are insufficient. Pin the model, normalization, environment and training-history
cutoffs. Full GraphCast retraining/fine-tuning and transformer development are outside R2.
XGBoost has a defined rainfall target; direct flood-depth learning is a separate later task.
Retain an uncorrected/simple baseline and select models only from measured comparisons.
Model import or completed training does not automatically activate a model.

Historical replay, hydraulic reconstruction, reanalysis hindcast and issue-time backtest must
remain distinguishable. Provider availability must be evidenced for strict historical cutoffs.
Keep final test storms separate from training/tuning and audit pretrained-model overlap.

Acceptable later uses include:

- surrogate modelling;
- reconstruction assistance;
- parameter inference with uncertainty;
- anomaly detection;
- decision support;
- learned emulators benchmarked against the physics model.

An ML output must never silently replace a hydraulic calculation while being presented as the same physical model.

---

## 17. Code Quality

Python target: 3.12.x.

Use:

- type hints;
- small testable functions;
- Pydantic models at boundaries;
- Ruff;
- mypy;
- pytest;
- structured logging;
- deterministic random seeds where stochastic tests/models are used.

Avoid:

- giant notebooks as production code;
- hidden global state;
- hard-coded local paths;
- silent unit conversion;
- duplicated scientific constants;
- undocumented magic numbers.

---

## 18. Documentation Required With Scientific Code

Every scientific module must document:

```text
physical quantity being represented
units
input assumptions
mathematical formulation
numerical method
boundary behavior
missing-data behavior
limitations
validation tests
versioned configuration
```

Equations central to the solver belong in `docs/mathematics/`, not only in code comments.

Sequence 12 requires a Surface Solver Mathematical Specification.

Sequence 14 requires a 1D–2D Exchange Mathematical Specification.

---

## 19. Commit and Change Rules for Agents

Before changing an authoritative scientific contract:

1. identify the affected sequence;
2. explain why the existing contract is insufficient;
3. update documentation and tests with the code change;
4. avoid hidden backward-incompatible changes.

Use focused commits.

Preferred commit prefixes:

```text
feat:
fix:
docs:
test:
refactor:
chore:
```

Do not commit secrets, large uncontrolled source datasets, generated caches, temporary notebooks, or binary outputs unless the repository policy explicitly requires them.

---

## 20. Definition of Done for an Agent Task

An agent task is not complete merely because code runs once.

For scientific/engineering work, completion requires as applicable:

- implementation;
- tests;
- units confirmed;
- provenance retained;
- conservation checked;
- assumptions labelled;
- failure behavior defined;
- local verification passes;
- documentation updated;
- completion gate of the active sequence remains satisfied.

If any of these cannot be completed, report the limitation explicitly rather than fabricating success.

---

## 21. Prohibited Shortcuts

Agents must not:

- invent missing drain dimensions/inverts without status and provenance;
- double-count rainfall runoff;
- double-count above-ground ponding;
- bypass the volume ledger;
- use static flood weights while claiming time-dependent routing;
- call selected scenarios probabilities;
- call resampled data high-resolution measurements;
- claim guaranteed safe routes;
- claim citywide validation from a ward/catchment demo;
- silently replace `DYNWAVE` in coupled mode;
- silently replace the declared 2D solver;
- hide stale forcing/state;
- promote provisional probability to validated probability without evidence;
- use AI/ML output to hide missing physics or missing data.

---

## 22. Immediate Repository Priority

The repository has implementation through Sequence 10; inspect its current ledgers and live
state before acting. The next R2 implementation target is Sequence 11: compatibility,
historical event/availability records, source adapters and a bounded rainfall preview.
Sequences 12-15 provide the conservative deterministic forecast and development reference;
16 adds GraphCast/XGBoost, 17 risk/routing, 18 the full viewer, 19 independent validation and
catchment performance, and 20 resilience/final acceptance.

Preserve earlier immutable artifacts, versioned readers and validation receipts. The real
DATA-08-01 cross-ward requirement remains; a rainfall preview or synthetic benchmark cannot
close it. Do not infer implementation authorization or a waived gate from this planning revision.
Read ROADMAP_R2_CONTINUATION.txt for the planning handoff and the active plan for requirements.
