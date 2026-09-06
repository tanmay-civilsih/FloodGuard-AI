# Spatial integrity policy revision: sequence-4-v3

The Sequence 6 audit found that source hashes were copied into normalization fingerprints
without checking the bytes read from storage. Processing verifies SHA-256, actual byte
length and limits before either a new build or an idempotent reuse. Object/version ownership
is checked explicitly. Reuse also verifies the current working and QA products.

The current `sequence-4-v3` fingerprint creates new immutable products under new keys. A verified
working artifact anchors the QA checksum and length through `floodguard_integrity`; its bytes are
covered by the database `normalized_sha256`. Historical v1/v2 artifacts remain preserved but do not
satisfy the current integrity policy and must be rebuilt from immutable raw source bytes.

## Municipal ward self-intersection policy

Strict topology validation exposed a real KMC/OpenCity ward polygon with a ring self-intersection.
The validator has **not** been weakened. Generic invalid topology is still rejected. For the
`WARD_BOUNDARY` category only, v3 permits one narrowly defined source repair:

1. the source must be a Polygon or MultiPolygon;
2. GEOS must report `Self-intersection` or `Ring Self-intersection`;
3. `make_valid(method=linework)` must return a nonempty valid Polygon/MultiPolygon;
4. the repaired boundary Hausdorff distance and envelope delta must remain within a tiny source-CRS
   tolerance (1e-9 degree for geographic input or 1e-6 m for projected input);
5. otherwise normalization fails and requires human source QA.

This operation reinterprets crossing source linework into valid polygon topology; it is not allowed
to shift, smooth, buffer, simplify, snap, or close arbitrary geometry. Each repaired feature carries
`_floodguard_topology_repair` with the GEOS reason, method, geometry types, linework/envelope
diagnostics and acceptance tolerance. The working integrity envelope records that this policy was
enabled. A source property using that reserved provenance name is rejected.

Other errors—holes outside shells, malformed rings, unsupported geometries, nonfinite coordinates,
collapsed results, changed linework/envelopes—remain hard failures. A successful numerical repair is
still subject to visual/cross-layer engineering QA and is not independent evidence of alignment.

## Rebuild after pulling

```text
docker compose up -d --build
docker compose exec -T api python -m floodguard.spatial.bootstrap --city-id kolkata
```

## Readiness semantics

Only current-CRS products whose working/QA pair verifies count as eligible layers. Historical
or unverified layers remain in inventory and are counted separately. A failed storage operation
must not be interpreted as valid data.

For compatibility, `alignment_check_passed` retains its former numerical meaning and is
explicitly labelled `alignment_check_scope=NUMERICAL_ROUNDTRIP_ONLY`. New clients use
`numerical_roundtrip_check_passed`. Neither proves cross-layer alignment;
`cross_layer_alignment_status=NOT_ASSESSED` is explicit until independent evidence is governed.
Likewise `elevation_metadata_status=NOT_APPLICABLE_NO_ELEVATION` explains the former vacuous
metadata boolean, and `rainfall_conservation_scope=SYNTHETIC_SELF_TEST` distinguishes the fixed
numerical benchmark from a validated rainfall product. A freeze must not use the legacy booleans
as substitutes for engineering evidence.

## Validation scope

The v3 repair path has dedicated regression tests proving default rejection, bounded self-intersection
repair, rejection of other topology errors, reserved-provenance protection, and KML parity. The real
Kolkata ward source must be rebuilt and visually inspected; passing the repair guard alone is not
engineering acceptance.
