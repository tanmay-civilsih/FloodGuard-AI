# Sequence 10 - Dynamic Forcing Service

Date: 6 September 2026. Branch: `sequence-10-forcing`. Release: `1.0.0`.
Status: **IMPLEMENTED AND VERIFIED; ASSEMBLY PASSED** on `2c39b70`.
Freeze: NOT_FROZEN. Final human acceptance pending Sequence 20.

## Authorization and predecessor

The owner instructed "now implement sequence 10" and "continue" after the Sequence 9 blocker
report. This authorizes a development-order exception. Sequence 9 remains NOT_FROZEN: DATA-08-01
still requires a genuine real drainage path across adjacent wards to a defensible destination.
Reference forcing does not establish real-pilot or operational readiness or waive that requirement.

## Implemented

- Strict request/manifest contracts, UTC windows, metric grids and version/hash provenance.
- Synthetic, replay and externally prepared forecast/nowcast/blend inputs.
- Conservative rainfall remapping per interval/member; Xarray/Zarr v2 artifacts preserve rain rate,
  accumulation, quality flags, interval bounds, issue/valid/lead times, CRS, native/effective resolution.
- Dynamic stage series with explicit interpolation and compatible or explicitly transformed datums.
- Pump operational controls; discrete states always STEP_HOLD, continuous fractions explicit.
- Exact twin/asset binding, explicit antecedent availability, no automatic hydraulic initialization.
- FULL_COVERAGE / PARTIAL_COVERAGE / BLENDED_EXTENSION / INSUFFICIENT; no silent temporal extension.
- Immutable request/artifacts/manifest, verified conditional writes, idempotent build/recreation,
  additive migration, operator CLI, read-only API and full deployed gate.

## Verification

- Implementation commit: `2c39b704b60c85bc2d18d0533c6383d1d3792029`.
- Local/API source fingerprint: `28a7e4f8da4881aca753045f82e3a28d40bb51d1a9a67ae12622ff5b86499732`.
- Full committed-source gate: **730 passed, 1 skipped** in 60.24 seconds; no deselections.
- Focused Sequence 10 coverage: **59 tests**; Ruff passed; strict mypy **148 source files** passed.
- Local Python 3.12.10 / deployed Python 3.12.11, exact pinned dependencies on both platforms.
- API v1.0.0 / Sequence 10; all six Compose services healthy; `/ready` confirms dependency/schema
  readiness at migration head `0009_sequence_10_forcing`.
- Controlled forcing package: `e82ca9de-a4da-5ec1-b9cc-f097a8f1aa1c`.
- Exact controlled twin: `f6f45792-6caa-5f0b-9d29-817110269ef1`.
- Package coverage FULL_COVERAGE, hydraulic input eligibility true for that reference twin,
  no package blockers, antecedent explicitly MISSING, no operational validation claim.
- Reference benchmark: 20 mm/h for three hours over 9600 m2 = **576 m3**, final depth **60 mm**.
- Empty package registry recreation preserved identity/manifest bytes; repeat recreation reused ID.
- All **six HTTP artifacts** matched size/hash. Full reads revalidate the retained twin and
  recompute the forcing assessment/artifacts; missing/corrupt bytes fail closed.
- Windows regenerated the Linux RainCube **byte for byte** and independently reopened it with Xarray.
  RainCube shape is time/y/x = 3/8/12. Effective source resolution remains 60 m on the 10 m target grid.
- Conditional storage: each of the two buckets had eight writers, one creation and seven rejections.
- Assembly blockers: **none**. Inherited freeze blockers: **DATA-08-01 only**. The gate exits 1
  for that inherited constraint while software/services/storage/assembly are explicitly PASSED.

The exact gate report is `docs/validation/sequence-10-development-gate-2c39b70.json`; the cross-platform
receipt is `docs/validation/sequence-10-cross-platform-rain-2c39b70.json`. The complete transcript and
retained deployed RainCube are under `artifacts/validation/sequence10-2c39b70/` (local ignored artifacts).
Reports are copied byte-for-byte from the clean source baseline; later documentation commits do not
alter release source identity. The Windows symlink permission skip and two Xarray/NumPy deprecation
warnings remain visible; numcodecs also emits its upstream crc32c deprecation notice.

## Limits

No hydraulic simulation or operational forecast is implemented here. Raw radar QPE, gauge correction,
motion estimation, radar extrapolation and NWP blend algorithms are conditional source adapters;
they are not claimed without suitable source data. Already processed radar/forecast rates can be
ingested with explicit lineage. No operational data was acquired. IMERG stays coarse replay/development
input. Unknown gate/sluice IDs are refused until relevant static assets exist in a versioned twin.
Hashing retains source assertions; it does not independently establish meteorological validity.

Volume summaries integrate the entire supplied RainCube; requested/common support is separate.
Absent/incomplete antecedent data does not imply a dry state; Sequence 14 owns initialization.
The inherited Windows symlink skip and pinned third-party deprecation warnings remain visible.

## Operator interface

Run in the configured API container for database/object-store access:

```text
python -m floodguard.forcing.build --request PATH --dry-run
python -m floodguard.forcing.build --request PATH
python -m floodguard.forcing.build --recreate-manifest PATH --dry-run
python -m floodguard.forcing.build --recreate-manifest PATH
python -m floodguard.forcing.bootstrap
```

The example `docs/examples/sequence-10-reference-request.json` binds an exact existing controlled
Sequence 9 twin. The bootstrap creates a current-source reference twin; no latest lookup is used.
See `docs/examples/sequence-10-request.schema.json` and `docs/architecture/sequence-10-forcing.md`.

Read-only API: `/forcing/readiness`, `/forcing/products`, `/forcing/products/{id}` and
`/forcing/products/{id}/{manifest|request.json|rain.zarr.zip|boundaries-and-controls.json|antecedent.json}`.
`antecedent-rain.zarr.zip` exists only when history is supplied.

Full gate: `python scripts/sequence10_development_gate.py --run-checks`.
Sequence 11 is outside this task. DATA-08-01 remains an inherited freeze blocker.

## Repository boundary

The task is local to branch `sequence-10-forcing`. main and remotes were not changed. No hosted
release, merge, human sign-off, Sequence 9 freeze or operational hydraulic validation is claimed.
Read `SEQUENCE_10_CONTINUATION.txt` before subsequent work and verify live state again.

## Planning revision recorded 7 September 2026

ROADMAP-R2-2026-09-07 redesigns future Sequences 11-20 at the owner's request.
The next planned sequence is compatibility/historical events/observation data; the surface
solver is now Sequence 12, coupled initialization remains assigned to Sequence 14 in R2,
and deterministic forecasting is Sequence 15. Read the active frozen plan and
`ROADMAP_R2_CONTINUATION.txt`. All implementation, test and freeze claims above refer to the
recorded Sequence 10 source; this documentation revision does not rerun or change those receipts.
