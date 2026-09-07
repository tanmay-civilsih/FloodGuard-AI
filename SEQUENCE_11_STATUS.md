# Sequence 11 status — historical data and compatibility

Roadmap: ROADMAP-R2-2026-09-07. Release: v1.1.0.

**Implementation complete. Historical-data gate PASSED. Sequence 11 R2 data interfaces
TECHNICALLY FROZEN** on the validated source below. No Sequence 12 implementation is included.

The [retained deployed gate](docs/validation/sequence-11-development-gate-4c139b5.json) has no
data-gate errors. It proves exact deployed source/runtime parity, real rainfall preparation,
same-identity event rebuild, six unchanged v1 forcing artifacts and recreation of both forcing
and event catalogues in isolated empty tables. The receipt reports eligibility; this status
record declares the corresponding bounded interface freeze under the approved R2 rules.

Frozen interfaces: `history-request-v1`, `historical-event-v1`, `observation-v1`,
`source-availability-v1`, `evaluation-dataset-v1` and `nasa-power-hourly-v1`.
Their exported JSON schemas are in `docs/examples/sequence-11-*.schema.json`.

## Verified source and software checks

Implementation source: `4c139b54b3e2b24f077af36b127121de3a182ac0`.
Source fingerprint: `a32c3e022e9843c39a826f61a82f5d2753f041586fa6fa9d601d2e71056053ee`.
The deployed API reports v1.1.0 / Sequence 11, Python 3.12.11, this exact fingerprint and
no dependency-lock mismatches. All six local Compose services are healthy.

- Full regression suite: **771 passed**, two upstream Xarray/NumPy deprecation warnings.
- Ruff: passed. Strict mypy: **164 source files**, no issues.
- Additive migration and isolated rollback preserve old catalogue rows and bytes.
- Conditional-storage probe: raw and scientific buckets each accepted one writer and rejected
  seven competing writers. Original immutable storage remains active.
- Preview behavior: rendering, missing accumulation, safe source text, play/pause, failed reads
  and superseded selection handling passed. Exported HTML also passed the Node behavior harness.
- Interactive browser visual inspection was unavailable because no browser was connected.
  This is recorded separately from automated checks; final human review remains Sequence 20.

The PowerShell console wrapper emitted a NativeCommandError for Docker's progress on stderr.
The Python gate produced a passing receipt; a separate direct check exited zero and verified
its software results, current source fingerprint and successful legacy recreation. This console
wrapper behavior is not an omitted regression failure.

## Retained real rainfall

Event: `ed49b4f8-ea39-5d65-818a-9ac679756534`.
Raw dataset version: `454d4fd3-e0f1-4820-80f7-5f7b34969529`.
Twin: `a73bc1b5-ec4e-5291-825f-aed596d97999` (real Ward 7, VISUAL_ONLY).

20 September 2021 UTC has **24/24 valid hourly intervals**, **51.90375 mm** integrated
MERRA-2 reanalysis rainfall and **eight consecutive three-hour forcing packages**.
Each package declares three antecedent hours. Hydraulic use remains refused; historical
provider availability is UNKNOWN and hydraulic state continuity is not initialized.

Open `http://localhost:8000/history/preview` with the local stack running. The standalone
export is `artifacts/sequence11/rainfall-preview.html`; its embedded data renders without API access.

Implemented: typed event/observation/availability and evaluation definitions, governed POWER
acquisition and reuse, separate station normalization, immutable event/replay storage, read-only
API and preview, source/event inventory, and additive migration. A Sequence 10 compatibility
defect in reading provisional drainage input envelopes is fixed with a regression test.

The independent Sequence 11 rainfall-data gate follows the R2 exception for rainfall-only work.
It does not close **DATA-08-01** or freeze the still-blocked Sequence 9/10 hydraulic prerequisites.
The retained real Ward 7 twin remains **VISUAL_ONLY**. No flood observations, GraphCast execution,
XGBoost training, hydraulic simulation, flood probability, warning or route is claimed.

- [Implementation, scientific assumptions and commands](docs/architecture/sequence-11-history.md)
- [Complete bounded candidate-event and source inventory](docs/architecture/sequence-11-source-event-inventory.md)
- [Sequence 10 retained status](SEQUENCE_10_STATUS.md)
- [Authoritative R2 plan](docs/Urban_Flood_Digital_Twin_Authoritative_20_Sequence_Plan_FROZEN.md)

## Next sequence

Sequence 12 is the next development target: the baseline 2D surface solver and numerical-grid
bindings. Use the R2 specification and preserve DATA-08-01, event-date evidence gaps and twin
eligibility throughout. A frozen rainfall-data interface does not authorize a real flood claim.
