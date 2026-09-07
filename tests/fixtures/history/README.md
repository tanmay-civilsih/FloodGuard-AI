# Retained small compatibility and unit fixtures

`power-hourly.json` and `power-daily.json` are small unmodified NASA POWER JSON responses
downloaded on 7 September 2026 local time. Selection: 88.3639 E, 22.5726 N,
2021-09-19 through 2021-09-21 inclusive, PRECTOTCORR, AG community, explicit UTC.
The URL shape and exact selection are retained in `docs/examples/sequence-11-power-selection.json`
and `floodguard/history/power.py`. Daily uses `/api/temporal/daily/point` with the same parameters.
Acknowledgement: NASA POWER and GMAO MERRA-2. No NASA endorsement is implied.

These fixtures test source decoding and hourly-versus-daily units without network dependence.
The deployed acquisition is a separately retained raw dataset version; provider response timing
metadata may differ without changing the numerical rainfall. Test helpers that move the extraction
coordinate to the synthetic twin are explicitly marked test doubles and never used as real evidence.

`sequence10-manifest.json` and `sequence10-request.json` are the pre-change retained bytes of
forcing package `e82ca9de-a4da-5ec1-b9cc-f097a8f1aa1c`. The manifest pins each associated
blob's checksum and size. The deployed gate also reads those retained blobs and recreates the
package in an empty catalogue. These are synthetic reference forcing, not real rainfall observations.
