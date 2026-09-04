# Sequence 3 — Automatic Data Harvester and Immutable Raw Data Vault

## Scope

Sequence 3 acquires only registry sources whose recorded access conditions permit automation. It preserves source bytes exactly as received and creates immutable dataset versions. No reprojection, resampling, geometry repair, OCR, raster conversion, or scientific normalization occurs here.

## Governance gate

The worker reads source metadata through the registry service contract. It requires:

- `status = AVAILABLE`;
- `automation_allowed = true`;
- `OPEN_AUTOMATED`, or an explicitly enabled `AUTHORIZATION_REQUIRED` source;
- a supported acquisition adapter;
- credentials resolved only from `credential_ref` when authorization is explicitly enabled.

`OPEN_MANUAL`, `PUBLIC_VIEW_ONLY`, `COMMERCIAL_OPTIONAL`, and `UNKNOWN` are not harvested automatically by the default worker.

## Acquisition adapters

The generic acquisition planner supports:

- direct HTTP/REST resources;
- CKAN `package_show` resource discovery;
- STAC Item asset discovery;
- bounded Overpass POST requests only when an explicit query is supplied;
- WMS/WFS/WMTS URLs only when explicit request parameters are supplied;
- PBF extract downloads only when deliberately enabled by the bootstrap caller.

File format is not transformed at acquisition time. PDF, GeoJSON, KML, CSV, GeoTIFF, NetCDF, GRIB, PBF, and other source bytes remain raw.

## OSM safeguards

The harvester does not use standard OpenStreetMap map tiles or the OSM editing API for bulk acquisition. Public Overpass requires an explicit bounded query. Large PBF retrieval is an opt-in bootstrap mode and remains subject to configured byte limits.

## Immutable raw layout

```text
raw/{city_id}/{source_id}/{dataset_version_id}/
├── objects/
│   ├── 0000-<source filename>
│   └── ...
└── manifest.json
```

The application calls write-once vault operations. An existing key is never replaced. MinIO bucket versioning is also enabled. Production deployments that require protection from privileged administrator deletion should additionally configure infrastructure-level retention/object lock.

## Dataset version identity and change detection

`dataset_id` is deterministic per `source_id`. Each successful changed harvest creates a new random `dataset_version_id`.

For every downloaded object the worker records:

```text
source_url
filename
sha256
byte_size
content_type
etag
last_modified
```

A deterministic manifest fingerprint is calculated from the source ID and sorted raw-object fingerprints. If that fingerprint already belongs to a complete version, the harvest result is `UNCHANGED` and no object is written. Changed bytes produce a new version and `previous_version_id` links to the latest complete predecessor.

## Provenance

Every dataset version stores a JSON snapshot of the registry source metadata that applied at acquisition time. The raw manifest repeats this source snapshot and the object-level hashes, making later spatial products traceable to the exact source bytes and governance state.

## Failure semantics

A version is reserved as `PENDING` before object writes. It becomes `COMPLETE` only after all raw objects and `manifest.json` are written. Exceptions mark the version `FAILED`; partial version-prefixed objects are never reused as a different dataset version. A repeated identical manifest with a non-complete record requires inspection rather than silently overwriting data.

## Resource limits

The worker enforces configurable limits for:

- maximum bytes per object;
- maximum total bytes per source harvest;
- maximum resources per source;
- HTTP timeout.

These limits protect the SIH development environment and public upstream services. They are operational safeguards, not statements about source completeness.

## Execution model

FastAPI exposes read-only version/readiness metadata. Long acquisition does not run inside an HTTP request handler. For the SIH deployment the logical `harvester-worker` is consolidated into the application image and invoked as a one-shot worker command:

```bash
docker compose exec api python -m floodguard.harvester.bootstrap --city-id kolkata
```

## Verification levels

```bash
python scripts/verify.py
python scripts/verify.py --services
python scripts/verify.py --bootstrap
```

The first checks code/tests, the second checks the running v0.3 platform and metadata APIs, and `--bootstrap` performs the explicit external-download completion gate. Sequence 3 is not formally frozen until the bootstrap gate creates at least one immutable Kolkata raw version and the full verification passes.
