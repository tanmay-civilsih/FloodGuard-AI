# Elevation, GraphCast and XGBoost for real flood prediction

Date: 6 September 2026. Status: feasibility proposal only; no model implementation, training,
data-feed activation, paid compute or scientific-plan amendment is implied.

Integrated into ROADMAP-R2-2026-09-07 on 7 September 2026. This file retains technical
background; the active authority is
[the revised frozen plan](../Urban_Flood_Digital_Twin_Authoritative_20_Sequence_Plan_FROZEN.md).
Future sequence references below follow R2. This note cannot change R2 scope or gates.

## Assessment

The integration is feasible. It should combine traceable weather inputs with a local hydraulic
model and independently evaluated machine learning. Adding two model names does not establish
real flood-prediction accuracy. The current release assembles verified static/forcing artifacts;
it does not yet simulate or validate real floods.

Verified repository position: Sequence 10 v1.0.0 is implemented with 730 passing tests, immutable
forcing packages, conservative rainfall remapping, boundary/control series and coverage checks.
The real Ward 7 twin remains VISUAL_ONLY with five available and seven missing components.
DATA-08-01 lacks a genuine source-bound cross-ward drainage path to a defensible destination.
R2 Sequence 11 supplies historical events, availability and adapters; Sequences 12-15 supply
surface hydraulics, SWMM, coupling/initialization, forecasting and development baseline evaluation.
Sequence 16 now explicitly includes pretrained GraphCast inference and XGBoost rainfall learning.
Sequence 19 supplies final independent validation/scaling. The owner-requested R2 revision
replaced the former post-Sequence-19-only ML rule; external forecast ingestion still fits Sequence 10.

## Traceable source inventory

| Input | Current evidence / next requirement |
|---|---|
| Elevation | Existing SRTMGL1 acquisition and immutable pilot terrain. Preserve original tile, hash, source age, horizontal CRS, vertical datum and native/effective resolution. Real terrain is not hydraulically accepted. |
| Better terrain | Investigate local surveyed bare-earth terrain, road/underpass levels and drain inverts. Copernicus GLO-30 is a comparison candidate, but is a DSM containing structures/vegetation, not a verified bare-earth urban DTM. |
| Historical rainfall | IMERG is registered; a concrete granule adapter/authenticated acquisition and matched historical events are still needed. Its 0.1-degree, half-hourly observations and approximately four-hour Early Run latency do not provide a fresh street-scale nowcast. |
| Current local rain | Establish an accessible machine-readable gauge/radar feed for Kolkata. Current registry entries are candidates with feed-specific authorization/terms unresolved; a public weather page is not proof of a usable radar field feed. |
| Forecast atmosphere | Pin a GraphCast checkpoint and compatible initial-condition source, or ingest explicitly identified provider forecasts. Verify actual issue, availability and valid times and precipitation accumulation semantics. |
| Hydraulic boundaries | Source-backed river/canal/tide/outfall levels in the same vertical frame as terrain/drains. |
| Operations | Actual pump state, capacity, outage and relevant gate/sluice records tied to static assets. |
| Flood observations | Independent time-stamped water depth/extent/onset observations and reliable non-flood cases, with location, datum/units, confidence and event identity. |

No access to a real-time feed or historical labelled flood archive has been established by this note.

## GraphCast's appropriate role

GraphCast forecasts the global atmosphere at 0.25-degree spacing in six-hour steps. It consumes
global atmospheric states at the current and preceding six-hour times. A Kolkata elevation tile
and a local weather CSV are insufficient inputs for the full model. Its atmospheric graph does
not describe the pilot's physical drainage topology.

The official repository now lives under google-deepmind/weathernext. Its dedicated GraphCast
documentation distinguishes the original 37-pressure-level model, the smaller one-degree model,
and the 0.25-degree operational variant with 13 levels and HRES-compatible initialization. Pin
the intended model/checkpoint and code revision; the moving repository default contains other models.
Use pretrained inference first if selected; global retraining is a separate large research task.
Assess accelerator/memory/runtime requirements against actual hardware before committing to it.
Keep model dependencies in an isolated worker and pass versioned forecasts into the existing service.

For this project's 0-3-hour horizon, the proposed role is regional background context alongside
timely local rainfall information. Six-hour accumulated precipitation cannot reveal the timing of
a short convective burst. A disaggregation method must be explicit and independently tested; preserve
accumulated volume and disclose temporal information limits. Uniform division into smaller intervals
is an assumption, not observed or validated fine-time weather skill.

## Proposed integration

1. Traceable terrain/drainage/land cover -> exact static twin.
2. GraphCast or another identified forecast + local gauge/radar observations -> prepared rainfall.
3. Optional trained XGBoost rainfall correction/fusion -> a separately versioned corrected product.
4. Corrected rainfall + stage boundaries + operational controls -> Sequence 10 ForcingPackage.
5. Static twin + ForcingPackage + explicit hydraulic state -> conservative 2D surface / 1D drainage
   solver and coupling -> predicted depth, onset, duration, extent and drain state.
6. Observed floods -> independent verification; retain physics and ML comparisons separately.

Proposed XGBoost roles must each have a specific supervised target. Rainfall correction needs matched
forecast/observed rainfall examples. A direct flood-depth or occurrence model needs measured floods
and credible dry cases. Suitable predictors can include recent rain, forecast rain, antecedent
wetness, terrain, imperviousness, local drainage capacity/connectivity, downstream stage and pump state.
Every feature must have been available at the historical issue time. Elevation alone supplies no
event labels. Simulation-only training produces a simulator surrogate whose real-world claims still
depend on independent observations.

XGBoost supports regression, classification and quantile objectives. Quantile intervals and classifier
scores need held-out calibration checks. Predictive accuracy, uncertainty calibration and runtime
must be measured; no percentage can be promised before testing. An arbitrary ML adjustment to flood
depth does not preserve the hydraulic water ledger, so it must not silently replace conservative output.

## Evaluation and decision gates

- Start with one connected pilot catchment and several independently documented flood/non-flood events.
- Separate whole storm events chronologically into training, tuning/calibration and held-out testing;
  add geographic holdouts when claiming transfer to another catchment. Avoid random neighbouring-pixel
  splits that leak the same storm into training and test.
- Reconstruct historical issue-time availability. Delayed reanalysis/final rainfall products cannot
  be represented as information available to a live forecast at that time.
- Compare uncorrected forecast, simple statistical correction, XGBoost correction and the physics
  baseline on identical events. Keep an ML component only if it improves the relevant held-out skill.
- Check rainfall volume/bias and event timing, flood-depth error, onset error, extent overlap,
  missed events and false alarms. Check reliability/Brier score or quantile coverage when uncertainty
  is claimed, plus the hydraulic mass balance and the end-to-end data latency/runtime budget.
- Verify stale/missing rain, datum mismatch, pump outage, unknown downstream stage, source corruption
  and distribution shift. Fail explicitly when the claimed horizon lacks adequate support.
- Progress from historical replay to prospective shadow forecasts before any operational claim.

Recommended next step: resolve the real pilot's drainage/datum/terrain gaps and establish paired
rainfall/flood-event data through revised Sequence 11 while completing Sequences 12-15. Use the
required Sequence 16 model integration against the existing external-forcing interface. Follow R2;
any further scope change must be explicit rather than reviving the superseded ordering.
A real validated flood forecast remains the acceptance target.

## Sources checked

- [GraphCast model documentation](https://github.com/google-deepmind/weathernext/blob/main/docs/weathernext1_graph/README.md)
- [DeepMind GraphCast model description](https://deepmind.google/blog/graphcast-ai-model-for-faster-and-more-accurate-global-weather-forecasting/)
- [NASA GPM/IMERG data FAQ](https://gpm.nasa.gov/data/faq)
- [Copernicus DEM description](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM)
- [XGBoost prediction intervals](https://xgboost.readthedocs.io/en/latest/python/examples/prediction_intervals.html)
- Repository: SEQUENCE_9_STATUS.md, SEQUENCE_10_STATUS.md, floodguard/registry/seed.py and the frozen
  authoritative plan, particularly section 3.7 and revised Sequences 11-16 and 19.
