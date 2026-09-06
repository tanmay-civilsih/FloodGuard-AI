# Historical training and replay prototype proposal

Date: 7 September 2026.
Status: background design integrated into ROADMAP-R2-2026-09-07. The owner subsequently
authorized revision of the frozen sequence order. Follow
[the active R2 plan](../Urban_Flood_Digital_Twin_Authoritative_20_Sequence_Plan_FROZEN.md)
for mandatory scope, dependencies and gates. This note itself performs no model/data/UI execution.

## Objective

Use documented historical Kolkata rainfall/flood events to develop and evaluate forecasting,
and to present an attractive, repeatable prototype showing the event, model outputs and available
observations on a synchronized map and timeline. A packaged event should remain viewable without
live provider access once its permitted data and derived display assets have been downloaded.

Historical data supports three different activities: training model parameters, independently
testing predictions, and presenting recorded event/model results. Each has its own event split
and provenance. A convincing animation is a product demonstration, not a measure of accuracy.

## Verified repository fit

- Current branch: `sequence-10-forcing`; Sequence 10 status records implementation and verification,
  with NOT_FROZEN inherited from DATA-08-01. This proposal does not close that blocker.
- Sequence 10 already accepts prepared historical rainfall through `Mode.REPLAY`, including exact
  interval bounds, source lineage, conservative remapping and immutable forcing artifacts.
- No historical GraphCast/XGBoost training pipeline, hydraulic flood forecast or web viewer is
  currently established by the inspected implementation. The reference forcing benchmark is
  controlled input, not a measured Kolkata flood.
- The actual pilot still needs a source-bound drainage connection and other hydraulic data.
- R2 Sequence 11 supplies compatibility, historical data and a bounded rainfall preview.
  Sequences 12-15 implement surface/drainage/coupling, initialization, deterministic forecasts
  and the development baseline. Sequence 18 supplies the full 2D/3D dashboard.
- The owner-requested R2 revision places pretrained GraphCast inference and XGBoost rainfall
  training/evaluation in Sequence 16, followed by final independent validation/scaling in 19.
  The former post-Sequence-19-only ML rule is superseded.

References: `SEQUENCE_10_STATUS.md`, `floodguard/forcing/contracts.py`,
`docs/architecture/sequence-10-forcing.md`, and
`docs/Urban_Flood_Digital_Twin_Authoritative_20_Sequence_Plan_FROZEN.md`.

## Model roles and recommended experiment

### GraphCast

Use a pinned pretrained checkpoint first. The official model documentation supplies GraphCast
variants trained on historical ERA5, including an operational variant fine-tuned on HRES.
Full-model retraining or fine-tuning is technically possible but is a separate research workload;
local rainfall, elevation and flood labels alone do not supply its global atmospheric input contract.
The original model requires both surface and upper-air fields, not just single-level ERA5.

For historical inference, obtain the checkpoint-compatible global initial states at the issue time
and six hours earlier, run a genuine forecast, then extract the regional output. Preserve the
checkpoint, normalization data, input hashes, issue time, lead time and software revision.
GraphCast's six-hour output cannot establish the timing of a local ten-minute storm burst.
Any temporal refinement must be specified and evaluated separately.

Source: [official GraphCast documentation](https://github.com/google-deepmind/weathernext/blob/main/docs/weathernext1_graph/README.md)
and [model input/output description](https://deepmind.google/blog/graphcast-ai-model-for-faster-and-more-accurate-global-weather-forecasting/).

### XGBoost

Start with one explicit target: observed rainfall accumulation over a stated location, interval
and lead time, predicted using forecast rainfall and information available before issue time.
Compare this correction with the uncorrected forecast and a simple statistical correction.
Keep XGBoost only if independent events show useful improvements.

Candidate predictors include forecast accumulation, lead time, preceding rainfall accumulations,
radar-derived features if available, and relevant atmospheric variables. Pin feature definitions,
units, availability rules and missing-value handling. Training on satellite estimates makes that
estimate the target; it does not establish agreement with local rain gauges.

A later direct flood-depth/occurrence model is a different task. It requires depth/occurrence
labels and appropriate dry cases, with terrain, drainage, antecedent wetness, downstream stage
and pump state as relevant features. A rainfall-trained model cannot silently become a depth model.
Simulation-generated targets support a simulator surrogate; independent measured flood evidence
is still needed to establish real-world skill. Corrections to flood depth must not overwrite the
conservative hydraulic output or its water ledger.

## Historical event package

Select one connected catchment and inventory multiple storm and non-flood events. Start the
viewer with the best documented event; select model evaluation events separately. Do not choose
a supposedly complete event until its actual files, coverage and access conditions are checked.

| Evidence | Use | Limitation to retain |
|---|---|---|
| ERA5 surface and pressure-level fields | Compatible historical atmospheric states | Reanalysis is a retrospective reconstruction, not an archived real-time forecast |
| Archived issue-time weather forecasts, where available | Operationally representative backtesting | Preserve original issue/availability times and model version |
| IMERG historical precipitation | Coarse rainfall replay or explicit estimated target | Not local radar or street-level rainfall truth |
| Archived gauges/numerical radar, where accessible | Local rainfall targets and nowcasting inputs | Coverage, latency, accumulation windows and QC must be documented |
| Documented depth, water-level or flood-extent observations | Evaluate corresponding flood outputs | Extent does not imply depth; sparse reports do not imply a continuous observed flood surface |
| Terrain, drainage, boundaries and operations | Reconstruct the hydraulic event | Use event-date conditions or disclose changes/unknowns |

ERA5 combines observations and modelling retrospectively, and offers surface and pressure-level
collections. [Copernicus ERA5 description](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=overview)

IMERG provides historical half-hourly precipitation estimates at 0.1-degree spacing. Final products
can support retrospective analysis but were not available at their observation times.
[NASA IMERG documentation](https://gpm.nasa.gov/resources/documents/imerg-v07-technical-documentation)

Each package should record event/catchment identity, source/version/hash, units, CRS and vertical
reference, native/effective resolution, observation interval, provider availability time where
known, acquisition time, quality/missingness and permitted redistribution. Acquisition time today
is not evidence that a record was available during the historical event.

## Replay and forecast evaluation modes

1. **Observed-event replay:** animate archived observations or estimates, with their source labels.
   This tests acquisition and presentation. It makes no forecast-skill claim.
2. **Hydraulic reconstruction:** drive the solver using recorded event rainfall and boundaries.
   This evaluates hydraulic response under known forcing, subject to the quality of those inputs.
3. **Historical forecast test:** choose an issue time, freeze all forecast inputs, predict the next
   interval/horizon, then reveal subsequent observations only for scoring and comparison.
4. **Illustrative UI fixture:** use explicitly synthetic or example data to check controls and
   layout when real outputs do not yet exist. Exclude fixture values from model performance metrics.

Record whether a hindcast used reanalysis initial states or genuinely archived issue-time inputs.
Reanalysis hindcast results can be useful, but must not be described as an exact operational replay.
Do not pass future observed rainfall into a flood simulation and report that as a rainfall forecast.

Split whole events chronologically into training, tuning/calibration and locked test sets. Do not
randomly split neighbouring pixels/timestamps from the same storm. Keep a separate display choice
from the complete test report so an attractive event does not become the only evidence shown.

Audit the pretrained GraphCast checkpoint's training and fine-tuning date ranges too. An event
already included in base-model training cannot serve as an independent test of that model simply
because it was held out of XGBoost training. If claiming transfer, add catchment holdouts.
Sensitivity/identifiability analysis precedes hydraulic calibration in R2 Sequence 15;
Sequence 19 audits the frozen configuration using independent evidence.

Rainfall metrics: accumulation bias/error, intense-rain detection and timing by lead time.
Flood metrics where observations support them: depth error, onset/peak-time error, extent overlap,
missed events and false alarms. Report coverage, event count, baseline comparison and runtime.
Probability or prediction-interval claims require separate calibration checks. Missing ground
truth remains unavailable; do not fill a comparison panel with fabricated observations.

## Prototype presentation

Use one synchronized event clock across the map and charts. Default to a clear 2D map, with an
optional 3D catchment view when real terrain/building assets support it. Use a restrained basemap,
consistent rainfall/depth legends and a fixed comparison scale across times and models.

Proposed layout:

```text
[ Event and date ] [ Recorded event / Historical forecast test ] [ 2D / 3D ]
+------------------------------+------------------------------------------+
| Catchment, roads and drains   | Rainfall: forecast vs observed/estimated |
| Rainfall or flood-depth layer | Depth trace at selected observed site    |
| Measurement markers          | Error and evidence coverage              |
+------------------------------+------------------------------------------+
[ Play / Pause ] [ Speed ] ===== event timeline ===== [ Issue | Valid time ]
[ Sources, model version, resolution and coverage ]
```

| Interaction | Expected behavior |
|---|---|
| Select event | Load a versioned package and show its actual coverage and mode |
| Play/pause, scrub and speed | Synchronize every layer/chart; never launch training |
| Select rainfall/depth/terrain/drainage | Show quantity, units, source and availability; unsupported layers explain what is missing |
| Click a measurement location | Show timestamped observation/model series and observation uncertainty where supplied |
| Compare baseline and corrected model | Use the same event, forecast issue, grid and legend scale |
| Reveal observations | Keep future observations out of historical forecast inputs; show them for evaluation |
| Switch to 3D | Preserve selected event/time/location and mark any vertical exaggeration |
| Inspect evidence | Show source/version and native/effective resolution without overwhelming the map |

Use smooth camera transitions and efficient rendering for visual polish. Displayed observation and
model timestamps must remain visible. Interpolation between stored frames is presentation, not new
measurement or additional model skill. Draw flow arrows only from actual velocity outputs.
Do not animate flood water from rainfall colours or elevation thresholds and call it solver output.
Rainfall accumulation is not standing flood depth.

Precompute genuine model runs and display assets for a dependable presentation. Label them as
recorded runs. Serving saved predictions does not require retraining during a demo. Publish tiles,
COGs or other browser-ready assets instead of loading full scientific Zarr arrays into the browser.
An offline package must also retain permitted basemap assets or use a local background.

## Delivery path and acceptance evidence

1. Inventory event data and choose a candidate catchment/event based on evidence completeness.
2. Acquire permitted records, normalize them, verify timestamps/units/coverage, and build immutable
   Sequence 10 replay packages. Preview rainfall independently of flood output readiness.
3. Complete the planned hydraulic/state/forecast implementation and real-pilot data requirements;
   generate traceable historical hydraulic runs and compare available flood observations.
4. Execute the required R2 Sequence 16 GraphCast/XGBoost work against the development baseline;
   retain actual run/training receipts and compare candidates without opening the final test set.
5. Implement the synchronized event viewer in Sequence 18, consuming actual model/risk/route
   products. Validate navigation, timestamps, missingness and offline playback. Sequence 19
   then performs independent evaluation/scaling before Sequence 20 final acceptance.

First complete visual demonstration: one recorded event, a catchment map, timestamped rainfall
playback, an accumulation chart and a source/coverage panel. Add predicted flood depth only when
the hydraulic run exists; add observed flood comparison only where measured evidence exists.

Prototype acceptance should demonstrate repeatable loading, accurate time/legend/units, explicit
observed/estimated/predicted labels, separate fixture data, unchanged source hashes, no fabricated
metrics, and a captured run manifest for every displayed prediction. Hydraulic acceptance still
requires physical benchmarks and a closed volume ledger. This proposal promises no accuracy level.
