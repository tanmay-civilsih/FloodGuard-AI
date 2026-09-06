# Spatial integrity policy revision: sequence-4-v2

The Sequence 6 audit found that source hashes were copied into normalization fingerprints
without checking the bytes read from storage. Processing now verifies SHA-256, actual byte
length and limits before either a new build or an idempotent reuse. Object/version ownership
is checked explicitly. Reuse also verifies the current working and QA products.

The `sequence-4-v2` fingerprint creates new immutable products under new keys. A verified working
artifact now anchors the QA checksum and length through `floodguard_integrity`. Its complete
bytes are covered by the existing database `normalized_sha256`. No migration is required.
Historical artifacts are preserved, but a missing integrity envelope or old policy returns
HTTP 409 and requires normalization from the original source. Corrupt objects are not repaired
in place. Reconstruction QA HTTP responses are checked against their existing recorded hash.

## Rebuild after pulling

```text
docker compose up -d --build
docker compose exec -T api python -m floodguard.spatial.bootstrap --city-id kolkata
```

The stricter geometry checks can expose invalid real source features previously accepted.
Those need explicit source QA; do not silently repair them merely to make a gate pass.

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
as substitutes for engineering evidence. A complete cross-layer assessment workflow remains
an open acceptance item, not a claimed implemented validation.

## Validation scope

Eleven isolated byte/pair integrity regression tests passed. Database-backed ingestion/reuse/
readiness tests are included for the pinned-runtime suite but were not run in this restricted
sandbox. The pre-existing spatial tests must also pass after rebuilding in Python 3.12.
