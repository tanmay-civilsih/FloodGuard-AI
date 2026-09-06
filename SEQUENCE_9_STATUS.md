# Sequence 9 - IMPLEMENTED AND VERIFIED; FREEZE BLOCKED

Date: 6 September 2026
Branch: `sequence-9-twin-builder`
Release: `0.9.0`
Assembly validation: **PASSED**
Sequence freeze: **NOT_FROZEN**
Final acceptance: **FINAL_HUMAN_ACCEPTANCE_PENDING**

The versioned twin builder is implemented, locally deployed and verified end to end.
Its complete clean-commit gate has exactly one freeze blocker: DATA-08-01. A genuine real
source-bound drainage path across adjacent wards to a defensible destination is still absent.
This objective data/model requirement cannot be deferred to Sequence 20 with human-only review.
Sequence 9 is therefore not marked TECHNICAL_DEVELOPMENT_FROZEN. The owner subsequently
authorized Sequence 10 implementation after this blocker was reported; see SEQUENCE_10_STATUS.md.

## Validated implementation and evidence

- Implementation commit: `6477175c5c02ee7693aa548a7e1c50478c7362ec`.
- Local/API source fingerprint: `b54ff96498f199d998f1903d6403bfa728c8afa04006d5a1e6fd319483ff61ff`.
- Complete gate report: `docs/validation/sequence-09-development-gate-6477175.json`.
- Full transcript: `artifacts/validation/sequence9-6477175/development-gate.log`.
- Report retained byte-for-byte from the clean implementation baseline. Later evidence/documentation
  changes do not alter the release source fingerprint.
- Predecessor: Sequence 8 technical freeze `8412eb7`, validated source `de6cce9`.

| Check | Result |
|---|---|
| Local runtime/dependency lock | Python 3.12.10; exact pinned dependencies |
| Ruff | Passed |
| Strict mypy | 136 source files; no errors |
| Full pytest suite | 671 passed, 1 skipped in 47.32 seconds; no deselection |
| Skip | Windows symlink creation permission unavailable |
| API/runtime/source parity | Sequence 9 / v0.9.0, Python 3.12.11; exact source fingerprint, no lock mismatch |
| Platform | api, postgres, redis, nats, minio, traefik healthy |
| Migration | 0008_sequence_9_twin at Alembic head |
| Assembly/recreation | Reference and real twin recreated in an empty metadata database with identical IDs and manifest bytes |
| Immutable reuse | Repeated recreation reused existing twin identity |
| HTTP artifact readback | 21 artifacts across the two committed-source twins matched byte count and SHA-256 |
| Retained source evidence | 24 evidence-artifact references verified as part of complete twin verification (4 reference, 20 real) |
| Conditional storage | Each bucket: 8 concurrent writers, 1 creation, 7 rejections |
| QA behavior | Node DOM harness passed safe text, rendering, failure clearing and stale-selection checks |
| Real two-ward freeze gate | BLOCKED: no source-bound real graph/path/destination product |
| Live browser acceptance | Not performed or claimed; remains human review |

The final gate exits 1 because freeze is blocked, while `assembly_validation_status=PASSED`,
`software_and_services_passed=true` and `deployed_conditional_storage_passed=true` remain explicit.
This is an unmet scientific data requirement, not a hidden software test failure.

## Completed interface

The twin manifest names every one of the twelve required static component versions, the exact
polygonal pilot, city, horizontal CRS, vertical-reference status, computed readiness and software
identity. Every component is AVAILABLE with immutable source/artifact hashes or MISSING with a reason.
Visual/hydraulic products remain separate. Hydraulic parameter identity includes both drainage
parameters and surface hydrology policies; pump assets derive only from the selected static model.

Explicit source adapters verify exact current product IDs, city/pilot/CRS/category/scope and source
artifacts. The twin retains component and evidence bytes in its own immutable snapshot. Recreation
requires no upstream latest lookups or existing twin database record. Changed inputs/software create
new identities; missing or corrupt bytes, relabelled identity and invalid component combinations fail.

The implementation includes source-linked ward/drain checks, roof-target checks, static parameter
consistency, conservative datum/coverage/readiness, additive persistence, read-only API/QA, explicit
operator build/recreate commands, JSON schemas, exact pilot selection and the full development gate.
It computes no hydraulic flow/forecast and never assigns HYDRAULIC_VALIDATED or surface-cell IDs.

See `docs/architecture/sequence-09-twin-builder.md` for all inputs, outputs, units, assumptions,
identity algorithm, failure behavior, scope limits and operator commands.

## Exact twins built from the committed source

| Twin | ID | Components and readiness |
|---|---|---|
| Aligned controlled reference | 0d72c671-314e-5753-a015-cf26cf260377 | 12 available components; HYDRAULIC_SCENARIO_READY; no real validation claim |
| Actual Ward 7 snapshot | a73bc1b5-ec4e-5291-825f-aed596d97999 | 5 available, 7 explicitly missing; VISUAL_ONLY |

The object store also retains two earlier development twin versions. The final gate records the
two exact committed-source twins above; older versions are preserved rather than overwritten.

Real available components: visual terrain, hydraulic terrain, wards, catchments and waterbodies.
The 104 drains, 84 structure candidates and 98 labels remain source draft evidence, not a graph.
Real missing components: visual city, hydraulic surface, roof runoff geometry, directed drain graph,
physical exchange component, complete hydraulic parameter set and pump assets. The selected terrain
is not scenario-ready, a common terrain/drain/boundary datum is unresolved, and the provisional
rectangular pilot extent extends beyond its selected ward union. These are explicit visual-only
blockers; a stored twin does not promote any of them to accepted engineering evidence.

The reference has all twelve controlled components, a 12 x 8 synthetic terrain at 10 m spacing,
eight hydraulic surface classes, a five-edge drainage path across adjacent synthetic wards, both
mandatory exchanges, static pump/storage/outfall definitions and coherent receiving geometry.
No synthetic asset, direction, elevation or destination has been substituted into the real pilot.

## Remaining freeze action: DATA-08-01

The live source inventory was checked: the approved Ward 7 reconstruction contains unassigned
engineering fields and raw labels, but no accepted source-bound directed graph or explicit real
outfall/downstream destination product. The source label catalogue contains invert/dimension
annotations; assigning them to assets without supporting bindings would invent engineering evidence.
The existing repository evidence contains no supplied real binding plan that can close this gate.

1. Supply defensible real source evidence and an explicit binding plan for a drain path crossing
   actual adjacent ward polygons and continuing to a documented downstream destination.
2. Validate/apply that plan through the existing Sequence 8 import CLI; retain missing parameters,
   direction/classification provenance, physical exchange geometry and exact source hashes.
3. Select the resulting immutable directed graph in a new twin request, with a compatible pilot
   declaration. Never edit an existing twin's graph reference or pretend the old draft is directed.
4. Rebuild/recreate the real twin and run the full Sequence 9 clean-source deployed gate.
5. Mark the sequence technically frozen only after that gate has no blockers. Human-only acceptance
   remains pending Sequence 20 under HR-08 and HR-09; no later scientific validation is inferred.

The exact pilot selection and schemas are in `docs/examples/`. A concise fresh-chat handoff is
`SEQUENCE_9_CONTINUATION.txt`. The original Sequence 9 task did not start Sequence 10 or change the frozen plan. The subsequent
owner-authorized development exception is recorded in SEQUENCE_10_STATUS.md.

## Repository/deployment boundary

All changes and gate evidence are local. `main` remains the Sequence 5 baseline; no remote push,
merge-to-main, hosted release, human sign-off or final Checkpoint A acceptance is claimed.

Inspect `http://localhost:8000/twins/qa` and `/twins/readiness?city_id=kolkata`.
Re-run the gate using `python scripts/sequence9_development_gate.py --run-checks` from a clean checkout
against the rebuilt matching API. It is expected to remain NOT_FROZEN until DATA-08-01 is resolved.
