# Sequence 8 — Directed drainage model and physical exchange geometry

Status: development in progress, following the Sequence 7 technical freeze recorded in
`SEQUENCE_7_STATUS.md`. The authoritative scientific specification is unchanged.

## Increment 8.1: typed graph and deterministic topology inspection

This increment accepts an explicitly supplied directed drainage graph and reports its declared
connectivity and missing hydraulic parameters. It establishes contracts for the later importer,
immutable product service, readiness assessment, API and reference bootstrap.

Inputs are versioned source references, metric node/edge geometry, declared ward IDs, direction
evidence, explicit engineering parameters, vertical-reference metadata and physical exchange points.
Outputs are a validated graph package and deterministic paths to declared outfalls, ward transitions,
unreachable nodes and parameter-gap diagnostics. No numerical hydraulic solution is produced.

### Contracts and ownership

- Nodes: INLET, MANHOLE, JUNCTION, STORAGE, PUMP, OUTFALL.
- Edges: PIPE, OPEN_DRAIN, CULVERT, CANAL; edges are owned by NETWORK_1D.
- Baseline exchanges: POINT_INLET and MANHOLE_SURCHARGE, stored as point geometry and matching x/y.
- LINEAR_OVERTOP remains outside this increment until the real pilot demonstrates its need.
- Surface cell IDs are forbidden. Grid binding belongs to Sequence 11.
- Every scalar parameter carries its unit, provenance status and version. Missing values require
  an explicit reason. Known values require a source; inferred, assumed and calibrated values also
  require a method. Optional uncertainty bounds must contain the supplied value.
- Elevations/lengths use m, areas m2, volumes m3, capacity m3/s, slope and coefficients 1,
  and Manning roughness s/m^(1/3). Unsupported implicit unit conversion is rejected.
- Pump and outfall definitions are versioned source references at this stage; these references do
  not establish that a pump curve, control schedule or downstream boundary series is executable.

### Direction and geometry rules

Direction evidence follows the frozen priority: municipal arrows/labels, invert elevations,
pump/outfall topology, hydraulic/topological inference, then low-confidence surface terrain.
Conflicting candidates at the strongest available priority fail rather than selecting an arbitrary
direction. Edge endpoints and ordered line geometry must agree within the package's declared
metric endpoint tolerance (default 0.01 m). Geometry is validated using the existing spatial guards.

Invert-based direction requires known endpoint inverts and a compatible or explicitly transformed
metric vertical reference. This is nominal graph orientation, not a prohibition on later Dynamic
Wave reverse flow. The increment neither transforms elevations nor infers direction from a DEM.

### Topology diagnostics and claim limits

Directed breadth-first search finds a reproducible minimum-hop path from each node to a declared
outfall. Cycles are permitted. No flow, capacity adequacy, flood forecast or hydraulic readiness
is inferred from path existence. Missing outfalls and disconnected/dead-end components remain
visible in unreachable-node diagnostics.

A transition between supplied ward IDs is labelled DECLARED_WARD_IDS_ONLY. It cannot prove that
wards are adjacent, that geometry crosses their real boundary, or that an outfall is defensible.
Genuine cross-ward continuation requires exact normalized ward geometry and reconstruction/source
lineage in later increments. It remains mandatory before Sequence 9 can be completed.

### Verification

Deterministic cases cover a connected inlet/manhole/outfall network, branching/dead-end networks,
cycles, missing downstream destinations, strongest-priority direction conflicts, unresolved datum,
wrong units, explicit missing parameters, invalid references/geometry and premature cell binding.
These are synthetic contract/topology benchmarks, not Kolkata engineering acceptance.

## Remaining Sequence 8 increments

1. Source-bound import and reviewable graph construction from real reconstruction/normalized layers;
   preserve missing engineering attributes and source hashes instead of inventing them.
2. Hydraulic parameter and readiness assessment, including pump/storage/outfall definitions and
   explicit parameter gaps; no HYDRAULIC_VALIDATED promotion without scientific evidence.
3. Immutable graph/parameter/exchange/QA/audit products, migration, service and read-back integrity.
4. API/QA, deterministic reference bootstrap and complete pinned-runtime development gate.
5. Exact real cross-ward geometry/downstream-destination evidence and the relevant final review
   register entries. Human-only acceptance may follow the approved Sequence 20 policy; a claimed
   real cross-ward path may never be substituted with invented ward names or synthetic geography.

Sequence 8 is not technically frozen by completion of increment 8.1. The runtime remains the
validated Sequence 7 API until a later Sequence 8 integration increment is ready for deployment.
