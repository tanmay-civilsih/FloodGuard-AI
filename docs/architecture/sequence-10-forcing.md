# Sequence 10 - Dynamic forcing package

Status: implementation complete; deployed gate pending. Authorized by the owner to implement Sequence 10
after the Sequence 9 blocker was reported. This is an explicit development-order exception. It does
not freeze Sequence 9, close DATA-08-01, or authorize a real hydraulic/operational claim. The frozen
scientific contracts remain unchanged. Reference development can proceed; release eligibility must
continue to report the inherited data blocker.

The service binds exact twin identity to rainfall, stage boundaries, controls and an optional,
explicit antecedent window. No hydraulic simulation, runoff generation, forecast publication or
state initialization occurs here. Missing antecedent data cannot silently become dry initial state.

Inputs are already normalized rainfall interval means in mm/h on regular projected metric grids,
UTC time edges, immutable source/version/hash provenance, named metric vertical references and
declared time-series interpolation. Replay, synthetic and externally prepared forecasts share one
contract. Radar nowcasts/blends require externally supplied processed rates and processing lineage;
raw radar QPE, gauge correction, motion estimation and pySTEPS are conditional adapters, not claimed
without available radar/gauge/NWP sources. IMERG remains a coarse development/replay source.

Rainfall uses the existing Sequence 4 area-overlap conservative remapper on identical footprints.
Each interval/member must conserve volume to relative tolerance 1e-10 (policy sequence-10-forcing-v1).
Volume is sum(rate_mm_h * dt_seconds * area_m2 / 3600000). Accumulation is cumulative depth in mm
at the end of each interval, from the first supplied edge. Numerical grid spacing does not improve
native/effective information resolution. No extrapolation, implicit zero padding or missing-cell
replacement is permitted. Inputs are finite and nonnegative. The prototype enforces bounded arrays.

RainCube is an Xarray dataset stored as a deterministic ZIP of a Zarr v2 group, with time/y/x and
optional ensemble-member dimensions, rain_rate, accumulation, quality_flag, interval bounds, issue,
valid and lead times, source, units, CRS, transform, resolution and explicit ensemble definition.
Zero is valid rainfall. Zarr fill/masking is disabled for these completely populated arrays.
The encoding follows [Xarray's Zarr interface](https://docs.xarray.dev/en/v2026.02.0/generated/xarray.Dataset.to_zarr.html)
and [Zarr v2](https://zarr-specs.readthedocs.io/en/latest/v2/v2.0.html).

Stage interpolation is LINEAR or explicitly declared STEP_HOLD, with no values outside supplied
support. Discrete controls require STEP_HOLD; continuous controls retain an explicit declared method.
Source-supported constant datum offsets are applied once and retained with source/target datum and
method. Unknown or incompatible vertical frames refuse hydraulic eligibility. Pump IDs and outfall
IDs must belong to the exact twin; unsupported gate/sluice assets require a future static contract.

Coverage intersects rainfall and every required boundary/control window against a requested forecast
window of at most three hours. FULL_COVERAGE and explicitly sourced BLENDED_EXTENSION can be eligible;
PARTIAL_COVERAGE and INSUFFICIENT cannot. A 90-minute product never becomes a three-hour product.
Eligibility also requires a scenario-ready twin and compatible datum; it is reference/provisional
input eligibility, never scientific validation. Antecedent completeness is independently reported.

Artifacts and requests are content-addressed, written conditionally, read back and hashed before
metadata registration. Identity includes policy, exact twin manifest hash, input request, generated
artifact hashes and software identity. Repeated builds reuse identity; changes create a new version.
Readers verify all artifacts and recompute assessment. Missing/corrupt inputs fail closed. API reads
are read-only; operator CLI owns build/recreation. Earlier twin and forcing versions remain immutable.

Validation must cover interpretable rainfall-volume benchmarks, irregular intervals, zero rain,
ensemble independence, resolution honesty, stage interpolation/offsets, discrete changes, wrong IDs,
missing series, partial/disjoint horizons, antecedent gaps, Xarray round-trip, repeat/recreation,
tampered metadata/artifacts, API failure behavior and full deployed source/dependency parity.
