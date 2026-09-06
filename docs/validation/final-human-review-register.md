# Final Human Review Register

Status: **OPEN — consolidated closure scheduled for Sequence 20**  
Policy: `docs/validation/final-human-review-policy.md`

This register contains human-only or engineering-judgement acceptance items that are intentionally deferred while automated development continues. Entries are never treated as passed merely because downstream code builds or tests succeed.

## Rules

- Do not delete an open item to make a sequence appear complete.
- Final review must reference exact immutable artifact IDs/hashes and the reviewed software baseline.
- A rejected item reopens the originating sequence and every downstream product that depends on it.
- Automated agents may collect evidence and prepare views/reports, but they must not invent reviewer identity, sign-off, `CONFIRMED_NONE`, `CATALOGUED`, survey control, datum compatibility or browser acceptance.

## Open items

| ID | Sequence | Human/final acceptance item | Current state | Closure requirement |
|---|---:|---|---|---|
| HR-04-01 | 4 | Independent cross-layer alignment of the exact current normalized products | `PENDING_SEQUENCE_20` | Human/engineering review tied to current normalized product hashes and working CRS |
| HR-05-01 | 5 | Reconstruction review provenance, including any approval created before operator authentication | `PENDING_SEQUENCE_20` | Review exact reconstruction lineage, reviewer identity/provenance and approved artifact |
| HR-06-01 | 6 | Flood-relevant depression classification for Ward 7 terrain | `PENDING_SEQUENCE_20` | Review exact terrain/QA; record `CATALOGUED` with interventions or `CONFIRMED_NONE` with evidence |
| HR-06-02 | 6 | Multi-level structure classification for Ward 7 terrain | `PENDING_SEQUENCE_20` | Review exact pilot; record structures or evidence-backed `CONFIRMED_NONE` |
| HR-06-03 | 6 | Real-browser QA and explicit acceptance of coarse SRTM limitations | `PENDING_SEQUENCE_20` | Review exact visual/hydraulic/QA artifacts and record acceptance/limitations |
| HR-06-04 | 6 | Local vertical-reference compatibility with future drain/stage/survey elevations | `OPEN_CONSTRAINT` | Establish compatible/explicitly transformed reference before any cross-datum hydraulic comparison; may be resolved before Sequence 20 if later inputs require it |
| HR-07-01 | 7 | Real-pilot visual-city geometry and source acceptance | `PENDING_SEQUENCE_20` | Review exact real-pilot building/road/water/park/railway visual features and source lineage |
| HR-07-02 | 7 | Real-pilot hydraulic surface classification and hydraulic-domain ownership | `PENDING_SEQUENCE_20` | Review every real hydraulic feature class/domain against exact immutable geometry and policy version |
| HR-07-03 | 7 | Roof receiving geometry or explicit drain target for every real roof | `PENDING_SEQUENCE_20` | Verify each real roof has one accepted, versioned receiving geometry or evidence-backed drain target; no guessed surface-cell IDs |
| HR-07-04 | 7 | Real-browser acceptance of separate visual/hydraulic/roof-runoff artifacts and limitations | `PENDING_SEQUENCE_20` | Review exact Sequence 7 artifacts/hashes and record acceptance of classification/parameter limitations |

Future sequences must append their own human-only items here when a deterministic automated check cannot establish final acceptance.

## Sequence 6 evidence anchor

Current pilot terrain selected during the last successful technical preflight:

- `terrain_id`: `302999c4-68d7-5dc9-bdd3-b12fd41c13d6`
- `terrain_pipeline`: `sequence-6-terrain-v7`
- source raw SHA-256: `a33db2996270c1755e283ea376a861ad3edf0e3bd91d238dedf06683a1adc358`
- base package SHA-256: `8ec840ce1341d5ef9b84d1626003cebaa9ea9d36a126cd0c6abaa13ec2bec1fc`
- visual SHA-256: `c0c19a76d08e1b9bd624ca4a41a3fda15a95391cd470274ddff65465df8cec89`
- hydraulic SHA-256: `fc6970cb047fc66d97dfb0449ed83de3a4f6ecc734efc2d14857625e35884145`
- multi-level catalog SHA-256: `a59fb745d27507f35f8563cef3fc2eeb39e693da6a8963a4c64efbbe0d7eb54d`
- QA SHA-256: `04748c00e43c0a243c3def32b7088b412bd0fc8843148de5aa72d39a5eb146ff`
- audit SHA-256: `0c9e789b48fa0320d3c88d18b5932c37da104833bc2c61bcc13d0f0d883cb90d`

These hashes are an evidence anchor, not human approval. If a newer current-policy terrain supersedes this product before Sequence 20, the register must be updated and the final review must target the superseding artifact.

## Sequence 7 automated reference anchor

The deterministic Sequence 7 reference fixture is deliberately synthetic and exists only to exercise the automated contracts before real-pilot human review:

- evidence scope: `REFERENCE_FIXTURE`
- pipeline: `sequence-7-urban-gis-v1`
- reference pilot ID: `kolkata-sequence7-reference`
- canonical reference package SHA-256: `03b2390c74c767bc37007b28ec791381b4dfae05be4e5042a6cbde86e556801a`
- deterministic package fingerprint: `81b1ad3ebc673871344c1841e3677cc044b957f73958705e03bc47024a83dad5`
- deterministic `urban_gis_id`: `4346f39d-77a5-5a25-9dcb-2c4eb6bb027c`
- exercised hydraulic classes: `ROAD`, `ROOF`, `BUILDING_BARRIER`, `OPEN_SOIL`, `PARK`, `WATER`, `RAILWAY`, `OTHER_IMPERVIOUS`

This reference anchor is **not** a substitute for HR-07-01 through HR-07-04. Final review must target the then-current real-pilot immutable products, not this synthetic fixture.


## Sequence 8 deferred acceptance and real-pilot constraints

| ID | Sequence | Human/final acceptance item | Current state | Closure requirement |
|---|---:|---|---|---|
| HR-08-01 | 8 | Real structure/node classification, nominal connectivity and direction evidence | PENDING_SEQUENCE_20 | Accept exact source-feature bindings and highest-priority direction evidence; nearest-feature associations are insufficient |
| HR-08-02 | 8 | Real dimensions, inverts, roughness, condition, capacity and vertical reference | PENDING_SEQUENCE_20 | Versioned evidence, explicit missing values and compatible elevation frame; no inferred survey or invented parameters |
| HR-08-03 | 8 | Real pump/storage/outfall definitions and downstream destination | PENDING_SEQUENCE_20 | Accept exact static definitions, source lineage and receiving geometry; static references alone are insufficient |
| HR-08-04 | 8 | Real physical inlet/manhole exchange coverage and overtopping need | PENDING_SEQUENCE_20 | Review source-bound geometry, rim, opening, coefficient, capacity and the need for distributed overtopping |
| HR-08-05 | 8 | Exact drain/ward/source/QA visual comparison and out-of-ward diagnostics | PENDING_SEQUENCE_20 | Review exact immutable versions, including three candidates outside all ward polygons; live browser acceptance has not occurred |

**DATA-08-01 - OPEN; must resolve before Sequence 9 closes.** No source-bound real directed graph or
accepted real cross-ward drainage continuation has been established. The stored source geometries
intersect wards 7, 8, 10 and 12, but intersection alone is not evidence of hydraulic connectivity,
direction or a defensible downstream destination. This is a missing data/model requirement as well
as a later acceptance dependency; it is not postponed to Sequence 20 by the human-review policy.
The Sequence 9 builder must keep this real-pilot closure gate separate from reference development.

Verified local bootstrap anchors (6 September 2026):

- Real import product: `30c05f00-2ab5-5aea-a640-5275711ce127`, REAL_PILOT_PROVISIONAL / VISUAL_ONLY.
- Reconstruction: `4fea299c-e2ea-5a11-ae98-eaff9649c6da`, working SHA-256
  `5cda954e5d61d2f2191b63c80e19efdb99848c4ecaafa6fcffa90ee0d5e351b6`.
- Ward normalization: `acff42f4-d7a0-5bed-bcdc-28d5ed740b63`, working SHA-256
  `da962cba8ec62bdf45e86a70d403880532f880f205e437aa5dc678dabc74d65a`.
- Imported features: 104 drains, 84 structure candidates, 98 labels, with unchanged source bytes.
- Controlled reference product: `898df152-6437-55ba-9ff4-bcdb430a4a00`, REFERENCE_FIXTURE /
  HYDRAULIC_SCENARIO_READY. It contains six nodes, five edges and both mandatory point exchanges.

The reference is not real drainage evidence and cannot close any HR-08 item or DATA-08-01.
The passing clean-commit report `docs/validation/sequence-08-development-gate-de6cce9.json`
retains every product artifact hash and successful HTTP readback. Source commit `de6cce9`
passed 568 tests, strict mypy for 122 source files, all six service checks and deployed
conditional-storage concurrency. This closes the Sequence 8 technical development gate only.
