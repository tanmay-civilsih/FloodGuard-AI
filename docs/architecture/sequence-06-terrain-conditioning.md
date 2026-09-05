# Sequence 6 — Hydraulically Conditioned Terrain and Multi-Level Urban Structures

Status: v0.6 checkpoint on `sequence-6-conditioned-terrain`.

Local validation reported by the project operator on 2026-09-05 for checkpoint `b341430`:
130 tests, Ruff, mypy and all six Docker services passed. The real terrain gate failed with zero
products and no COMPLETE SRTM raw version. This records software/service success and a remaining
data dependency; it is not a Sequence 6 freeze approval.

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

### Atomic increment 6.5 — local raster import and original-byte verification

The existing automatic harvester cannot acquire a portal entry or convert an HGT. The terrain
importer adds an explicit operator-supplied file path using the existing raw-vault/version contracts;
it does not change the source registry, weaken the automated harvester's access checks, or download
anything. It accepts only the registered NASA SRTMGL1 source when its status/access class permits
local import. `imported_by` and the actual `access_reference` are mandatory and recorded as operator
assertions, not independently verified authorization. Never put credentials into the receipt.

The CLI selects the latest reconstruction for the requested city/ward and requires its recorded
human approval. Its metric extent and working-artifact checksum become the crop's boundary
reference. This does not turn the map extent into a hydrologic catchment or approve terrain quality.

Each input version stores the original HGT, derived `pilot.terrain.json`, import receipt and manifest.
Repeated identical inputs/receipt reuse the version; changed provenance creates a new version.
Failed writes remain FAILED, never COMPLETE, and cannot pass readiness. `--plan` and `--dry-run`
write no versions or objects. The plan identifies the needed tile; the dry run also validates the file.

The terrain worker requires the original HGT in the same immutable manifest, verifies its hash,
and recomputes every derived grid cell before building/reusing a terrain product. Unsupported
metadata changes and information-resolution overstatements are rejected. `/raw` returns original
HGT bytes as `application/octet-stream` for these products; existing JSON inputs retain JSON
responses. The audit records both the input-package and original-raster lineage. Policy version is
`sequence-6-terrain-v5`; existing products remain historical until rebuilt.

#### Local PowerShell workflow

Pull `sequence-6-conditioned-terrain`, then rebuild and inspect the required input:

```powershell
docker compose up -d --build --wait --wait-timeout 180
docker compose exec -T api python -m floodguard.terrain.import_srtm --plan
```

Obtain the indicated **SRTMGL1 V003** tile from its
[NASA Earthdata product page](https://www.earthdata.nasa.gov/data/catalog/lpcloud-srtmgl1-003),
using your authorized access. For the current Kolkata pilot the tile is `N22E088.hgt`. Extract the
original HGT from its downloaded ZIP; keep its original filename. A screenshot, GeoTIFF, renamed
ZIP, fabricated grid or a different elevation product is not a substitute.

For an original file saved at `D:\Terrain\N22E088.hgt` (replace that path as needed):

```powershell
docker compose cp "D:\Terrain\N22E088.hgt" api:/tmp/N22E088.hgt
$accessReference = Read-Host "Describe the actual download source and access basis"
docker compose exec -T api python -m floodguard.terrain.import_srtm --file /tmp/N22E088.hgt --imported-by "$env:USERNAME" --access-reference "$accessReference" --dry-run
```

When the dry run succeeds, run the same command without `--dry-run`:

```powershell
docker compose exec -T api python -m floodguard.terrain.import_srtm --file /tmp/N22E088.hgt --imported-by "$env:USERNAME" --access-reference "$accessReference"
python scripts\verify.py --services
Start-Process "http://localhost:8000/terrain/qa?city_id=kolkata"
```

Initial readiness is `VISUAL_READY`. The real terrain gate intentionally remains pending until
local vertical-reference compatibility, depression decisions and multi-level assessments are
documented. No controls, elevations, classifications or approvals are invented by this workflow.

### Atomic increment 6.6 — versioned terrain assessments

The local importer accepts `--assessment` with a typed JSON review. Each assessment names its
reviewer and timezone-aware review time, references the exact unassessed package SHA-256, and
documents vertical-reference compatibility, intended DSM use, depressions, multi-level structures,
observations where available, and remaining limitations. The base hash covers the original HGT,
pilot/boundary reference, grid and conversion metadata. A review cannot be reused against a changed
tile, extent, cell size or pilot without another review of that input.

This adapter supports an unchanged EGM96 surface. `COMPATIBLE` requires an explicitly documented
local EGM96 reference; it does not perform datum transformations. Evidence fields must cite the
actual sources and method used, including the absence of evidence when an assessment remains
`NOT_ASSESSED`. Source documentation alone does not establish local vertical compatibility, and a
coarse raster alone cannot justify `CONFIRMED_NONE` for street depressions or overlapping levels.
The review records these statements as operator assertions, not independently verified findings.

Completed reviews may add only the existing bounded interventions, structure catalog and validation
observations. They cannot change the original source grid, DSM classification, source quality or
resolution metadata. Reported control statistics require actual observations. The dry run evaluates
interventions and recomputes residuals before creating any database version or vault objects.

The new version retains `terrain-assessment.json` alongside the original HGT, terrain package and
receipt. Every worker build/reuse checks the assessment's manifest entry, byte size, SHA-256 and
base-package binding, and reproduces the entire assessed package. The audit includes the review.
Missing, corrupted or contradictory review evidence cannot promote a derived SRTM package.
Policy version is `sequence-6-terrain-v6`; rebuild older products before evaluating readiness.

After the original HGT has been copied into the API container as above, export a form:

```powershell
docker compose exec -T api python -m floodguard.terrain.import_srtm --file /tmp/N22E088.hgt --imported-by "$env:USERNAME" --access-reference "$accessReference" --assessment-template /tmp/kolkata-terrain-assessment.json
docker compose cp api:/tmp/kolkata-terrain-assessment.json "D:\Terrain\kolkata-terrain-assessment.json"
```

This validates the file and writes an intentionally incomplete form; it creates no raw-vault or
terrain version. Existing template paths are not overwritten. Fill the form using actual inspection
and reference records. Use `reviewed_at` with an explicit UTC offset. Leave uncertain statuses as
`UNRESOLVED`/`NOT_ASSESSED` and document why; do not invent elevations or observations. The complete
field schema is available without a database connection:

```powershell
docker compose exec -T api python -m floodguard.terrain.import_srtm --assessment-schema
```

Then copy the completed form and validate it:

```powershell
docker compose cp "D:\Terrain\kolkata-terrain-assessment.json" api:/tmp/kolkata-terrain-reviewed.json
docker compose exec -T api python -m floodguard.terrain.import_srtm --file /tmp/N22E088.hgt --imported-by "$env:USERNAME" --access-reference "$accessReference" --assessment /tmp/kolkata-terrain-reviewed.json --dry-run
```

After a successful dry run, import and run the completion gate:

```powershell
docker compose exec -T api python -m floodguard.terrain.import_srtm --file /tmp/N22E088.hgt --imported-by "$env:USERNAME" --access-reference "$accessReference" --assessment /tmp/kolkata-terrain-reviewed.json
python scripts\verify.py --terrain-bootstrap
Invoke-RestMethod "http://localhost:8000/terrain/readiness?city_id=kolkata" | ConvertTo-Json -Depth 10
Start-Process "http://localhost:8000/terrain/qa?city_id=kolkata"
```

Schema checks do not verify the truth of review statements or approve an engineering model.
The real pilot must satisfy the authoritative completion gate before a release tag/freeze: source
bytes and provenance, visual/hydraulic products, preserved genuine depressions, correctly classified
important multi-level structures, explicit limitations, conservative readiness and local service/QA
validation. This increment grants no automatic freeze. Without adequate vertical observations,
readiness remains scenario-ready or lower.

Tests use an explicitly synthetic 42 m raster, a protected cell, a separate bridge catalog, and a
40 m reference control: the unchanged protected cell has a computed 2 m residual. They verify
immutable review versions, stale-source rejection, corruption failures, dry-run behavior and that
a newer failed review removes an older product's eligibility. These are software benchmarks,
not real Kolkata terrain evidence.

## Scientific boundary

This checkpoint demonstrates defensible preparation and auditable conditioning logic. It is not a
claim that Kolkata has a newly validated DEM, that the pilot has hydraulic terrain observations, or
that the later coupled solver can already be calibrated. Missing source access remains an explicit
limitation in readiness and audit records.
