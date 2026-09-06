# Sequence 7 — TECHNICAL DEVELOPMENT FROZEN / FINAL HUMAN ACCEPTANCE PENDING

Date: 6 September 2026  
Development branch: `sequence-7-urban-gis`  
Validated code baseline: `318ec92086daef14d816df16b2786a8482b452c0`  
Release identity: `0.7.0` / Sequence `7`

## State

- Automated development status: **TECHNICAL_DEVELOPMENT_FROZEN**.
- Full pinned-runtime development gate: **PASSED**, with no technical blockers.
- Final human acceptance: **FINAL_HUMAN_ACCEPTANCE_PENDING — SEQUENCE 20**.
- Sequence 8 development: **permitted**.
- Git integration: development-branch freeze; `main` remains at Sequence 5.

This technical freeze concerns implemented interfaces and deterministic reference validation.
Real Kolkata GIS classification, calibrated hydrology and hydraulic validation remain pending.
The earlier technical-freeze candidate is superseded by the evidence below.

## Reproducible validation evidence

This command exited zero against the clean committed baseline and its rebuilt local Docker API:

```powershell
.venv\Scripts\python.exe -u scripts/sequence7_development_gate.py --run-checks --output artifacts/validation/sequence7-318ec92/development-gate.json
```

Gate started: `2026-09-06T15:08:08.782567+00:00`  
Versioned report: `docs/validation/sequence-07-development-gate-318ec92.json`  
Full local transcript: `artifacts/validation/sequence7-318ec92/development-gate.log`  
Report SHA-256: `be4cc557b58603013e6253b468bbc21ec453125d36ab3bae0dd862a628f6287e`  
Source fingerprint: `7d9c660e5deaecf3e817dc41779a29a13da08c67cff71f1caf9d7146cfdf8759`

Results:

- Local Python **3.12.10**; API Python **3.12.11**; no dependency-lock mismatches.
- Ruff **passed**; strict mypy **passed across 104 source files**.
- Pytest: **409 passed, 1 skipped** (unavailable Windows symlink permission).
- All six Docker services and API/readiness/QA verifier **passed**.
- API fingerprint **matched** the validated local source.
- Reference package **created successfully and REFERENCE_READY**.
- Real conditional-storage concurrency **passed in both raw and spatial buckets**:
  8 concurrent writers, exactly 1 creation and 7 rejections per bucket; winning bytes read back intact.
- Source fingerprint, Git commit and clean worktree remained unchanged throughout the gate.

The recorded gate reports:

```text
development_status = PASSED
technical_development_freeze_status = ELIGIBLE
freeze_status = TECHNICAL_DEVELOPMENT_FREEZE_ELIGIBLE
technical_blockers = []
```

This status marker records the resulting technical freeze. Its documentation-only commit follows
the validated implementation commit; the implementation commit remains the evidence baseline.

## Frozen contracts and repairs

- Separate immutable visual-city and hydraulic-surface products.
- All eight hydraulic surface classes with explicit domain ownership.
- Mutually exclusive simplified-runoff and explicit-loss policies with parameter provenance.
- Exactly one versioned receiving-geometry or explicit-drain-target rule per roof.
- Roof generated-volume and transfer-conservation calculations with declared tolerances.
- Numerical `surface_cell_ids` forbidden until the later grid sequence.
- Strict metric CRS, geometry and topology checks.
- Five create-only artifacts, SHA-256 verification on read, and verified idempotent reuse.
- Readiness verifies every artifact; missing or corrupted bytes cannot remain eligible.
- Script package discovery and direct Sequence 6/7 gate entrypoints work under Python 3.12.
- CLI regression tests isolate report outputs and preserve operator evidence.
- Invalid readiness counters and source changes during verification cannot pass the gate.

## Immutable reference anchor

- Evidence scope: `REFERENCE_FIXTURE`.
- Pilot ID: `kolkata-sequence7-reference`.
- Package SHA-256: `03b2390c74c767bc37007b28ec791381b4dfae05be4e5042a6cbde86e556801a`.
- Fingerprint: `81b1ad3ebc673871344c1841e3677cc044b957f73958705e03bc47024a83dad5`.
- `urban_gis_id`: `4346f39d-77a5-5a25-9dcb-2c4eb6bb027c`.
- Features: **4 visual, 8 hydraulic, 1 roof with a versioned receiving geometry**.

```text
urban-gis/{city_id}/{pilot_area_id}/{urban_gis_id}/
  visual_city.geojson
  hydraulic_surface.geojson
  roof_runoff.json
  qa.geojson
  audit.json
```

The audit records `surface_cell_ids_assigned = false`. A regression confirms that typing repairs
preserved the published candidate's canonical package bytes and identity.

## Deferred human review

`docs/validation/final-human-review-register.md` retains HR-07-01 through HR-07-04 for real-pilot
geometry/source acceptance, hydraulic classification/domain ownership, every real roof target,
and exact-browser artifact acceptance. The reference fixture does not satisfy those items.

Live final-completion status remains false and human acceptance remains pending under
`docs/validation/final-human-review-policy.md`. Sequence 8 may develop against these frozen technical
interfaces. Rejection of an earlier real-pilot decision must reopen affected downstream products.
