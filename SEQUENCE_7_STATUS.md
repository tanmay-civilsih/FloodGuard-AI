# Sequence 7 status — TECHNICAL FREEZE CANDIDATE

Date: 6 September 2026  
Branch: `sequence-7-urban-gis`  
Base: Sequence 6 technical freeze `81749b59a73e64758418083589063f4717b81352`  
Release identity: `0.7.0` / Sequence `7`

## State

- Implementation: **COMPLETE**
- Focused automated scientific/unit validation: **PASSED**
- Source compilation: **PASSED**
- Full pinned Python 3.12/Ruff/mypy/repository/Docker/storage gate in this sandbox: **NOT AVAILABLE**
- Technical development freeze: **CANDIDATE — requires one pinned-runtime gate run**
- Final human acceptance: **PENDING SEQUENCE 20**
- `main`: intentionally untouched

This status does not claim real-pilot engineering acceptance, calibrated hydrology, or hydraulic validation.

## Delivered Sequence 7 contract

- Separate immutable visual-city and hydraulic-surface products.
- All eight frozen-plan hydraulic surface classes.
- Explicit hydraulic-domain ownership with Sequence 7 rejection of `NETWORK_1D` surface ownership.
- Mutually exclusive simplified-runoff vs explicit-loss hydrology policies.
- Engineering parameter provenance states retained in the contract.
- One versioned roof-runoff rule per roof.
- Receiving-geometry or explicit-drain-target policy; numerical `surface_cell_ids` are forbidden in Sequence 7.
- Roof generated-volume and transfer-conservation calculations with declared relative tolerance.
- Strict metric-CRS and topology validation using the existing spatial guardrails.
- Immutable create-only artifacts with SHA-256 verification on read.
- Sequence 7 migration, API, QA inspector, deterministic reference bootstrap, verifier integration and development gate.
- `REFERENCE_FIXTURE`, provisional-real and reviewed-real evidence scopes kept distinct.

## Immutable product contract

```text
urban-gis/{city_id}/{pilot_area_id}/{urban_gis_id}/
  visual_city.geojson
  hydraulic_surface.geojson
  roof_runoff.json
  qa.geojson
  audit.json
```

The audit explicitly records `surface_cell_ids_assigned = false`.

## Automated reference fixture

The controlled reference package exercises every Sequence 7 class without representing it as real Kolkata evidence:

- package SHA-256: `03b2390c74c767bc37007b28ec791381b4dfae05be4e5042a6cbde86e556801a`
- fingerprint: `81b1ad3ebc673871344c1841e3677cc044b957f73958705e03bc47024a83dad5`
- deterministic `urban_gis_id`: `4346f39d-77a5-5a25-9dcb-2c4eb6bb027c`

## Sandbox validation executed

A local shadow of the Sequence 7 contracts/service/reference/development-gate logic was executed with the dependencies available in this environment.

Results:

```text
13 passed
python -m compileall: PASSED
```

The focused cases cover:

1. all eight hydraulic classes;
2. visual/hydraulic representation separation;
3. hydraulic-domain ownership rejection rules;
4. mutually exclusive hydrologic-loss modes;
5. roof-rule completeness;
6. rejection of premature `surface_cell_ids`;
7. versioned roof receiving geometry;
8. effective-rain and roof-volume calculations;
9. conservation failure detection;
10. immutable/idempotent product creation;
11. SHA-256 corruption failure;
12. CRS mismatch rejection;
13. reference-ready development-gate classification without false final acceptance.

Sandbox runtime limitations:

- Python: `3.13.5`, not the required `3.12.x`;
- Pydantic/Shapely/PyProj matched the versions used by the focused work;
- sandbox SQLAlchemy was `2.0.50`, while the repository lock declares `2.0.52`;
- Ruff and mypy are not installed/cached and network installation is unavailable;
- Docker/services/MinIO are unavailable in this sandbox;
- therefore the new Sequence 7 full pinned gate has **not** been truthfully claimed as passed here.

The previously supplied Sequence 6 local evidence established a healthy Python 3.12 environment, full-suite baseline, services and real MinIO conditional-write concurrency for the predecessor branch. That evidence is useful continuity, but it is not substituted for the new Sequence 7 gate.

## Required final technical-freeze gate

Run on a clean pinned checkout after pulling this branch:

```text
python scripts/sequence7_development_gate.py --run-checks
```

That single command executes the repository verifier with Sequence 7 service/reference bootstrap, Ruff, mypy, the complete pytest suite, API/source/runtime checks and the real conditional-storage concurrency probe.

A zero exit with:

```text
development_status = PASSED
technical_development_freeze_status = ELIGIBLE
freeze_status = TECHNICAL_DEVELOPMENT_FREEZE_ELIGIBLE
```

is the required evidence to change this file from `TECHNICAL FREEZE CANDIDATE` to `TECHNICAL_DEVELOPMENT_FROZEN`.

## Deferred human review

Real-pilot visual geometry/source acceptance, hydraulic surface classification/domain ownership, every real roof receiving geometry/drain target, and exact-browser artifact acceptance are registered in `docs/validation/final-human-review-register.md` as HR-07-01 through HR-07-04.

They do not block implementation of Sequence 8 under the owner-approved deferral policy once the automated technical gate is green, but they must be closed during Sequence 20 before final scientific/engineering acceptance.
