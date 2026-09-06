# Sequence 8 - Directed drain model, parameters, exchange geometry and readiness

Status: implementation complete; full clean-commit deployed development gate pending.
See `SEQUENCE_8_STATUS.md` for the current evidence and freeze state.
The authoritative scientific specification is unchanged.

## Scope and ownership

Sequence 8 represents nominal directed drainage connectivity and static hydraulic parameters.
It computes no flow, hydraulic state, surface runoff, surcharge volume or forecast.
Nodes are INLET, MANHOLE, JUNCTION, STORAGE, PUMP and OUTFALL. Edges are PIPE, OPEN_DRAIN,
CULVERT and CANAL, owned by NETWORK_1D. POINT_INLET and MANHOLE_SURCHARGE are physical
exchange point geometries with matching x/y, node identity, rim, area, coefficient, capacity,
inlet type, source and confidence. Surface cell IDs are forbidden; binding belongs to Sequence 11.
LINEAR_OVERTOP remains unimplemented unless pilot evidence requires distributed overtopping.

## Frozen input contracts

`DrainGraphPackage` owns the graph and parameter contracts. `DrainModelInput` adds exact ward
polygons and versioned static pump/storage/outfall definitions. `ImportSourceInfo` identifies
an exact approved Sequence 5 reconstruction and current Sequence 4 ward normalization by UUID,
object key, SHA-256, city, pilot and metric CRS. `ImportBindingPlan` binds every directed model
node and edge to features in an exact import draft and fingerprint.

Every important scalar uses a value, SI unit, status and version. Missing values retain a reason
and no numeric substitute. Known values retain a source. INFERRED, ASSUMED and CALIBRATED also
require a method; optional bounds must contain the value. Supported statuses remain MUNICIPAL,
MEASURED, GIS_DERIVED, LITERATURE, INFERRED, ASSUMED, CALIBRATED and MISSING.
Lengths/elevations are m; areas m2; storage m3; capacities m3/s; slope/coefficient dimensionless;
Manning roughness s/m^(1/3). No silent unit conversion is performed.

Direction priority is municipal arrows/labels, inverts, pump/outfall topology, hydraulic/topological
inference, then LOW-confidence terrain fallback. Contradictory strongest-priority evidence fails.
Invert-based direction requires known descending endpoint inverts and compatible/transformed metric
datum metadata. Nominal orientation does not prohibit later Dynamic Wave reverse flow.

## Source import and binding

The loader verifies the existing reconstruction raw PDF, working geometry, QA and audit bytes, plus
the normalized ward product through its current-pipeline integrity contract. It performs no external
acquisition. Import verifies source hashes, bounded unambiguous JSON, CRS, unique feature/ward IDs,
reconstruction identity, geometry and feature kinds. It retains source geometry/properties unchanged
and computes ward intersections. Intersections are spatial diagnostics, not hydraulic connections.

An IMPORT_DRAFT is always VISUAL_ONLY with direction_assigned=false and connections_inferred=false.
Source labels are not converted into engineering values, and nearest-drain associations are not
accepted as hydraulic topology. Out-of-ward features remain visible with an explicit count.

A directed graph requires an explicit binding plan. Every node binds to a point, line endpoint or
position on a source drain, and each edge must be covered by its named source drain linework.
Labels cannot serve as node geometry. The default metric endpoint/binding tolerance is 0.01 m,
explicitly stored in each package and bounded at 1 m. It permits numerical endpoint alignment;
it does not grant engineering classification or permission to bridge missing source linework.
A graph may use a subset of candidates. `binding-coverage` lists unbound source drains and states
that referenced features may be only partially used. Full source coverage is never inferred.

## Static assessment and numerical rules

`sequence-8-readiness-v1` revalidates the input before every assessment. Directed breadth-first search
produces deterministic minimum-hop paths to declared outfalls, permits cycles, and lists unreachable
nodes, missing exchange coverage and each missing hydraulic parameter.

Node ward IDs must match actual polygon coverage. Same-ward edges must remain in that ward. For a
cross-ward edge, polygons must share a boundary longer than the endpoint tolerance, have overlapping
area no greater than tolerance squared, and the line must cross the shared boundary, remain within
the pair's union (buffered by endpoint tolerance) and have positive length greater than tolerance in
both wards. A qualifying path also needs a matching versioned receiving-destination definition at its
outfall. Reference geometry can pass this geometric test but never counts as real-pilot evidence.

Pump definitions carry an explicit enabled state and a head/discharge curve with increasing head,
nonincreasing discharge and positive capacity somewhere. Storage definitions carry increasing depth
and positive plan area, beginning at depth zero. Storage volume is the trapezoidal integral of the
piecewise-linear area/depth curve and must agree with the scalar storage volume within
`1e-9 * max(curve_volume_m3, 1)` m3. This is a static arithmetic consistency tolerance, not hydraulic
mass-balance validation. Outfalls retain destination ID/kind, receiving geometry and FREE or
FIXED_STAGE boundaries; fixed stages require an elevation parameter in the graph's vertical frame.
Dynamic schedules, forcing time series and solver execution remain later-sequence work.

| Readiness | Required evidence |
|---|---|
| VISUAL_ONLY | Valid stored geometry; unresolved topology/definitions/exchanges stay explicit |
| HYDROLOGIC_READY | All nodes reach outfalls; ward geometry, static definitions and inlet/manhole exchange coverage pass |
| HYDRAULIC_SCENARIO_READY | Hydrologic checks plus all required scalar parameters, metric comparable datum, consistent storage volume, and rim not below invert |
| HYDRAULIC_VALIDATED | Never assigned by Sequence 8; requires later independent scientific validation |

Parameter completeness does not establish capacity adequacy, surveyed accuracy, a usable hydraulic
forcing package, accepted operations or simulation stability. Shared datum metadata asserts an input
frame; Sequence 8 does not perform or independently verify a survey datum transformation.

## Immutable products and API

Pipeline `sequence-8-drain-model-v1` fingerprints canonical bounded JSON input, product kind and
pipeline version. UUIDv5 product IDs are deterministic. SQL metadata use additive Alembic migration
`0007_sequence_8_drain_model`, and object storage owns immutable `drainage/{product_id}/{kind}.json`.

Drafts retain input, source copies, candidate draft, wards, QA and audit. Directed models retain input,
graph, parameters, exchanges, assessment, wards, QA and audit; bound models also retain both exact
source copies and binding coverage. The audit records input lineage, pipeline, evidence scope and
artifact hashes. Existing artifacts require identical bytes on reuse; every byte count/hash is
verified before database registration and on product verification. Concurrent metadata registration
reuses the unique fingerprint. Corruption, missing artifacts or relabelled identity block reuse and
readiness. HTTP artifact reads verify the complete product before returning any component.

The read-only API exposes `/drainage/readiness`, `/drainage/products`,
`/drainage/products/{product_id}`, `/drainage/products/{product_id}/{kind}` and `/drainage/qa`.
There are no HTTP acquisition, graph-construction or approval actions. The QA viewer uses same-origin
artifacts and a metric SVG plan view, with no external map dependency. Product selection displays
exact identity, scope, readiness, diagnostics and download links. Failed or stale requests clear or
preserve the correct selection; source text is inserted as text, never executable HTML.

## Operator commands

```bash
python -m floodguard.drainage.bootstrap --city-id kolkata --ward-id 7
python -m floodguard.drainage.import_model --city-id kolkata --ward-id 7 --dry-run
python -m floodguard.drainage.import_model --binding-plan reviewed-binding.json --dry-run
python -m floodguard.drainage.import_model --binding-plan reviewed-binding.json
python scripts/sequence8_development_gate.py --run-checks
```

Use the existing Docker API container for commands requiring its database/object-store configuration,
for example `docker compose exec -T api python -m floodguard.drainage.bootstrap`.
Dry-run does not persist products. The binding-plan JSON schema is available through
`ImportBindingPlan.model_json_schema()`; the tests contain a complete controlled binding example.
Operator execution records supplied evidence, not human approval.

## Development gate and remaining real evidence

The controlled reference exercises every node/edge type, both mandatory exchanges, a 50 m directed
path across adjacent synthetic wards, a pump curve, a 20 m3 storage, and a defined free receiver.
All reference engineering values are ASSUMED with explicit fixture provenance. The real import uses
the approved Ward 7 reconstruction and current normalized ward polygons. Its 104 drains, 84 structure
candidates and 98 labels remain VISUAL_ONLY; geometry intersects wards 7, 8, 10 and 12, while three
features intersect no source ward. These intersections do not prove genuine hydraulic continuation.

The full gate requires a clean committed checkout, Python 3.12, exact dependency lock, all software
tests, six healthy deployed services, matching API/source fingerprint, reference and real import
bootstrap/reuse, complete HTTP artifact hash readback, and deployed conditional-storage concurrency.
QA JavaScript is tested with a Node DOM harness; live browser visual acceptance is a separate pending
item. No browser surface was available during this run.

The owner-approved two-stage policy permits reference/provisional development while human-only
acceptance accumulates for Sequence 20. It does not revise the frozen scientific criterion. Actual
source-bound adjacent-ward connectivity to a defensible destination remains an explicit requirement
before Sequence 9 closes. Real asset classification, directions, parameters, vertical datum,
exchange coverage and downstream definition must be supplied and assessed; their absence must not be
relabelled as successful human review. See the final-human-review register and Sequence 8 status.
