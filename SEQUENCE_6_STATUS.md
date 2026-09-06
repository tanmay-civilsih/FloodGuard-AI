# Sequence 6 audit-repair checkpoint — NOT FROZEN

Date: 6 September 2026. Development branch: `sequence-6-conditioned-terrain`.
`main` has not been merged or changed by these repairs.

## Repairs delivered

- Finite-coordinate, geometry-structure and topology checks; no silent geometry repair.
- Exact rainfall footprint matching, finite-volume checks and explicit interpolation coverage.
- Actual source-byte verification, QA hash anchoring, and versioned spatial policy rebuilds.
- Authenticated operator-scoped writes, server-matched reviewer identity and page-local QA credentials.
- Real database/schema/storage readiness probes and loopback-only development ports.
- Conditional create-only storage with backend capability checks and bounded object reads.
- A selected-pilot preflight report with code/lock evidence and artifact-hash checks.

The old spatial `alignment_check_passed` boolean is explicitly numerical-only for compatibility.
Independent cross-layer alignment acceptance remains open; the new scope/status fields prevent
calling that numerical check engineering validation. Historical approval records are not made
authenticated retroactively. None of these changes certifies street-scale hydraulic accuracy.

## Executed validation

The isolated sandbox executed **131 passing tests**: six unchanged upstream spatial tests and
125 new regression cases across resampling, geometry, authorization, dependency probes, operator
setup, integrity, conditional-storage transport, source/lock evidence and preflight policy.
Python was 3.13.5, NumPy 2.3.5 and Shapely 2.1.2. This is not the required Python 3.12 / complete
lockfile environment. Source compilation also passed.

Ruff, mypy, the complete repository suite, database/migration integration, actual MinIO concurrency
and real-browser/pilot acceptance were **not executed** in that sandbox. Integration regressions
are committed for the complete environment. No GitHub Actions run was requested or started.

The sandbox preflight returned **BLOCKED / NOT_FROZEN**. Its missing local runtime/services are
not assertions that another operator's running deployment is broken.

## Local validation after pulling

Use a clean checkout and the declared Python 3.12 environment. Install the current lockfile first:

```text
python -m pip install -r requirements.lock
python scripts/setup_operator.py
docker compose up -d --build
docker compose exec -T api python -m floodguard.spatial.bootstrap --city-id kolkata
docker compose exec -T api python -m floodguard.terrain.bootstrap --city-id kolkata
python scripts/sequence6_preflight.py --run-checks
```

The operator setup prints a bearer token once; keep it private and out of shared logs. The token
is needed for review/acquisition writes, not read-only QA. Do not rotate an existing account unless
intended. The helper refuses an accidental rotation. Details are in
`docs/validation/sequence-06-operator-security.md`.

Spatial rebuilds create new immutable keys. Strict geometry errors require source QA, not blind
repair. Terrain bootstrap may correctly report missing or unassessed pilot data; do not fill in
assessment fields without evidence to make it pass. Follow the existing assessment workflow in
`docs/architecture/sequence-06-terrain-conditioning.md`.

Preflight `--run-checks` runs the existing full software/service verifier and the new real-storage
concurrency check. It compares the running API's source fingerprint and installed dependencies with
the local checkout, selects the latest current-policy product for the requested ward, verifies six
terrain artifact hashes, checks assessment/lineage consistency, and rechecks the selection for changes.
Reports default to `floodguard-sequence6-preflight.json` beside the checkout, keeping the tree clean.

An exit code of zero means technical preflight passed, **not that Sequence 6 is frozen**. A release
still needs documented engineering sign-off, independent cross-layer alignment evidence, trustworthy
review provenance and real-browser QA bound to the exact source/artifact versions. This preflight
never records approval, edits an assessment, changes readiness, creates a tag or merges a branch.

The Compose profile remains local development. Production needs TLS, non-default/scoped credentials,
retention policy and operational acceptance; process-local acquisition jobs remain a declared limit.
