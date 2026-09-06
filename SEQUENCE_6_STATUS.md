# Sequence 6 — TECHNICAL DEVELOPMENT FROZEN / FINAL HUMAN ACCEPTANCE PENDING

Date: 6 September 2026  
Development branch: `sequence-6-conditioned-terrain`  
Validated code baseline before this status marker: `10c273a1a99b98a7e339080d8597fb44c566a28c`  
`main` remains unmerged and unchanged by the Sequence 6 repair/freeze work.

## Status

- Automated development status: **TECHNICAL_DEVELOPMENT_FROZEN**
- Final human acceptance: **FINAL_HUMAN_ACCEPTANCE_PENDING**
- Human review closure: **deferred to Sequence 20** under `docs/validation/final-human-review-policy.md`
- Real Ward 7 terrain: remains conservative/provisional until human depression and multi-level review is completed
- `HYDRAULIC_VALIDATED`: **not claimed**
- Sequence 7 development: **permitted**

This status freezes the validated technical interfaces for continued development. It is not a claim that the real pilot terrain, reconstruction, cross-layer alignment or browser presentation has received human engineering sign-off.

## Automated evidence already obtained

A pinned local Python 3.12 run on commit `0f364d0a7e5be6a75542b5fbc4d1d89c3c0aa29b` established the complete software/runtime baseline:

- Ruff: passed;
- mypy: passed across 90 source files;
- pytest: **358 passed, 1 skipped**;
- Docker services: API, PostgreSQL/PostGIS, Redis, NATS, MinIO and Traefik healthy;
- API/service verifier: passed;
- Kolkata spatial bootstrap: passed with current ward/catchment/water-body layers;
- real conditional-storage concurrency: passed for both raw and spatial buckets with 8 concurrent writers, exactly 1 create and 7 rejections per bucket;
- six selected terrain artifacts were read back and matched their recorded SHA-256 values.

The current branch is five focused commits ahead of that fully green baseline. The diff is limited to terrain readiness policy, Sequence 6 preflight/development-gate policy, assessment-draft workflow, tests, `.gitignore`, and validation documentation; no hydraulic solver or numerical kernel was introduced in those five commits.

Post-baseline focused validation performed in the assistant sandbox:

- new Sequence 6 development-gate policy tests: **6/6 passed**;
- terrain readiness policy cases: **5/5 passed** (explicit unresolved datum accepted only for conservative scenario policy; undisclosed unresolved datum, unsupported transform label, incomplete assessments, and failed validation remain non-promotable);
- Python compilation of the new development-gate test harness: passed.

The assessment-template workflow was also exercised on the real local Docker stack: generation succeeded and validation correctly reduced the remaining failures to the intentionally human-only reviewer/depression/multi-level fields.

No GitHub Actions run is used as freeze evidence.

## What is frozen for Sequence 7

The following technical contracts are stable development inputs:

- raw / visual / hydraulic terrain separation;
- immutable terrain and spatial product lineage;
- current-pipeline artifact hashing and read-back verification;
- explicit native/computational/effective resolution metadata;
- conservative SRTM limitations;
- no automatic sink filling;
- no automatic DSM-to-DTM claim;
- explicit multi-level structure contract;
- fail-closed geometry/topology checks with narrowly governed ward self-intersection repair;
- conditional create-only object storage with deployed concurrency verification;
- authenticated mutation path and read-only QA access;
- separate final-human-acceptance and automated-development gates.

Downstream automated physics validation should use deterministic synthetic/reference fixtures where real-pilot human judgement is still pending. Real-pilot outputs remain provisional until the final review register is closed.

## Deferred human review

The authoritative register is:

`docs/validation/final-human-review-register.md`

Current open Sequence 6 items include:

1. independent cross-layer alignment acceptance;
2. exact terrain depression review;
3. exact multi-level structure review;
4. reconstruction review provenance/sign-off;
5. real-browser QA and acceptance of coarse-data limitations;
6. local vertical-reference compatibility before any later comparison with drain inverts, stages or survey levels.

Agents must not fill these fields or invent evidence to upgrade the real terrain merely to satisfy a gate.

## Development gate command

The conservative final-acceptance preflight remains available:

```text
python scripts/sequence6_preflight.py --run-checks
```

For Sequences 7–19, the owner-approved automated development gate is:

```text
python scripts/sequence6_development_gate.py --run-checks
```

The development gate reuses the full preflight and only reclassifies explicitly identified human terrain-review items as deferred. Runtime, storage, integrity, invalid datum claims, scientific failures and other automatable failures remain blockers.

A successful development gate does not grant final human acceptance. Sequence 20 must close the review register against exact immutable artifacts and reopen affected sequences if the review changes an earlier decision.
