# Sequence 7 — Urban GIS Reconstruction, Hydraulic Surface Classes and Roof Runoff Policy

Status: Sequence 7 technical-development specification. Final real-pilot human acceptance is deferred to Sequence 20 under `docs/validation/final-human-review-policy.md`.

## Objective

Maintain two deliberately separate city representations:

1. **visual city** — presentation geometry such as buildings, heights, roads, water bodies, parks and administrative context;
2. **hydraulic surface** — simplified, explicitly owned surface classes used by later hydrologic/hydraulic components.

A visually detailed object is never automatically a hydraulic object. Hydraulic ownership and loss behavior must be explicit.

## Hydraulic surface classes

The Sequence 7 contract supports exactly:

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

Every hydraulic feature carries one explicit `hydraulic_domain`. Sequence 7 surface features may use `SURFACE_2D`; `WATER` may also be a `BOUNDARY`. A Sequence 7 surface feature may not claim `NETWORK_1D` ownership because the drainage graph is introduced in Sequence 8. `VISUAL_ONLY` objects belong only in the visual representation.

## Hydrologic loss policy

Each runoff-producing surface chooses exactly one compatible formulation.

### Simplified runoff coefficient

For rain rate `R` and runoff coefficient `C_r`:

\[
R_e = C_r R
\]

`C_r` must be finite and in `[0,1]`. Explicit infiltration/loss rates cannot be configured simultaneously.

### Explicit losses

For infiltration rate `I` and other loss rate `L`:

\[
R_e = \max(0, R-I-L)
\]

The non-negative bound prevents a surface from generating negative water. An explicit-loss surface cannot also define `C_r`.

Every active hydrologic parameter carries one of the project provenance states:

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

`MISSING` is not accepted for an active Sequence 7 runoff policy. Reference-fixture parameters are explicitly `ASSUMED` and are not real-pilot values.

## Roof runoff policy

Sequence 7 does **not** bind roofs to numerical surface cells. The contract rejects undeclared fields such as `surface_cell_ids`.

A roof must have exactly one rule:

```text
ROOF
  -> versioned RoofReceivingGeometry owned by SURFACE_2D
     OR
  -> explicit drain target reference
```

The explicit drain target is a reference only. Sequence 8 will define the directed drain graph and physical exchange geometry.

For roof area `A`, effective roof rain rate `R_e` in mm/h, and interval `Δt` in seconds:

\[
V_{roof} = \frac{R_e}{1000\times3600} A\Delta t
\]

If `V_t` is the volume transferred to the receiving geometry/target, the Sequence 7 conservation diagnostic is:

\[
\epsilon_{roof}=\frac{|V_{roof}-V_t|}{\max(V_{roof},10^{-15})}
\]

The transfer passes when `ε_roof` is no greater than the versioned rule tolerance. The default technical reference tolerance is `1e-9`; each persisted rule records its own tolerance.

## Geometry and CRS rules

- Package CRS must be the configured projected metric working CRS (`EPSG:32645` in the current Kolkata prototype).
- Visual/hydraulic surface geometries and roof receiving geometries are polygonal `Polygon`/`MultiPolygon` features.
- Existing strict finite-coordinate/topology validation is reused.
- Invalid geometry is rejected; Sequence 7 does not silently repair arbitrary linework.

## Immutable products

A valid `UrbanGisPackage` is fingerprinted with the Sequence 7 pipeline version and persisted into separate immutable artifacts:

```text
urban-gis/{city_id}/{pilot_area_id}/{urban_gis_id}/
  visual_city.geojson
  hydraulic_surface.geojson
  roof_runoff.json
  qa.geojson
  audit.json
```

Every artifact SHA-256 is stored in `urban_gis_products`. Reads recompute the checksum and fail closed on corruption. Rebuilding an identical package is idempotent.

Readiness verifies all five stored artifacts before counting a current-pipeline package as
eligible. Missing or corrupted artifacts remove that package from readiness, while retaining its
historical database record. Reuse also verifies all artifacts and cannot silently recreate missing
objects or return success for corrupted bytes. New builds read back their persisted artifacts.

The audit records:

- pipeline/fingerprint;
- evidence scope;
- surface and roof policy versions;
- source references;
- domain-ownership completeness;
- roof-rule completeness;
- `surface_cell_ids_assigned = false`;
- limitations.

## Evidence scopes and readiness

```text
REFERENCE_FIXTURE
REAL_PILOT_PROVISIONAL
REAL_PILOT_REVIEWED
```

These map to:

```text
REFERENCE_READY
REAL_PILOT_PROVISIONAL
REAL_PILOT_REVIEWED
```

`REFERENCE_READY` is sufficient only for the automated development gate. It proves the code path and scientific contracts using controlled geometry. It is not real Ward 7 acceptance.

Final Sequence 7 completion requires `REAL_PILOT_REVIEWED`, but project-owner policy defers that human-only acceptance to Sequence 20. Until then the API exposes both:

```text
technical_development_gate_passed
final_human_acceptance_pending
final_completion_gate_passed
```

so downstream services cannot confuse technical progression with final engineering acceptance.

## Deterministic reference fixture

`python -m floodguard.urban_gis.bootstrap` creates `kolkata-sequence7-reference` using controlled synthetic geometry. It exercises all eight hydraulic classes, both loss modes, a roof, one versioned receiving geometry, visual/hydraulic separation, object-store immutability and readiness semantics.

The fixture contains no claim that the geometry or hydrologic parameters describe real Kolkata streets/buildings.

## API

Read-only endpoints:

```text
GET /urban-gis/readiness
GET /urban-gis/products
GET /urban-gis/products/{urban_gis_id}
GET /urban-gis/products/{urban_gis_id}/visual
GET /urban-gis/products/{urban_gis_id}/hydraulic
GET /urban-gis/products/{urban_gis_id}/roof-runoff
GET /urban-gis/products/{urban_gis_id}/qa
GET /urban-gis/products/{urban_gis_id}/audit
GET /urban-gis/qa
```

No HTTP endpoint automatically promotes reference/provisional data to reviewed real-pilot evidence.

## Automated technical gate

```text
python scripts/verify.py --services --urban-gis-bootstrap
python scripts/sequence7_development_gate.py --run-checks
```

The gate requires static/type/test checks, service health, Sequence 7 API identity, current-pipeline reference readiness, immutable object storage and source/runtime identity. Real-pilot visual classification, hydraulic class/domain review and roof receiving-target acceptance remain in the Sequence 20 human-review register.

The gate rechecks the source fingerprint, commit and clean worktree after verification. Evidence
collected across a source/commit change cannot qualify for a technical freeze. CLI regression tests
write reports into isolated temporary directories, preserving operator evidence.

## Explicit limitations at technical freeze

- No real Ward 7 building/road/roof classification is asserted by the reference fixture.
- No roof is bound to a numerical cell in Sequence 7.
- No roof drain target is promoted into a Sequence 8 network node before the drain graph exists.
- Reference hydrologic coefficients/loss rates are controlled test values, not calibrated Kolkata parameters.
- Final visual/engineering acceptance remains pending Sequence 20.
