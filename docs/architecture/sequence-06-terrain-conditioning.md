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

### Atomic increment 6.2 — recomputed control residuals

`vertical_validation.control_points` optionally supplies independent observations at grid-cell
centres. Each contains `control_id`, zero-based `row`/`column`, `reference_elevation_m`, the same
`vertical_datum`, `source_reference`, and timezone-aware `measured_at` (normalized to UTC). The
survey `method` is required. Duplicate IDs/cells, out-of-domain or nodata observations, incompatible
datums and non-finite values are rejected. Coordinates are computed from the grid origin and cell
size; this adapter does not interpolate off-centre survey observations.

The worker computes residual = hydraulic elevation minus observed elevation, RMSE, mean bias and
maximum absolute error using `hydraulic-cell-centre-residuals-v1`. Reported count/RMSE must agree
with supplied observations; a 0.000001 m absolute RMSE tolerance covers serialization/round-off
only, not engineering accuracy. Product RMSE/count fields now contain computed values only:
without observations they are null/zero, even if an unverified summary was supplied. The immutable
audit retains that reported summary, every control's provenance and every computed residual.

Passing the prototype RMSE screen **does not grant `HYDRAULIC_VALIDATED`**. Independent survey
authenticity, spatial coverage, contextual evidence and an engineering acceptance policy still need
review. Failed computed screens downgrade readiness. No observations or zero error is never
invented. This additive input contract and revised output semantics use a new pipeline fingerprint;
older products remain historical, with no destructive database migration.

`GET /terrain/products/{terrain_id}/audit` exposes these results. All terrain artifact endpoints
verify SHA-256 before returning bytes; corruption produces HTTP 409. Tests include the analytical
residuals `[3, 1, -2]` m (RMSE `sqrt(14/3)` m) and a preserved 1,000 m3 road-sag storage volume.

Artifacts are content-addressed by a deterministic fingerprint under:

```text
terrain/{city_id}/{source_id}/{dataset_version_id}/{terrain_id}/
```

`GET /terrain/readiness`, `GET /terrain/products`, product artifact endpoints, and
`GET /terrain/qa` expose metadata and bounded WGS 84 QA geometry. Heavy work belongs to
`floodguard.terrain.bootstrap`, never to a request handler.

### Atomic increment 6.3 — trustworthy QA geometry and viewer

QA emits at most 2,500 **terrain-cell** polygons, including on narrow grids. It prioritizes explicit
intervention cells and samples the remaining valid cells deterministically. If interventions alone
exceed the cap, their omitted count is reported. Each polygon covers its actual single source cell:
no stride-sized block borrows one sampled elevation, no nodata hole is painted over, and no final
cell extends beyond the grid. Multi-level catalog polygons are separate from the cell cap and retain
their projected corners and provenance.

The GeoJSON includes a finite WGS84 `bbox` and `sampling` metadata (valid/displayed/omitted cells,
omitted interventions, method and cap). The viewer uses that bbox, or a coordinate-pair-preserving
fallback for historical artifacts. It shows the selected product's status, marks historical products
excluded from the gate, explains sampling and limitations, and links to the audit. City selection
uses `/terrain/qa?city_id=kolkata`. Metadata is inserted as literal text, never HTML; obsolete async
responses cannot replace a newer selection.

The runtime policy is `sequence-6-terrain-v4`; rebuild existing raw packages to create new immutable
products. Readiness exposes `current_pipeline_version` so the viewer can distinguish historical
products. Tests cover thin grids, individual cell footprints, nodata, catalog corners and invalid
projection results. Five Node.js tests execute the actual viewer script with DOM/MapLibre doubles,
including unsafe-looking metadata, HTTP failures and selection races. They are skipped explicitly
when Node.js is absent. They do not replace a real browser/WebGL/CDN or Docker integration check.

## Scientific boundary

### Atomic increment 6.4 — explicit SRTM HGT conversion

`floodguard.terrain.srtm` converts an original uncompressed SRTMGL1 HGT tile into a bounded metric
pilot grid using nearest source posts. The adapter checks exact dimensions/byte count and tile
coordinates, retains negative elevations and nodata, rejects out-of-tile sampling, and caps JSON
output at 250,000 cells. Grid origins are snapped outward to the requested metric cell size.
The source remains unchanged; a new optional `derivation` contract records its SHA-256, filename,
conversion policy and pilot-boundary reference. Existing hand-prepared JSON inputs remain supported.

Format and datum follow the [LP DAAC SRTM User Guide](https://lpdaac.usgs.gov/documents/179/SRTM_User_Guide_V3.pdf).
Native post spacing is reported separately from an 80 m effective-information screening floor;
coarser computational cells raise that floor. This is not a local accuracy certification, and source
void-fill regions may be coarser. Datum compatibility and terrain assessments remain unresolved,
so conversion alone produces `VISUAL_READY`. GeoTIFFs, ZIPs, mosaics and 3-arc-second HGT tiles are
explicitly unsupported by this adapter. Its tests use synthetic ramps/voids solely as benchmarks.

This checkpoint demonstrates defensible preparation and auditable conditioning logic. It is not a
claim that Kolkata has a newly validated DEM, that the pilot has hydraulic terrain observations, or
that the later coupled solver can already be calibrated. Missing source access remains an explicit
limitation in readiness and audit records.
