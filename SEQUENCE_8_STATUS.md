# Sequence 8 — DEVELOPMENT IN PROGRESS

Date: 6 September 2026

Branch: `sequence-8-drain-model`

Predecessor technical freeze: `11ed8fc` (Sequence 7 status/evidence), validated source `318ec92`.

## Current scope

Increment **8.1 — typed drainage graph and deterministic topology inspection** is implemented and
locally verified. Sequence 8 as a whole is **not frozen**.

Implemented files:

- `floodguard/drainage/contracts.py`
- `floodguard/drainage/topology.py`
- `tests/drainage_fixtures.py`
- `tests/test_drainage_contracts.py`
- `tests/test_drainage_topology.py`

The architectural plan and remaining increments are in
`docs/architecture/sequence-08-drain-model.md`.

## Implemented behavior

- Six node types, four edge types and explicit NETWORK_1D ownership.
- Versioned engineering parameters with units, provenance, missing reasons and optional bounds.
- Named geometry, roughness, slope, capacity, storage and pump/outfall/condition-reference fields.
- Frozen-plan direction priority and rejection of contradictory strongest-priority evidence.
- Metric geometry, endpoint alignment, source-identity and datum guards.
- Physical POINT_INLET/MANHOLE_SURCHARGE contracts with geometry, x/y, rim, opening area,
  coefficient, capacity, source and confidence; numerical cell bindings remain forbidden.
- Deterministic minimum-hop paths to declared outfalls, dead-end/disconnected-node diagnostics,
  missing exchange coverage and parameter-gap reports. Cycles are supported.
- Ward transitions explicitly limited to DECLARED_WARD_IDS_ONLY; genuine cross-ward and hydraulic
  validation claims remain false.

## Validation

Focused Sequence 8 tests: **48 passed**.

Full local `python scripts/verify.py` on Python **3.12.10** passed:

- Ruff: **passed**.
- Strict mypy: **107 source files, no issues**.
- Pytest: **457 passed, 1 skipped** in 30.49 seconds. The skip is unavailable Windows symlink
  permission; no tests were deselected.

Transcript: `artifacts/validation/sequence8-increment1/software-verification.log`.
This is software verification of increment 8.1. It is not a deployed Sequence 8 development gate.

All graph cases are labelled synthetic references. No real drain dimensions, inverts, network
connections, outfall acceptance or ward-boundary evidence have been invented.

## Runtime and release boundary

The deployed Docker API remains **Sequence 7 / v0.7.0**, built from the validated `318ec92` source.
The Sequence 8 branch adds local library code; it is not deployed and therefore has a different
source fingerprint. A later Sequence 8 API integration must rebuild and verify its exact source.

No Sequence 8 migration, persisted product, API, technical freeze or final acceptance is claimed.
`main` remains at the Sequence 5 baseline. These are local development checkpoints, not a claim of
remote publication or hosted acceptance.

## Next continuation

1. Build source-bound graph construction/import from reconstruction and normalized ward layers,
   with explicit source hashes and preserved uncertainty; do not connect lines solely because
   they overlap visually or invent flow direction from a DEM.
2. Implement the hydraulic parameter/readiness assessment and auditable reasons for every missing
   required value. Versioned pump/outfall references alone do not constitute executable definitions.
3. Add immutable graph/parameter/exchange/QA/audit storage, migration, service and corruption guards.
4. Add API/QA and reference bootstrap, then pass the complete pinned-runtime Sequence 8 gate.
5. Establish genuine adjacent-ward continuation and downstream-destination evidence before closing
   Sequence 9. Apply the existing human-review deferral policy without weakening automated checks.

Continue from this branch after checking its live Git state and the predecessor freeze report.
Do not begin the Sequence 9 twin builder while the Sequence 8 technical gate remains incomplete.
