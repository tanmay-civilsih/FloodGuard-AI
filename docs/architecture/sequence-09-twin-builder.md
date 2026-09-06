# Sequence 9 - Versioned static twin builder

Status: implementation complete; full clean-commit deployed gate pending. DATA-08-01 remains open.
The authoritative plan and approved final-human-review policy are unchanged.

## Objective and ownership

Freeze explicitly selected static components into one immutable twin version. Future forecasts
consume a twin_id, not independent latest-source lookups. This sequence computes no hydraulic
flows, forcing, surface grid bindings, forecasts, mass balance or operational controls.

The twelve manifest component fields are visual_terrain_version, hydraulic_terrain_version,
visual_city_version, hydraulic_surface_version, roof_runoff_geometry_version, drain_graph_version,
exchange_geometry_version, hydraulic_parameter_set_version, ward_version, catchment_version,
waterbody_version and pump_asset_version. Each is AVAILABLE with product/pipeline/scope/hash and
an exact snapshot artifact, or MISSING with a nonblank reason and no placeholder version.

The manifest also records twin_id, city_id, polygonal pilot_area and ward IDs, horizontal_crs,
vertical_reference_status, hydraulic_readiness, software_version, software_source_sha256, retained
source evidence, readiness blockers, real cross-ward support and pending final human acceptance.

## Selection, source integrity and assumptions

`TwinBuildRequest` requires exact terrain, urban GIS, drain and normalized spatial product IDs.
Optional absent terrain/urban/drain products require explicit reasons. Normalized ward, catchment
and waterbody selections are mandatory. There is no latest-product resolution at build or recreation.
Source adapters check city, metric CRS, pilot where applicable, category, current pipeline and each
artifact's integrity. Reference components cannot be substituted into a real pilot. Reviewed upstream
real GIS remains provisional at twin level because cross-component acceptance has not occurred.

The builder retains all selected terrain raw/visual/hydraulic/structure/QA/audit artifacts, urban
visual/hydraulic/roof/QA/audit products, all selected drain artifacts and normalized spatial working
geometry, QA and metadata. An unbound drain import draft is retained only as evidence; graph,
exchange and pump components remain MISSING. Pump absence is never inferred from an import draft.
A graph with explicit pump definitions supplies an asset snapshot derived from those definitions.

Every selected component is copied to immutable twin-owned content-addressed storage. Source copies
make existing twins independent of later upstream metadata, pipeline changes or source deletion.
They do not guarantee regeneration of the original remote datasets. Reconstruction here means exact
static twin assembly from the frozen manifest and its retained bytes, not recalibration or rerunning
all historical source conversion software.

## Identity and recreation

Policy `sequence-9-twin-v1` canonicalizes the full manifest with twin_id omitted, hashes it with
SHA-256, and derives twin_id with UUIDv5 namespace `ff25d5dc-6af4-46ad-b253-0c711b785fa7`.
Component versions bind their original product IDs, pipeline, scope and source-byte SHA-256.
`twins/blobs/{sha256}.json` stores opaque snapshot bytes, including retained binary terrain evidence;
the suffix is a storage convention and does not imply that raw binary evidence is JSON.
`twins/{twin_id}/manifest.json` and `audit.json` bind the manifest identity and software evidence.
Creation timestamps live in database records and do not change deterministic twin identity.

Any change to component bytes, selection, parameters, pilot, missing reason or software identity
creates a new twin. Shared blobs can be reused only when their exact bytes match. Manifest recreation
revalidates manifest identity, every component/evidence byte count and SHA-256, content-addressed
locations, cross-component checks and computed readiness. It preserves the original software identity
under the supported assembly policy, even when invoked by a newer reader. Unsupported policies fail.

Bootstrap proves recreation using a fresh empty SQLite twin metadata database and the retained blob
store, without any upstream service in the recreation service. The recreated twin ID and manifest
bytes must match the original; repeated recreation must reuse the identity. This is tested locally
and in the deployed container. Additive Alembic migration `0008_sequence_9_twin` owns twin metadata.

## Scientific consistency and readiness

No implicit unit or CRS transformations occur. Coordinates/lengths/elevations are metric; upstream
parameter units and surface hydrology ownership remain unchanged. Geometry coverage uses exact
Shapely predicates, with no new invented spatial tolerance. The drain assessment retains its own
explicit endpoint/ward tolerance. A rectangular terrain extent is only a provisional selection area,
not a claim that it is an accepted hydraulic catchment or its surrounding wards are all contained.

Checks include:

- terrain CRS, pilot coverage, nodata, matching visual/hydraulic source-frame metadata and upstream
  terrain readiness;
- valid spatial geometry, exact named ward membership and pilot/catchment/ward coverage;
- matching city/pilot/CRS/scope for the selected directed graph, exact normalized ward-byte identity,
  graph/exchange/pump agreement and reconstruction of real source bindings from retained bytes;
- drainage parameter artifact equality with graph inverts, storage, edge parameters and definitions;
- all Sequence 8 static assessment checks, including physical exchange coverage and cross-ward path;
- visual/hydraulic city schemas, surface ownership, exact roof policy coverage, valid receiving
  geometry and explicit drain targets present in the selected graph;
- parameter-set identity covering both drainage parameters and hydraulic surface hydrology policies;
- a common named metric vertical datum with compatible/transformed status across terrain and drain.
  Static outfall stages use the graph frame. No survey or datum transformation is fabricated.

Related component groups must use one source product version. Schema/identity/scope mismatch is an
error. Missing components or incomplete geographic/hydraulic evidence produce explicit blockers and
VISUAL_ONLY readiness. HYDRAULIC_SCENARIO_READY requires no component/scenario blockers.
The manifest supports the common readiness vocabulary but refuses HYDRAULIC_VALIDATED because the
builder does not perform independent scientific validation. HYDROLOGIC_READY upstream drains remain
below scenario-ready at twin level. No later simulation stability or hydraulic capacity adequacy is
claimed from static completeness.

## API and operator workflow

The API exposes GET-only `/twins/readiness`, `/twins/products`, `/twins/products/{twin_id}`,
`/twins/products/{twin_id}/manifest`, `/twins/products/{twin_id}/audit`, and component downloads
using the exact manifest field name. Complete frozen artifact verification precedes delivery.
Unknown IDs/components return 404, invalid UUIDs 422, integrity failures 409 and missing stored bytes
503. An explicitly MISSING component has no downloadable placeholder.

`/twins/qa` shows each exact component version or missing reason, readiness, datum state, software
identity, pilot and blockers. It has no mutation/approval actions and uses no remote assets.
Safe DOM text, request failures and stale selection behavior are covered by a Node harness;
no live-browser engineering acceptance is claimed.

```bash
python -m floodguard.twin.bootstrap
python -m floodguard.twin.build --request docs/examples/sequence-09-pilot-selection.json --dry-run
python -m floodguard.twin.build --request docs/examples/sequence-09-pilot-selection.json
python -m floodguard.twin.build --recreate-manifest saved-manifest.json --dry-run
python -m floodguard.twin.build --recreate-manifest saved-manifest.json
python scripts/verify.py --services --twin-bootstrap
python scripts/sequence9_development_gate.py --run-checks
```

Use `docker compose exec -T api` before Python commands requiring the deployed database/object-store
configuration. Dry-run reads and validates without persisting. The example pilot selection contains
exact existing version IDs and missing reasons. Selection and drain-binding JSON schemas are retained
under `docs/examples/`; the binding schema is not a real engineering plan or an approval record.

## Benchmarks and closure gates

The aligned reference contains 12 component versions: a controlled 12 x 8 terrain at 10 m spacing,
all eight surface classes with explicit roof receiving geometry, the six-node directed drainage
benchmark across two adjacent reference wards, static pump/storage/outfall definitions and coherent
catchment/waterbody geometry. Synthetic quantities stay labelled REFERENCE_FIXTURE.
The real Ward 7 twin stores actual terrain, wards, catchment and waterbodies; its 286-feature drain
draft is retained as evidence. Urban GIS, directed graph, exchange, complete parameters and pump
assets remain explicitly absent. It is VISUAL_ONLY and keeps unresolved geographic/datum evidence.

Assembly validation requires software tests, exact dependency/runtime/source identity, six healthy
services, additive migration, both deployed twins, empty-database recreation, artifact hash readback
and conditional-storage concurrency. Sequence freeze additionally requires at least one retained
real source-bound adjacent-ward drainage path to a defensible downstream destination.
`assembly_development_gate_passed` is separate from `technical_development_gate_passed`.
Checkpoint A is REFERENCE_ONLY until real cross-ward support exists. A real provisional milestone
still does not grant final human acceptance.

DATA-08-01 cannot be deferred with human-only review. If it remains open, the gate must report
NOT_FROZEN even after every assembly/software check passes. Sequence 10 must not start from a claimed
Sequence 9 freeze. Final source/component, geographic/vertical and visual acceptance remains in the
Sequence 20 human-review register and can reopen any affected twin version.
