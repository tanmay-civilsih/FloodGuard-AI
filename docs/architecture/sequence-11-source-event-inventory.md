# Sequence 11 candidate inventory

Inventory date: 7 September 2026. This is the complete bounded candidate set considered for
this prototype step, not a citywide flood-event catalogue. All dates below are UTC.
No candidate has a TRAIN/TUNE/TEST assignment. No event has accepted measured flood labels.

## Pilot and candidate windows

The real retained context is Ward 7 twin `a73bc1b5-ec4e-5291-825f-aed596d97999`,
`REAL_PILOT_PROVISIONAL / VISUAL_ONLY`. Ward 7 is a study area; a connected catchment and
event-date engineering conditions are not verified. DATA-08-01 remains unresolved.

| Candidate | Window | Reason for consideration | Selection/availability |
|---|---|---|---|
| September 2021 wet spell | 2021-09-19 through 2021-09-22 exclusive | Bounded historical precipitation sample; three adjacent wet days in the actual source | Numerical POWER response acquired; 20 September selected for visible replay; all three days are one storm-group candidate |
| Later monsoon comparison | 2023-09-20 through 2023-09-23 exclusive | Distinct later year for eventual chronological comparison | Not acquired; rainfall and flood occurrence unverified; candidate dates do not assert a storm |
| Winter dry-control candidate | 2022-01-10 through 2022-01-13 exclusive | Contrasting season and false-positive control candidate | Not acquired; actual dryness unverified; must be measured before classifying dry |

The chosen 2021 day is a rainfall demonstration, not a claimed independent flood-validation
event. Its 51.90375 mm coarse estimate supports ingestion, unit and display checks only.
Neither the two other days in that wet spell nor sliding three-hour windows may be split
across training and independent testing. Additional event labels and a locked split are
prerequisites for later model evaluation. The inventory deliberately keeps unverified
candidates separate from retained data.

## Concrete feeds and access state

`python -m floodguard.history.catalogue` registers six idempotent candidate records without
downloading or changing existing operator permissions. The concrete POWER selection adds
its own URL-derived source record through acquisition.

| Product | Current implementation/data state | Actual access boundary |
|---|---|---|
| NASA POWER hourly PRECTOTCORR, UTC, selected point/dates | Implemented adapter and real immutable acquisition | Public automated endpoint; no credential required for the observed request. [Official API](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/) |
| GPM_3IMERGHH_07 Final, half-hourly, 0.1° | Registered candidate; no numerical granule acquired | Selected GES DISC archive requires Earthdata access setup; `env://EARTHDATA_TOKEN` is a reference, not evidence that a credential exists. Final is retrospective. [NASA product](https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGHH_07/summary), [NASA IMERG](https://gpm.nasa.gov/data/imerg) |
| ERA5 hourly pressure levels | Registered atmospheric-state candidate; not acquired | CDS account/token and manual product-terms acceptance required. No accepted account state assumed. [Product](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-pressure-levels) |
| ERA5 hourly single levels | Registered atmospheric-state candidate; not acquired | Same CDS boundary; local surface-only selection is insufficient for GraphCast. [Product](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels), [CDS API setup](https://cds.climate.copernicus.eu/how-to-api) |
| IMD Kolkata AWS/ARG numerical rainfall archive | Unverified capability; no station sample retained | Exact station, periods, QC, archive retention and authorization unknown. [Provider](https://mausam.imd.gov.in/) is contact context, not proof of an open archive |
| IMD Kolkata numerical radar archive | Unverified capability; no numerical sample retained | Exact product, format, coverage, licensing and access unknown. A public image does not satisfy this requirement |
| KMC dated flood depths/extents/water levels | Unavailable to this implementation | No dated numerical evidence, local depth reference or vertical datum supplied. [Provider](https://www.kmcgov.in/) is contact context |

Old broad source catalogue records are preserved. New product-specific records use PLANNED
and disable automated acquisition until verified. Registry completeness does not imply
feed availability. Candidate registration never edits authorization flags to make a download work.

## GraphCast atmospheric archive preflight

The upstream GraphCast URL now redirects to WeatherNext. Use its explicit
[GraphCast documentation](https://github.com/google-deepmind/weathernext/blob/main/docs/weathernext1_graph/README.md)
when planning Sequence 16; do not silently substitute WeatherNext 2 or its checkpoints.
The full GraphCast candidate is the 0.25°/37-level model trained through 2017.
The operational variant has a different 13-level/HRES contract and training overlap through
2021. A 2021 demonstration cannot automatically be independent of that variant's training.
These are inventory choices; no checkpoint or model environment is activated.

[WeatherBench 2's primary data guide](https://weatherbench2.readthedocs.io/en/latest/data-guide.html)
lists the full 37-level hourly ERA5 Zarr archive:
`gs://weatherbench2/datasets/era5/1959-2023_01_10-full_37-1h-0p25deg-chunk-1.zarr`.
Its common smaller archives use 13 levels and cannot silently stand in for the full model.
The archive's own LICENSE and exact coordinate/variable metadata require verification before
acquisition. Public listing is not an accepted license or retained compatible bundle.

For a bounded initial state, inventory two global times six hours apart, selected checkpoint
pressure levels, surface/pressure variables, static fields, normalization statistics and future
astronomical forcings. Pin exact coordinate order, units, accumulated-precipitation semantics,
source availability and checksums before constructing tensors. No local weather CSV is a substitute.

No initial-state bundle was acquired in Sequence 11. A rough float32 lower-bound calculation
for just six pressure-level fields at two times is
`1440 × 721 × 37 × 6 × 2 × 4 = 1,843,914,240 bytes` before surface/static fields or work arrays.
That exceeds this adapter's 2 MB per-request bound and requires a separate chunk-aware
archive/compute plan and accepted product access. Sequence 16 must perform that preflight,
pin the upstream revision/checkpoint and acquire verified inputs before claiming GraphCast runs.
This is a deferred resource-dependent output permitted by Sequence 11, not model-readiness evidence.
