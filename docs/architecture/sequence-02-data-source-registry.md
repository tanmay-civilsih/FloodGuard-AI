# Sequence 2 — Data Source Registry

Sequence 2 implements the authoritative catalogue of external datasets and feeds used by FloodGuard-AI.

The registry records provider, dataset name, city, category, endpoint, access method, format, licence, redistribution policy, automation permission, authentication type, credential reference, authority level, CRS/datum metadata, spatial/temporal resolution, refresh policy, fallback source/strategy, status, terms URL, and verification time.

Important rules:

- `credential_ref` stores only references such as `env://EARTHDATA_TOKEN`; raw secrets are rejected.
- `OPEN_AUTOMATED` sources must explicitly permit automation.
- `PUBLIC_VIEW_ONLY`, `OPEN_MANUAL`, and `UNKNOWN` sources are never marked as automated.
- Planned IMD radar/nowcast, LiDAR, SCADA, drain-sensor, and CCTV integrations remain non-operational until access is approved.
- OpenStreetMap is treated as ODbL data, with bounded Overpass use and Geofabrik PBF as the repeat/bulk fallback.
- The registry distinguishes documented catalogue completeness from actual operational availability.

The registry API exposes list, detail, create, replace, and readiness endpoints. Hard deletion is intentionally not exposed so source history and provenance are not silently erased.
