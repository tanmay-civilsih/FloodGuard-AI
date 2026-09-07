# Sequence 11: historical rainfall and compatibility

Release v1.1, ROADMAP-R2-2026-09-07. The interface freeze and retained evidence are
recorded in [SEQUENCE_11_STATUS.md](../../SEQUENCE_11_STATUS.md). This is the independent
rainfall-data gate allowed by R2. DATA-08-01 and the ineligible real twin remain unchanged.

## Implemented flow

Explicit POWER selection → governed source registration → immutable raw acquisition →
hourly observation normalization → exact twin/study-area binding → consecutive three-hour
Sequence 10 forcing packages → immutable historical event → read-only rainfall preview.

No acquisition, training, state initialization or simulation is started from the preview.
The CLI reuses complete retained acquisitions by default; `--refresh` explicitly requests
another provider response. The current source permission is checked even before reuse.
Transient acquisition errors retry at most three whole bounded requests, with 1 s and 2 s
delays. Interrupted single-response downloads restart; no HTTP Range/resume support or
paging is asserted for POWER. Completed selections resume from the raw vault. Refresh may
produce a new version, including when the provider's response metadata changes.

## Contracts and ownership

- `historical-event-v1` identifies one event and references its request, raw acquisition,
  normalized observations, decoder metadata, exact twin and ordered forcing windows.
  Its request carries event-date infrastructure assumptions and catchment evidence.
- `history-request-v1` declares whole-hour event boundaries, a 1–31 UTC-day acquisition,
  an exact twin, study/catchment identity, an explicit regional spatial assumption and
  0–24 hours of antecedent. All grid corners must be within 25 km of the selected point.
  This is a conservative prototype application bound, not an asserted native grid footprint.
- `ObservationRecord` distinguishes rainfall rate (mm/h), interval accumulation (mm),
  flood depth (m relative to local surface) and water level (m with a vertical reference).
  A missing/rejected observation has a null value, never a zero placeholder. Source support,
  QC, geometry, uncertainty when supplied, and version remain explicit. No flood extent
  adapter or measured flood observations are available; an extent mask must not be passed
  as a depth or water-level number.
- `SourceAvailabilityRecord` retains valid support, source issue time when supplied,
  acquisition time, revision, historical availability status and evidence. VERIFIED requires
  an evidenced provider publication time. ESTIMATED requires its own latency policy and
  remains ineligible for strict backtests. UNKNOWN cannot assert a publication time.
- `EvaluationDatasetDefinition` freezes whole-event TRAIN/TUNE/TEST assignments,
  target/features and label quality into a canonical SHA-256. Storm groups cannot cross
  splits; splits are chronological and nonoverlapping. An optional base-model cutoff rejects
  overlapping evaluation storms. The CLI validates/exports this definition; it does not
  create a trained model or assert that referenced event labels have been scientifically accepted.

`historical_event_id` is not the existing messaging-envelope `event_id`. The Sequence 10
forcing package has no serialized `rain_event_id`; the new event's window references define
the relationship without adding fields to old forcing bytes. Hydraulic state continuity is
explicitly `NOT_INITIALIZED_RAINFALL_ONLY`. Consecutive rain windows do not prove continuous
hydraulic state. Sequence 14 owns initialization and state handoff.

Separate adapters normalize authorized station intervals and gridded POWER point extraction.
Station geometry is transformed to EPSG:4326 with explicit CRS; intervals normalize to UTC.
Cumulative counters require a same-epoch nondecreasing pair. Reset ambiguity fails rather than
inventing an increment. Identical source/station/interval/version duplicates coalesce;
conflicting duplicates fail and corrections require a new version. No gauge-to-grid interpolation,
radar bias adjustment, storm-motion estimate or automatic fallback is implemented here.

## Actual numerical source and units

The demonstration uses NASA POWER hourly PRECTOTCORR at 88.3639 E, 22.5726 N,
19–21 September 2021 UTC inclusive. The visible event is 20 September UTC, preceded by
three declared hours. It is a numerical MERRA-2 reanalysis estimate, not a station observation.
POWER describes MERRA-2's native grid as 0.5° latitude × 0.625° longitude; the adapter carries
65,000 m as a conservative approximate support value. A requested extraction coordinate
does not identify a measured station or exact cell boundary.
[NASA source methodology](https://power.larc.nasa.gov/docs/methodology/data/sources/).

The response declares `mm/day` even though the general hourly API documentation lists
hourly precipitation units. The adapter follows explicit response units: mm/day rates / 24
become mm/h; mm/hour, mm/hr and mm/h remain unchanged. Ambiguous units fail. Original bytes
and conversion metadata remain retained. The timestamp is the start of its one-hour averaging
interval. [Hourly API](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/),
[timestamp convention](https://power.larc.nasa.gov/docs/faqs/other/).

Independent hourly-versus-daily product check, at this same extraction point and UTC dates:

| UTC date | Integrated hourly estimate, mm | Daily response, mm |
|---|---:|---:|
| 2021-09-19 | 47.027500 | 47.03 |
| 2021-09-20 | 51.903750 | 51.90 |
| 2021-09-21 | 27.234583 | 27.23 |

The 0.006 mm comparison tolerance accounts for provider decimal rounding. This is a unit
consistency test, not a rainfall-skill or hydraulic validation tolerance. A daily accumulation
alone is never expanded into a fabricated hourly storm. Rainfall volume uses
`V = sum(rate_mm_h × interval_hours × cell_area_m2 / 1000)`. Existing Sequence 10 remapping
and its conservation tolerance remain authoritative. Applying a coarse estimate uniformly
over a small study area creates no new spatial information.

## Persistence and compatibility

Migration `0010_sequence_11_history` adds only the `historical_events` catalogue and city
index. No old table, ID, schema, raw object or policy is rewritten. Event bytes and supporting
artifacts reuse the existing content-addressed scientific blob store. Reads verify checksums,
decode the original raw data again, compare normalized observations and verify each window's
forcing request. A rehashed but semantically different window or observation is rejected.
Repeated builds against the same source software and retained input produce the same event ID.
The exact source fingerprint is retained; later source changes intentionally create new products.

The deployed v1 reference package
`e82ca9de-a4da-5ec1-b9cc-f097a8f1aa1c` is retained as the compatibility anchor. Its manifest,
request, Zarr and other blobs are verified through the updated readers and recreated into an
empty forcing catalogue using retained blobs. The old writer schema remains unchanged.

Sequence 11 exposed one Sequence 10 defect: a provisional imported drainage envelope has
no `model` key. Forcing assessment now reads model definitions only when the verified twin
declares an AVAILABLE drain graph. Provisional linework remains insufficient for hydraulic
use, while genuine rainfall can be packaged. Both assembled-model behavior and the
provisional-envelope regression are tested.

## Demonstration and operator commands

Use Python 3.12 with the pinned dependencies and the running local Compose services.
Inside the API container, execute:

```bash
python -m floodguard.history.catalogue
python -m floodguard.history.build --acquire-power docs/examples/sequence-11-power-selection.json --output artifacts/sequence11/acquisition.json
python -m floodguard.history.demo --twin-id a73bc1b5-ec4e-5291-825f-aed596d97999 --dataset-version-id <retained-dataset-version> --selection docs/examples/sequence-11-power-selection.json --output artifacts/sequence11/event-request.json
python -m floodguard.history.build --request artifacts/sequence11/event-request.json --dry-run
python -m floodguard.history.build --request artifacts/sequence11/event-request.json --output artifacts/sequence11/event-manifest.json
python -m floodguard.history.build --export-preview <historical-event-id> --output artifacts/sequence11/rainfall-preview.html
```

Replace retained IDs only through deliberate source/twin selection. The demo requires the
existing real pilot; it will refuse a reference fixture. `--recreate-manifest` validates the
retained evidence and reconstructs a missing event catalogue entry without acquiring new data.
`--validate-dataset` checks a proposed evaluation definition and exports its canonical split hash.

Read-only endpoints:

- `GET /history/preview`: event selector, map, hourly/accumulated charts, time slider and playback.
- `GET /history/events`: city-scoped catalogue inventory, not a claim that every entry is valid.
- `GET /history/events/{historical_event_id}`: verified event manifest.
- `GET /history/events/{historical_event_id}/view`: verified bounded data for rendering.

The preview clears stale data on failed or superseded selections, escapes source text, supports
keyboard controls, and works without external assets when exported. Missing rain breaks the
full-event accumulation curve; known partial rain is not advertised as a complete total.
Hydraulic readiness, unknown publication times and missing flood evidence remain visible.

## Verification and boundaries

Run `python scripts/sequence11_development_gate.py --event-id <id> --repository-commit <HEAD>
--run-checks --output artifacts/sequence11/development-gate.json` in Python 3.12.
Node.js must be on PATH for the existing and new browser-behavior harnesses. The gate repeats
the Sequence 8/9/10 readiness predicates, checks deployed source parity and old artifacts,
rebuilds the real event, and recreates both catalogues in isolated SQLite tables.
The older release-specific gate scripts and receipts remain historical, unchanged.

An inherited DATA-08-01 failure remains recorded; under R2 it does not fail the independent
rainfall-data interface gate. Missing event-date terrain/drainage validity, stages, pumps,
gauges, radar and measured flood labels prohibit hydraulic reconstruction or flood-skill claims.
No GraphCast execution, XGBoost fit, forecast probability, warning or route is introduced.
