# Roadmap R2 change review

Revision: ROADMAP-R2-2026-09-07

The owner requested this revision on 7 September 2026 to include changes to the implemented
foundation, historical training/evaluation, GraphCast/XGBoost and a visual replay prototype.
The active plan remains
[the authoritative specification](../Urban_Flood_Digital_Twin_Authoritative_20_Sequence_Plan_FROZEN.md).
This review is a navigation and change record, not a second roadmap.

## What was preserved

- The complete Sequence 1-10 specification text.
- Existing implementation and immutable scientific artifacts.
- The local-inertial surface formulation, roof/exchange grid binding and its numerical tests.
- SWMM Dynamic Wave, disabled duplicate runoff/ponding, and drainage reference tests.
- C1 lagged-head coupling, signed weir/orifice exchange, capacities and source-volume limits.
- All four initialization modes, with explicit observation-update accounting and data eligibility.
- The global volume ledger, state continuity, datum and source-resolution requirements.
- Deterministic FloodCube ownership, road-level exposure and stream-scoped freshness.
- Ensemble/scenario separation, time-dependent routing and the full 2D/3D dashboard.
- Sensitivity before calibration, new immutable calibrated twins, independent validation,
  connected-catchment performance, failure recovery and final human acceptance.
- DATA-08-01 and the existing technical/human review distinction.

## Old-to-new mapping

| Former sequence | New location | Change |
|---|---|---|
| 11 surface solver | 12 | Adds explicit earlier-product compatibility and roof/accounting details |
| 12 SWMM | 13 | Adds exact controls, hotstarts and native-flooding accounting |
| 13 coupling/state | 14 | Adds historical reconstruction, continuity and observation-state accounting |
| 14 forecast/exposure | 15 | Adds purpose/availability checks and development baseline evaluation |
| 15 risk/scenarios | 17.A | Preserved as a required subgate |
| 16 routing | 17.B | Preserved as a required subgate |
| 17 dashboard | 18 | Adds event playback, model/observation comparison and offline assets |
| 18 scaling | 19.14 and performance gate | Adds whole-pipeline and GraphCast resource measurements |
| 19 sensitivity/calibration/validation | Development portion in 15; final audit in 19 | Locks test events before model selection |
| 20 release | 20 | Adds model/data recovery, reproducible replay and supported-claim acceptance |

New Sequence 11 owns compatibility/event/availability/source work and a bounded rainfall preview.
New Sequence 16 requires actual pretrained GraphCast inference and XGBoost rainfall training,
evaluation and prepared-forcing integration. The former rule postponing all ML until after
Sequence 19 is explicitly replaced. Full GraphCast retraining/fine-tuning and transformers
remain outside this revision.

## Existing-code impact ownership

| Existing implementation | Owning new sequence |
|---|---|
| Registry source/product/access metadata | 11 |
| Raw acquisition selection and source adapters | 11 |
| Observation units, intervals, spatial references and QC | 11 |
| Evidence-backed terrain/drainage/twin corrections | 11 through original owner workflows; rechecked in 19 |
| Forcing compatibility, new manifests and event windows | 11 |
| Numerical bindings for static geometry | 12 |
| Drain-to-SWMM, stage/control consumption | 13 |
| State initialization and event-window handoff | 14 |
| Forecast purpose, historical input eligibility and baseline reports | 15 |
| Model/feature/run metadata and prepared-rainfall adapters | 16 |
| Risk and route derivation | 17 |
| Browser publication and full replay APIs | 18 |
| Calibration feedback, final evaluation and performance corrections | 19 |
| Migration/restore, packaging and final recovery checks | 20 |

## Wording and dependency decisions

Frozen planning does not mean frozen software. Engineering verification, data readiness,
independent evaluation and supported scientific claims have different evidence requirements.
Sequence 11 can complete an independent rainfall-data gate while real hydraulic readiness
remains blocked. Later components cannot use that success to waive real-twin requirements.

Historical replay, hydraulic reconstruction, reanalysis hindcast and issue-time backtest now
have separate meanings and explicit metadata. Recorded observations may be used to assess
predictions, but cannot enter a predictor's future inputs. Pretrained-model training overlap is
audited as well as the local XGBoost split.

The model integration gate requires executed runs, not adapters alone. A candidate that fails
to improve the baseline can still be evaluated and recorded as rejected; integration completion
does not imply model selection. Missing mandatory model/data execution keeps the gate open.

Numerical gauge/radar/live access is conditional on provider evidence. The plan does not
promise an unauthenticated feed, available historical flood-depth labels or laptop feasibility
for full GraphCast. Resource assessment and unknown-data behavior are explicit.

## Aligned documents

README.md, agent.md, ROADMAP_R2_CONTINUATION.txt and the Sequence 10 handoff/status addendum
point to R2. The Sequence 8 architecture's forward numerical-binding reference now points to 12.
The earlier feasibility/replay notes are marked background and aligned to the new sequence order.
Existing validation receipts remain unchanged.

The exact pre-revision plan is retained at
[the archived snapshot](archive/AUTHORITATIVE_PLAN_BEFORE_R2_2026-09-07.txt), with its SHA-256
in archive/README.md. It is not an active specification.

## Review scope

The document review checks sequence uniqueness/order, release targets, gate and dependency
structure, preserved early-sequence text, retention of original technical requirements,
updated agent references, code-fence balance, local links and documentation-only Git changes.
This is not a rerun of the application's scientific or deployment test suite.
