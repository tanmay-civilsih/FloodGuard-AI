# Sequence 4 — Spatial Normalization, Resampling and Reference Harmonization

## Scope

Sequence 4 converts supported immutable Sequence 3 raw spatial objects into traceable normalized
products without changing the physical meaning of the source data. It does not reconstruct legacy
drainage drawings, condition hydraulic terrain, create hydraulic surface classes, or infer missing
engineering attributes.

## Working horizontal reference

The default Kolkata working CRS is configurable as:

```text
EPSG:32645 — WGS 84 / UTM zone 45N
```

The spatial worker validates at startup that the configured CRS is projected and metric. KML is
interpreted as WGS 84 longitude/latitude. GeoJSON follows RFC 7946 WGS 84 semantics unless a legacy
explicit CRS declaration is present.

Normalized vector coordinates are stored in the configured metric working CRS. A separate WGS 84
GeoJSON derivative is stored for MapLibre QA display. The QA derivative is not a second hydraulic
source; it is a display representation of the normalized geometry.

## Immutable lineage

Sequence 4 reads raw bytes only from immutable Sequence 3 object references and writes to a
separate bucket:

```text
normalized/{city_id}/{source_id}/{dataset_version_id}/{normalization_id}/working.json
normalized/{city_id}/{source_id}/{dataset_version_id}/{normalization_id}/qa.geojson
```

Each spatial database record preserves:

- source `dataset_version_id`;
- source `source_id` and category;
- raw object key;
- normalization fingerprint;
- SHA-256 of the normalized working object;
- source and working CRS;
- feature count and geometry types;
- working-CRS and WGS 84 bounds;
- maximum CRS round-trip numerical error;
- variable-specific resampling policy;
- vertical-reference fields;
- resolution/information-quality fields.

A normalization fingerprint includes the raw SHA-256, raw version, source identity, working CRS,
and Sequence 4 pipeline version. Reruns reuse an existing normalized layer. Existing spatial object
keys are never overwritten; if a key exists with different bytes, normalization fails.

## Service ownership

The spatial domain does not query harvester-private SQLAlchemy tables. The bootstrap worker obtains
Sequence 3 `DatasetVersionRead` / `RawObjectRead` contracts through the harvester service and reads
the immutable object keys those contracts expose. The spatial database owns only `spatial_layers`.

## Vertical reference gate

Every elevation-bearing dataset must carry:

```text
vertical_datum
vertical_unit
vertical_offset_m
datum_transform_status
vertical_reference_confidence
```

Allowed transform states are:

```text
NOT_APPLICABLE
COMPATIBLE
TRANSFORMED
UNRESOLVED
```

Elevation data are rejected by the vertical-reference validator unless the datum is compatible or
an explicit transform has been documented. Sequence 4 never silently assumes that terrain, drain
inverts, canal/river stage, or tide elevations share a vertical reference.

The current open Kolkata bootstrap normalizes non-elevation vector layers harvested in Sequence 3.
Therefore `elevation_layer_count=0` is permitted, but any future normalized elevation layer must
pass the vertical gate before `vertical_metadata_valid` can remain true.

## Variable-specific resampling

A single generic interpolation function is prohibited.

### Categorical

`NEAREST` selects the nearest source cell centre. No averaging is performed across categories.

### Elevation

`BILINEAR_WITH_SOURCE_UNCERTAINTY` performs rectilinear interpolation while carrying the source
uncertainty value forward unchanged. Resampling to a finer grid does not improve the recorded
source information resolution.

### Rainfall

`AREA_CONSERVATIVE` computes source/destination cell overlap areas. For each destination cell, the
rain rate is the overlap-area-weighted source rain volume divided by destination area.

The diagnostic follows the frozen specification:

```text
V = sum_t sum_i [R_i,t / (1000 * 3600)] * A_i * dt
relative_error = abs(V_before - V_after) / max(abs(V_before), machine_epsilon)
```

The accepted relative error is configured by:

```text
FLOODGUARD_RAINFALL_CONSERVATION_TOLERANCE
```

A deterministic non-uniform-grid conservation test is exposed in spatial readiness and is also
covered by unit tests.

## Resolution metadata

Spatial records distinguish:

```text
native_resolution_m
computational_resolution_m
effective_information_resolution_m
source_quality
```

The contract rejects an `effective_information_resolution_m` that claims finer source information
than the native resolution.

## Engineering QA viewer

`GET /spatial/qa` serves a minimal MapLibre QA page. It displays normalized layers from the API,
including current wards, catchments, and water bodies, and automatically supports future normalized
roads/buildings, source-map derivatives, reconstructed drainage, and QA/confidence markers.

The basemap is labelled visual context only. It is not a hydraulic input and does not replace
versioned FloodGuard datasets.

Read-only API endpoints:

```text
GET /spatial/readiness
GET /spatial/layers
GET /spatial/layers/{normalization_id}
GET /spatial/layers/{normalization_id}/geojson
GET /spatial/qa
```

Long normalization work runs in the CLI/worker path, not inside an HTTP request.

## Kolkata bootstrap

The Sequence 4 bootstrap consumes the latest COMPLETE raw version for relevant Kolkata vector
sources:

```bash
docker compose exec -T api python -m floodguard.spatial.bootstrap --city-id kolkata
```

Core completion categories are:

```text
WARD_BOUNDARY
CATCHMENT
WATER_BODY
```

`DRAINAGE_MAP`, `OPENSTREETMAP`, and `TRAFFIC` are optional at this stage. Unsupported raw objects
such as municipal drainage PDFs are retained in the raw vault and skipped; they are not guessed or
rasterized here. Drainage PDF reconstruction begins in Sequence 5.

## Completion gate

The formal local gate is:

```bash
python scripts/verify.py --spatial-bootstrap
```

It requires:

1. Python 3.12, Ruff, mypy, and pytest to pass;
2. the Docker platform and Sequence 4 API to be healthy;
3. the spatial bootstrap to normalize the available real Kolkata core vector layers;
4. no missing core categories;
5. metric CRS round-trip error within configured tolerance;
6. valid vertical metadata for every normalized elevation layer;
7. rainfall conservative-remapping diagnostic to pass;
8. the MapLibre QA page to be reachable.

Passing this gate establishes Sequence 4 spatial/reference readiness only. It does not establish
hydraulic terrain validity or drainage reconstruction quality.
