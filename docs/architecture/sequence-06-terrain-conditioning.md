# Sequence 6 — Hydraulically Conditioned Terrain and Multi-Level Urban Structures

Status: v0.6 checkpoint on `sequence-6-conditioned-terrain`.

The `terrain-worker` prepares elevation products for later hydraulic simulation while retaining
source limitations. This sequence owns terrain provenance and conditioning; it does not run a
surface solver, infer missing elevations, or certify a hydraulic model.

## Input contract

The worker reads one immutable raw-vault object whose filename ends in `.terrain.json` or
`.terrain-package.json`. Its JSON document is a `TerrainPackage` containing:

- a rectilinear metric `TerrainGrid` with explicit CRS, dimensions, cell size, origin, and nullable
  elevations;
- `source_surface_type` (`DSM`, `DTM`, or `UNKNOWN`);
- vertical datum, unit, transform status, and quality;
- separate native, computational, and effective information resolutions;
- depression and multi-level assessments;
- explicit intervention records;
- a multi-level structure catalog; and
- vertical-validation evidence and limitations.

The configured working CRS must be projected with metre axes. This checkpoint deliberately does
not turn arbitrary GeoTIFF/COG bytes into a grid. A future raster adapter can emit this contract
after its own CRS, nodata, unit, and provenance checks.

## Three immutable products

Every build retains the raw object pointer and writes separate artifacts:

1. `raw_elevation` — the exact immutable source bytes;
2. `visual_terrain` — a source-faithful grid for display and inspection; and
3. `hydraulic_terrain` — the visual grid plus only the documented interventions.

The visual product is never silently converted from DSM to DTM. No sink-filling algorithm runs by
default. A genuine underpass, road sag, low intersection, or intended storage depression remains
unchanged unless a named intervention records why it should change. Every fill or obstruction
removal is bounded by `max_conditioning_adjustment_m`, provenance-backed, and auditable.

Flyovers, bridges, underpasses, culverts, elevated roads, and tunnels are represented in a separate
structure catalog with lower and upper elevations, roles, bounds, source reference, and confidence.
The QA GeoJSON draws these separately so a single-valued cell elevation cannot imply overlapping
road levels.

## Readiness and validation

The worker records:

```text
native_horizontal_resolution_m
computational_resolution_m
effective_information_resolution_m
vertical_quality
vertical_validation_method
vertical_rmse_m
control_point_count
road_sag_validation
underpass_validation
drain_rim_elevation_consistency
validation_limitations
```

### Atomic increment 6.1 — fail-closed inputs and readiness

Input contracts reject non-finite values, all-nodata grids, blank evidence, duplicate JSON keys,
unknown fields, contradictory catalogs and out-of-grid structures. Effective information resolution
cannot be finer than either the native source or the computational grid. Supplied elevations are
always metres; this worker does not perform implicit unit conversions.

Summary RMSE/count/check labels alone cannot establish `HYDRAULIC_VALIDATED`. Missing observations
cap readiness at `HYDRAULIC_SCENARIO_READY`. Explicit failed checks or RMSE above the declared limit
downgrade to `VISUAL_READY`. A `TRANSFORMED` label without a supported transformation-evidence
contract also remains visual-only. The default 5 m RMSE limit is a prototype screening setting,
not an engineering acceptance standard.

Readiness counts only the latest product per pilot from the current pipeline policy. Historical
products remain readable and immutable but cannot satisfy the gate. The response distinguishes
`total_terrains`, `eligible_terrains`, and `historical_terrains`; status counts cover eligible products.
Rebuild packages after a pipeline-version change. The completion gate requires at least one eligible
scenario-ready product plus documented depression and multi-level assessments; it is not a freeze
approval or proof of real pilot observations.

## Artifacts and API

Artifacts are content-addressed by a deterministic fingerprint under:

```text
terrain/{city_id}/{source_id}/{dataset_version_id}/{terrain_id}/
```

`GET /terrain/readiness`, `GET /terrain/products`, product artifact endpoints, and
`GET /terrain/qa` expose metadata and bounded WGS 84 QA geometry. Heavy work belongs to
`floodguard.terrain.bootstrap`, never to a request handler.

## Scientific boundary

This checkpoint demonstrates defensible preparation and auditable conditioning logic. It is not a
claim that Kolkata has a newly validated DEM, that the pilot has hydraulic terrain observations, or
that the later coupled solver can already be calibrated. Missing source access remains an explicit
limitation in readiness and audit records.
