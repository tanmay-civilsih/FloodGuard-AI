# Sequence 10 - Dynamic Forcing Service

Date: 6 September 2026. Branch: `sequence-10-forcing`. Release: `1.0.0`.
Status: implementation complete; committed-source deployed gate pending.
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

Focused Sequence 10 tests: 59 passed. They cover the 576 m3 rainfall benchmark, irregular intervals,
nonuniform rain, dry ensembles, Xarray reopening, short/disjoint coverage, stage interpolation,
datum offset, discrete/continuous controls, wrong/missing assets, antecedent gaps/recreation,
visual-twin refusal, empty-registry recreation, rehashed tampering and HTTP failure behavior.
The final clean-source gate will rerun the entire repository suite and deployed probes.

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
