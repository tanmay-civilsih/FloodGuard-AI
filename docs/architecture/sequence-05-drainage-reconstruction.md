# Sequence 5 — Legacy Municipal Drainage Reconstruction

## Scope

Sequence 5 converts one authentic Kolkata Municipal Corporation drainage drawing into a
provenance-preserving geospatial candidate layer. It does not infer hydraulic dimensions,
invert elevations, flow directions, materials, or connectivity that the source and review do not
support. It does not create terrain or a simulation-ready SWMM network.

The initial real object is the OpenCity/KMC Ward 7 PDF:

```text
Kolkata_-_Drainage_Network_Map_of_Ward_7.pdf
SHA-256 54f6a133d6978a692eef902ed7727d561b61af1080b4aa1fbc5547f2b80417b4
```

The PDF remains in the immutable Sequence 3 raw vault. Reconstruction artifacts use new,
deterministic keys under the spatial object store.

## Native inspection and OCR rule

The selected PDF is a one-page A0 AutoCAD export. The worker inspects native PDF operations before
considering OCR. The frozen object contains native vector paths and native text spans, so the
pipeline uses `NATIVE_VECTOR_TEXT` and records `ocr_used=false`. A map without adequate native
content is stopped for an explicit OCR-fallback review; OCR is never applied silently.

## Versioned georeference

The calibration file is:

```text
floodguard/reconstruction/calibrations/kmc-opencity-ward-7-v1.json
```

It is pinned to the raw PDF SHA-256 and to the SHA-256 of the KMC/OpenCity 2022 ward-reference KML.
Four named ward-boundary extrema fit a six-parameter affine transform from PDF page space to the
working Kolkata CRS, `EPSG:32645`. Every control-point residual, RMSE, maximum error, method, and
reference is persisted. The calibrated RMSE limit is 15 m, reflecting the legacy drawing and
cross-product boundary differences. This accuracy is adequate for reconstruction QA only and is
not an elevation, invert, or survey-accuracy claim.

## Native feature extraction

The initial KMC drawing's native CAD symbology is interpreted conservatively:

- red stroke fragments are grouped by local direction and offset, then merged across bounded dash
  gaps into drain candidates;
- repeated closed cyan circular symbols are retained as manhole candidates;
- native text matching manhole, invert, diameter, length, or sewer annotations is preserved as
  label points;
- labels and structures retain a nearest-drain association only within a declared page-space
  distance.

Every output feature stores its source object, dataset version, page, extraction method, confidence
score/band, and deterministic feature ID. Raw label text is preserved, but its engineering meaning
is not silently promoted into a model parameter.

## Immutable outputs

```text
reconstruction/{city_id}/{source_id}/{dataset_version_id}/{reconstruction_id}/working.geojson
reconstruction/{city_id}/{source_id}/{dataset_version_id}/{reconstruction_id}/qa.geojson
reconstruction/{city_id}/{source_id}/{dataset_version_id}/{reconstruction_id}/audit.json
```

The working layer uses `EPSG:32645`; the QA derivative uses WGS 84. Existing keys can be reused only
when their bytes are identical.

## Human QA gate

New reconstructions start as `PENDING_REVIEW`. An approval review must:

1. identify a human reviewer;
2. confirm source/basemap alignment;
3. confirm that the red and cyan source symbology is interpreted correctly;
4. inspect feature placement;
5. confirm missing engineering attributes remain `NULL`.

Review records are append-only. The service rejects an `AUTOMATED` approval. An automated actor may
run diagnostics or record a rejection, but cannot satisfy the frozen human-review gate.

Read-only and review endpoints are:

```text
GET  /reconstruction/readiness
GET  /reconstruction/maps
GET  /reconstruction/maps/{reconstruction_id}
GET  /reconstruction/maps/{reconstruction_id}/geojson
GET  /reconstruction/maps/{reconstruction_id}/reviews
POST /reconstruction/maps/{reconstruction_id}/reviews
GET  /reconstruction/qa
```

Heavy PDF reconstruction stays in the worker/CLI path:

```bash
docker compose exec -T api python -m floodguard.reconstruction.bootstrap --city-id kolkata
```

## Completion gate

The formal gate is:

```bash
python scripts/verify.py --reconstruction-bootstrap
```

It requires an authentic hash-pinned KMC PDF; successful native extraction of drains, structures,
and labels; a georeference within tolerance; immutable lineage artifacts; the QA viewer; and a
recorded human approval. Until that approval exists, readiness remains false and v0.5 must not be
tagged as frozen.

Passing Sequence 5 does not make the reconstructed features hydraulically simulation-ready. Drain
dimensions, inverts, directions, materials, topology interpretation, and field validation remain
explicit later work.
