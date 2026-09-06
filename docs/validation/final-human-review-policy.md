# Final Human Review Deferral Policy

Status: **project-owner approved execution policy**  
Approved: 6 September 2026  
Applies to: Sequences 1–20 of the authoritative FloodGuard development plan

## Purpose

The authoritative 20-sequence scientific plan remains the source of truth for physics, data contracts, provenance, conservation, numerical methods and final completion criteria. This policy changes **when human-only acceptance evidence is collected**, not the scientific meaning of any gate.

The project owner has elected to perform consolidated human/engineering review at the end of Sequence 20. Until then, AI agents may continue sequential development only after the current sequence passes every check that can be validated objectively by code, deterministic scientific tests, integrity checks or reproducible runtime probes.

This is not permission to fabricate human evidence or to weaken scientific safeguards.

## Two-stage sequence completion

### Stage A — automated development gate (Sequences 1–19)

A sequence may be technically frozen for continued development only when all applicable agent-verifiable requirements pass, including:

- Ruff, mypy and pytest;
- deterministic unit/integration tests and physically interpretable benchmarks;
- declared numerical/conservation tolerances;
- schema, units, time and CRS checks;
- provenance, checksum, immutability and source-version checks;
- reproducible dependency/runtime identity;
- service/dependency readiness where required;
- fail-closed behavior for missing/invalid data;
- artifact lineage and integrity checks;
- scientific invariants defined by the authoritative plan.

A technical development freeze means the code/interface is stable enough to become the next sequence's development baseline. It does **not** mean that a real-world map, terrain, parameter set or forecast has received human engineering acceptance.

### Stage B — consolidated human acceptance (Sequence 20)

Human-only acceptance is deferred and must be closed before the project receives final scientific/engineering acceptance. Examples include:

- visual engineering QA of real GIS/reconstruction/terrain artifacts;
- field- or domain-judgement classification of depressions and multi-level structures;
- independent cross-layer alignment acceptance;
- review provenance/sign-off requiring a real human identity;
- browser-based visual acceptance of exact immutable artifacts;
- explicit acceptance of source-resolution and real-world limitations;
- any later sequence-specific item that cannot be established by deterministic automated evidence.

The final review must be performed against exact immutable versions/hashes. If the review rejects an earlier artifact or assumption, that sequence and every affected downstream product must be reopened and revalidated. Sequence 20 is not a rubber-stamp step.

## Required statuses

Use these meanings consistently:

- `TECHNICAL_DEVELOPMENT_FROZEN` — automated development gate passed; next sequence may proceed.
- `FINAL_HUMAN_ACCEPTANCE_PENDING` — one or more human-only items remain deferred.
- `FINAL_ACCEPTED` — permitted only after Sequence 20 closes all required human review and any resulting rework.
- `HYDRAULIC_VALIDATED` — never inferred from a technical development freeze; it still requires the validation evidence defined by the scientific plan.

## Rules for deferred evidence

Agents must not populate or simulate human evidence to make a gate pass. In particular, agents must not invent:

- reviewer identity or review timestamps;
- `CONFIRMED_NONE` / `CATALOGUED` site judgements without human review or authoritative evidence;
- survey RMSE/control points;
- datum compatibility;
- real-browser acceptance;
- engineering sign-off.

Deferred items must stay explicit in a review register. Downstream code may be built and tested using synthetic/reference fixtures or clearly provisional real-pilot artifacts, but no operational/validated real-world claim may depend on an unreviewed item.

## Sequence 6 application

Sequence 6 automated development may proceed with the current immutable Ward 7 terrain artifacts at conservative `VISUAL_READY` status when the missing promotion to scenario-ready is caused only by deferred human depression/multi-level review. The automated gate must still verify:

- current-pipeline artifact existence and lineage;
- source/archive reproducibility;
- raw/visual/hydraulic/structure/QA/audit integrity hashes;
- pilot/reconstruction binding;
- source resolution and vertical metadata honesty;
- no automatic sink filling or unproven DSM-to-DTM conversion;
- no failed automated validation check.

Until final human review, that real terrain must not be presented as `HYDRAULIC_VALIDATED`, and downstream hydraulic benchmarks should rely on synthetic/reference cases for physics verification. Real-pilot hydraulic claims remain provisional.

## Relationship to the authoritative plan

This is an approved execution-policy overlay, not a rewrite of the frozen scientific specification. The scientific completion criteria remain unchanged. The only deliberate revision is that human-only acceptance is accumulated and closed in Sequence 20 rather than blocking implementation of Sequences 7–19.
