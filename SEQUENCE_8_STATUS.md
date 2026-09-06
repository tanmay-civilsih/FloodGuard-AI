# Sequence 8 - TECHNICAL_DEVELOPMENT_FROZEN

Date: 6 September 2026
Branch: `sequence-8-drain-model`
Release: `0.8.0`
Final acceptance: `FINAL_HUMAN_ACCEPTANCE_PENDING` (Sequence 20)

Sequence 8 technical development is closed under the approved two-stage execution policy.
The complete clean-commit deployed gate passed with no technical blockers. This freezes the
implementation/interfaces for continued development; it does not claim real-pilot scientific
completion or hydraulic validation.

## Validated baseline

- Implementation commit: `de6cce9cafc732be93ecb4af6505877d721631c1`.
- Release source fingerprint: `f30279ca8c98d4ab79ffc607580b2cb5f4a0ce0f9a4481b73980b90d9edb895a`.
- Gate report: `docs/validation/sequence-08-development-gate-de6cce9.json`.
- Full transcript: `artifacts/validation/sequence8-de6cce9/development-gate.log`.
- Report generated from the clean implementation commit; subsequent closure-document changes do
  not change the release source fingerprint. The report is retained byte-for-byte.
- Predecessor: Sequence 7 technical freeze `11ed8fc`, validated source `318ec92`.

## Completed implementation

- Typed graph with all six node types, four edge types and NETWORK_1D ownership.
- Frozen direction priority, conflict guards and explicit versioned hydraulic parameter gaps.
- POINT_INLET and MANHOLE_SURCHARGE physical exchange geometry; no numerical surface-cell IDs.
- Exact reconstruction/current-ward import with hashes, CRS, feature identity and preserved source
  bytes; explicit source geometry bindings for directed construction.
- Polygon-based ward membership/adjacency/path checks and source-linked downstream definitions.
- Static pump curves, storage area/depth curves and free/fixed-stage outfall definitions.
- VISUAL_ONLY, HYDROLOGIC_READY and HYDRAULIC_SCENARIO_READY assessment; no HYDRAULIC_VALIDATED
  assignment. Topological paths are not hydraulic solutions.
- Immutable products, artifact manifests, corruption/reuse guards and additive database migration.
- Read-only API, metric geometry QA viewer, explicit import/binding CLI and reproducible bootstrap.
- Complete development gate with pinned runtime/source checks, software tests, service health,
  exact product HTTP readback and deployed conditional-storage concurrency.

Interface, assumptions, units, numerical tolerances, failure behavior and commands are documented in
`docs/architecture/sequence-08-drain-model.md`.

## Verified gate evidence

| Check | Result |
|---|---|
| Local runtime | Python 3.12.10; no dependency-lock mismatches |
| Ruff | Passed |
| Strict mypy | Passed; 122 source files |
| Pytest | 568 passed, 1 skipped in 37.04 seconds; no deselection |
| Skip | Windows symlink creation permission unavailable |
| Deployed API | Sequence 8 / v0.8.0, Python 3.12.11; exact source fingerprint and dependency lock matched |
| Services | api, postgres, redis, nats, minio, traefik healthy |
| Migration | 0007_sequence_8_drain_model at Alembic head |
| Existing-source/reference bootstrap | Passed; repeat execution reused both immutable products |
| HTTP artifact integrity | All 15 artifacts across both products matched stored sizes and SHA-256 |
| Conditional storage | Each bucket: 8 concurrent writers, 1 creation, 7 rejections |
| QA behavior | Node DOM harness passed rendering, error clearing, safe source text and stale-selection tests |
| Live browser visual review | Not performed; no browser surface available; HR-08-05 remains open |

Predecessor readiness was checked after deployment. Sequence 7 retains its ready reference product.
The real Sequence 6 terrain remains VISUAL_READY; it was not promoted by drain-model development.

## Exact products

| Product | ID | State |
|---|---|---|
| Real Ward 7 import | 30c05f00-2ab5-5aea-a640-5275711ce127 | REAL_PILOT_PROVISIONAL / VISUAL_ONLY; 104 drains, 84 structure candidates, 98 labels |
| Controlled directed reference | 898df152-6437-55ba-9ff4-bcdb430a4a00 | REFERENCE_FIXTURE / HYDRAULIC_SCENARIO_READY; 6 nodes, 5 edges, 2 exchanges |

The reference has a 50 m path across adjacent synthetic wards to a defined receiver, all required
static parameters, a pump curve and a consistent 20 m3 storage. It is not Kolkata hydraulic evidence.

Real-source anchors:

- Reconstruction `4fea299c-e2ea-5a11-ae98-eaff9649c6da`, working SHA-256
  `5cda954e5d61d2f2191b63c80e19efdb99848c4ecaafa6fcffa90ee0d5e351b6`.
- Ward normalization `acff42f4-d7a0-5bed-bcdc-28d5ed740b63`, working SHA-256
  `da962cba8ec62bdf45e86a70d403880532f880f205e437aa5dc678dabc74d65a`.

Every downstream artifact hash, size and product fingerprint is in the retained gate report.

## Explicit remaining constraints

**DATA-08-01 remains OPEN and must be resolved before Sequence 9 closes.** There is no source-bound
real directed graph or verified genuine cross-ward path yet. Source features intersect wards 7, 8,
10 and 12, while three intersect no ward polygon. Those geometric observations are not connectivity,
flow direction, node classification or a defensible downstream destination. No missing engineering
values, review identity, survey datum or outfall acceptance were invented.

The next sequence may develop/test its builder with the frozen reference and clearly provisional
inputs under the owner-approved policy. It may not declare its real two-ward completion gate passed
until genuine source-bound continuation and downstream evidence exist and pass assessment.

HR-08-01 through HR-08-05 remain pending Sequence 20 for exact real asset, parameter, definition,
exchange and visual engineering acceptance. See `docs/validation/final-human-review-register.md`.
DATA-08-01 is a data/model requirement, not a human-only item postponed to Sequence 20.
All final-completion and hydraulic-validation claims remain false.

## Continuation and repository boundary

Continue from this branch and verify live status before starting Sequence 9. No Sequence 9 code was
implemented in this closure task. `main` remains the Sequence 5 baseline `ae41a2a`; these are local
implementation and evidence commits, with no remote push, merge-to-main or hosted release claimed.

Re-run the complete gate from a clean checkout against a rebuilt matching API:

```bash
python scripts/sequence8_development_gate.py --run-checks
```

Inspect stored products at `http://localhost:8000/drainage/qa` and readiness at
`http://localhost:8000/drainage/readiness?city_id=kolkata`.
