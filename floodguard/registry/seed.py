"""Curated Kolkata source catalogue for Sequence 2.

These records document access/governance assumptions; they do not assert that every
external endpoint is operationally available. Access metadata was audited on 2026-09-04.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid5

from floodguard.registry.contracts import (
    AccessClass,
    AccessMethod,
    AuthenticationType,
    AuthorityLevel,
    SourceCategory,
    SourceCreate,
    SourceStatus,
)

SEED_NAMESPACE = UUID("94d86ea1-0209-4c70-b9d3-2c73fd91b676")
VERIFIED_AT = datetime(2026, 9, 4, tzinfo=UTC)


def seed_id(slug: str) -> UUID:
    return uuid5(SEED_NAMESPACE, slug)


OSM_GEOFABRIK_ID = seed_id("osm-geofabrik-eastern-zone")
IMERG_ID = seed_id("nasa-gpm-imerg")

PROTOTYPE_REQUIRED_CATEGORIES = (
    SourceCategory.DRAINAGE_MAP,
    SourceCategory.WARD_BOUNDARY,
    SourceCategory.CATCHMENT,
    SourceCategory.WATER_BODY,
    SourceCategory.OPENSTREETMAP,
    SourceCategory.ELEVATION,
    SourceCategory.SATELLITE_IMAGERY,
    SourceCategory.RAINFALL_OBSERVATION,
    SourceCategory.HISTORICAL_RAINFALL,
    SourceCategory.RAINFALL_NOWCAST,
    SourceCategory.RADAR,
    SourceCategory.HYDRAULIC_BOUNDARY,
    SourceCategory.LIDAR,
    SourceCategory.PUMP_SCADA,
    SourceCategory.DRAIN_SENSOR,
    SourceCategory.CCTV,
    SourceCategory.TRAFFIC,
)


def _opencity_source(
    *,
    slug: str,
    provider: str,
    dataset_name: str,
    category: SourceCategory,
    endpoint: str,
    format: str,
    authority_level: AuthorityLevel,
    spatial_resolution: str,
    temporal_resolution: str,
    refresh_policy: str,
    fallback_strategy: str,
) -> SourceCreate:
    return SourceCreate(
        source_id=seed_id(slug),
        provider=provider,
        dataset_name=dataset_name,
        city_id="kolkata",
        category=category,
        endpoint=endpoint,
        access_method=AccessMethod.CKAN,
        format=format,
        licence="Other (Public Domain), as published in OpenCity CKAN metadata",
        redistribution_policy=(
            "Public-domain dataset; preserve provider/source attribution and immutable provenance."
        ),
        automation_allowed=True,
        access_class=AccessClass.OPEN_AUTOMATED,
        authentication_type=AuthenticationType.NONE,
        authority_level=authority_level,
        horizontal_crs="Source-defined; normalize in Sequence 4",
        vertical_datum=None,
        spatial_resolution=spatial_resolution,
        temporal_resolution=temporal_resolution,
        refresh_policy=refresh_policy,
        fallback_strategy=fallback_strategy,
        status=SourceStatus.AVAILABLE,
        terms_url=endpoint,
        last_verified_at=VERIFIED_AT,
    )


def kolkata_seed_sources() -> list[SourceCreate]:
    return [
        _opencity_source(
            slug="opencity-kmc-drainage-maps",
            provider="Kolkata Municipal Corporation via OpenCity",
            dataset_name="Kolkata Drainage Maps",
            category=SourceCategory.DRAINAGE_MAP,
            endpoint="https://data.opencity.in/dataset/kolkata-drainage-maps",
            format="PDF",
            authority_level=AuthorityLevel.MUNICIPAL_PRIMARY,
            spatial_resolution="Ward drainage layout drawings; source-map dependent",
            temporal_resolution="Static / revision-based",
            refresh_policy="Check CKAN metadata before each reconstruction campaign",
            fallback_strategy=(
                "No equivalent authoritative fallback; use the last immutable verified copy and "
                "mark reconstruction input degraded if the source is unavailable."
            ),
        ),
        _opencity_source(
            slug="opencity-kmc-wards",
            provider="Kolkata Municipal Corporation via OpenCity",
            dataset_name="Kolkata Wards Information",
            category=SourceCategory.WARD_BOUNDARY,
            endpoint="https://data.opencity.in/dataset/kolkata-wards-information",
            format="KML",
            authority_level=AuthorityLevel.MUNICIPAL_PRIMARY,
            spatial_resolution="Administrative vector boundary",
            temporal_resolution="Static / revision-based",
            refresh_policy="Check CKAN metadata monthly during development",
            fallback_strategy=(
                "Retain the last verified immutable ward version; never silently substitute "
                "electoral or other administrative boundaries."
            ),
        ),
        _opencity_source(
            slug="opencity-kolkata-microwatersheds",
            provider="Government of India / SLUSI via OpenCity",
            dataset_name="Kolkata Microwatersheds Map",
            category=SourceCategory.CATCHMENT,
            endpoint="https://data.opencity.in/dataset/kolkata-microwatersheds-map",
            format="GeoJSON",
            authority_level=AuthorityLevel.NATIONAL_GOVERNMENT,
            spatial_resolution="Vector catchment/watershed/microwatershed polygons",
            temporal_resolution="Static / revision-based",
            refresh_policy="Check source metadata quarterly",
            fallback_strategy=(
                "Later derive pilot hydrologic catchments from validated hydraulic terrain, label "
                "them GIS_DERIVED, and keep them separate from this source product."
            ),
        ),
        _opencity_source(
            slug="opencity-kolkata-water-bodies",
            provider="Ministry of Jal Shakti via OpenCity",
            dataset_name="Kolkata Water Bodies Census Data",
            category=SourceCategory.WATER_BODY,
            endpoint="https://data.opencity.in/dataset/kolkata-water-bodies-census-data",
            format="KML",
            authority_level=AuthorityLevel.NATIONAL_GOVERNMENT,
            spatial_resolution="Mapped census water-body locations/features",
            temporal_resolution="2018-19 census; released 2023",
            refresh_policy="Check source metadata quarterly",
            fallback_strategy=(
                "OSM water features may supplement gaps but are lower-authority and must never "
                "silently replace the census layer."
            ),
        ),
        SourceCreate(
            source_id=OSM_GEOFABRIK_ID,
            provider="Geofabrik / OpenStreetMap contributors",
            dataset_name="Eastern Zone India OpenStreetMap Extract",
            city_id="kolkata",
            category=SourceCategory.OPENSTREETMAP,
            endpoint="https://download.geofabrik.de/asia/india/eastern-zone-latest.osm.pbf",
            access_method=AccessMethod.PBF_EXTRACT,
            format="OSM PBF",
            licence="Open Data Commons Open Database License (ODbL) 1.0",
            redistribution_policy=(
                "Attribute OpenStreetMap contributors and comply with ODbL share-alike rules for "
                "derivative databases."
            ),
            automation_allowed=True,
            access_class=AccessClass.OPEN_AUTOMATED,
            authentication_type=AuthenticationType.NONE,
            authority_level=AuthorityLevel.COMMUNITY,
            horizontal_crs="WGS84 / OSM geographic coordinates",
            spatial_resolution="Feature-level volunteered geographic data",
            temporal_resolution="Regular regional extract updates",
            refresh_policy="Prefer for repeat/bulk ingestion; cache downloaded extract and checksum",
            fallback_strategy="Use a bounded Overpass query only for small pilot areas.",
            status=SourceStatus.AVAILABLE,
            terms_url="https://www.openstreetmap.org/copyright",
            last_verified_at=VERIFIED_AT,
        ),
        SourceCreate(
            source_id=seed_id("osm-overpass-kolkata"),
            provider="OpenStreetMap contributors / public Overpass instance",
            dataset_name="Kolkata bounded OSM query",
            city_id="kolkata",
            category=SourceCategory.OPENSTREETMAP,
            endpoint="https://overpass-api.de/api/interpreter",
            access_method=AccessMethod.OVERPASS,
            format="OSM XML/JSON",
            licence="Open Data Commons Open Database License (ODbL) 1.0",
            redistribution_policy=(
                "Attribute OpenStreetMap contributors; public Overpass is fair-use infrastructure, "
                "not a bulk-download service."
            ),
            automation_allowed=True,
            access_class=AccessClass.OPEN_AUTOMATED,
            authentication_type=AuthenticationType.NONE,
            authority_level=AuthorityLevel.COMMUNITY,
            horizontal_crs="WGS84 / OSM geographic coordinates",
            spatial_resolution="Feature-level volunteered geographic data",
            temporal_resolution="Near-current with instance replication lag",
            refresh_policy=(
                "Small pilot queries only; serialize, cache, identify the client, and respect "
                "instance limits."
            ),
            fallback_source_id=OSM_GEOFABRIK_ID,
            fallback_strategy="Use Geofabrik Eastern Zone PBF for repeat or larger-area ingestion.",
            status=SourceStatus.AVAILABLE,
            terms_url="https://www.openstreetmap.org/copyright",
            last_verified_at=VERIFIED_AT,
        ),
        SourceCreate(
            source_id=seed_id("nasa-srtmgl1"),
            provider="NASA Earthdata",
            dataset_name="SRTM 1 Arc-Second Global elevation",
            city_id="kolkata",
            category=SourceCategory.ELEVATION,
            endpoint="https://www.earthdata.nasa.gov/data/catalog/lpcloud-srtmgl1-003",
            access_method=AccessMethod.PORTAL,
            format="GeoTIFF/HGT (product dependent)",
            licence=(
                "NASA Earthdata mission data: generally CC0 unless a product-specific restriction "
                "is stated"
            ),
            redistribution_policy=(
                "Retain product citation and verify product-specific restrictions before "
                "redistribution."
            ),
            automation_allowed=True,
            access_class=AccessClass.AUTHORIZATION_REQUIRED,
            authentication_type=AuthenticationType.EARTHDATA_LOGIN,
            credential_ref="env://EARTHDATA_TOKEN",
            authority_level=AuthorityLevel.INTERNATIONAL_AGENCY,
            horizontal_crs="Product-defined; commonly geographic WGS84",
            vertical_datum="Product-defined; verify before hydraulic use",
            spatial_resolution="~1 arc-second (~30 m)",
            temporal_resolution="Static elevation product",
            refresh_policy="Pin product/version; do not refresh silently",
            fallback_strategy=(
                "Use another explicitly licensed elevation product only after vertical-reference "
                "metadata is verified; resampling never creates higher information resolution."
            ),
            status=SourceStatus.AVAILABLE,
            terms_url=(
                "https://www.earthdata.nasa.gov/engage/open-data-services-software/data-use-policy"
            ),
            last_verified_at=VERIFIED_AT,
        ),
        SourceCreate(
            source_id=seed_id("copernicus-sentinel-2"),
            provider="Copernicus Data Space Ecosystem",
            dataset_name="Sentinel-2 imagery",
            city_id="kolkata",
            category=SourceCategory.SATELLITE_IMAGERY,
            endpoint="https://dataspace.copernicus.eu/",
            access_method=AccessMethod.STAC,
            format="SAFE/COG or service-dependent",
            licence=(
                "Copernicus Sentinel data: free, full and open subject to the Sentinel Data Legal "
                "Notice"
            ),
            redistribution_policy=(
                "Credit Copernicus/Sentinel as required and distinguish Sentinel data rights from "
                "other portal content."
            ),
            automation_allowed=True,
            access_class=AccessClass.AUTHORIZATION_REQUIRED,
            authentication_type=AuthenticationType.OAUTH2,
            credential_ref="env://COPERNICUS_ACCESS_TOKEN",
            authority_level=AuthorityLevel.INTERNATIONAL_AGENCY,
            horizontal_crs="Product tile CRS / metadata-defined",
            spatial_resolution="10/20/60 m by band",
            temporal_resolution="Mission revisit/product acquisition dependent",
            refresh_policy="Query only scenes required by a versioned pilot analysis",
            fallback_strategy=(
                "Use cached verified imagery or omit imagery-dependent enhancement; imagery is not "
                "a hydraulic terrain substitute."
            ),
            status=SourceStatus.AVAILABLE,
            terms_url="https://dataspace.copernicus.eu/terms-and-conditions",
            last_verified_at=VERIFIED_AT,
        ),
        SourceCreate(
            source_id=IMERG_ID,
            provider="NASA GPM / Earthdata",
            dataset_name="GPM IMERG precipitation",
            city_id="kolkata",
            category=SourceCategory.HISTORICAL_RAINFALL,
            endpoint="https://www.earthdata.nasa.gov/data/instruments/gpm-imerg",
            access_method=AccessMethod.PORTAL,
            format="HDF5/NetCDF (product dependent)",
            licence=(
                "NASA Earthdata mission data: generally CC0 unless a product-specific restriction "
                "is stated"
            ),
            redistribution_policy="Retain collection/product-version citation and provenance.",
            automation_allowed=True,
            access_class=AccessClass.AUTHORIZATION_REQUIRED,
            authentication_type=AuthenticationType.EARTHDATA_LOGIN,
            credential_ref="env://EARTHDATA_TOKEN",
            authority_level=AuthorityLevel.INTERNATIONAL_AGENCY,
            horizontal_crs="Product-defined geographic grid",
            spatial_resolution="Product-defined; not street-scale radar",
            temporal_resolution="Product-dependent sub-daily precipitation",
            refresh_policy="Pin collection/product version for replay and ingestion tests",
            fallback_strategy="Use synthetic storms for deterministic development tests.",
            status=SourceStatus.AVAILABLE,
            terms_url=(
                "https://www.earthdata.nasa.gov/engage/open-data-services-software/data-use-policy"
            ),
            last_verified_at=VERIFIED_AT,
        ),
        SourceCreate(
            source_id=seed_id("imd-rain-observation"),
            provider="India Meteorological Department",
            dataset_name="Kolkata rainfall observations candidate feed",
            city_id="kolkata",
            category=SourceCategory.RAINFALL_OBSERVATION,
            endpoint="https://mausam.imd.gov.in/",
            access_method=AccessMethod.PORTAL,
            format="Provider-dependent",
            licence="Feed-specific machine-readable reuse terms not yet established",
            redistribution_policy=(
                "Do not automate or redistribute until feed-specific permission is documented."
            ),
            automation_allowed=False,
            access_class=AccessClass.UNKNOWN,
            authentication_type=AuthenticationType.UNKNOWN,
            authority_level=AuthorityLevel.NATIONAL_GOVERNMENT,
            spatial_resolution="Station/product dependent",
            temporal_resolution="Feed dependent",
            refresh_policy="No automated refresh until access review is complete",
            fallback_source_id=IMERG_ID,
            fallback_strategy=(
                "For replay/development use versioned IMERG or synthetic forcing and never label "
                "either as an IMD observation substitute."
            ),
            status=SourceStatus.PLANNED,
            terms_url="https://mausam.imd.gov.in/",
            last_verified_at=VERIFIED_AT,
        ),
        SourceCreate(
            source_id=seed_id("imd-nowcast"),
            provider="India Meteorological Department",
            dataset_name="Kolkata operational precipitation nowcast candidate",
            city_id="kolkata",
            category=SourceCategory.RAINFALL_NOWCAST,
            endpoint="https://mausam.imd.gov.in/",
            access_method=AccessMethod.PORTAL,
            format="Provider-dependent",
            licence="Machine-readable feed terms not yet established",
            redistribution_policy="No automation or redistribution until an approved feed exists.",
            automation_allowed=False,
            access_class=AccessClass.UNKNOWN,
            authentication_type=AuthenticationType.UNKNOWN,
            authority_level=AuthorityLevel.NATIONAL_GOVERNMENT,
            spatial_resolution="Feed dependent",
            temporal_resolution="Feed dependent",
            refresh_policy="Blocked pending approved operational feed",
            fallback_strategy=(
                "Use an externally supplied forecast, replay, or synthetic storm with explicit "
                "forcing-mode and horizon-coverage labels."
            ),
            status=SourceStatus.PLANNED,
            terms_url="https://mausam.imd.gov.in/",
            last_verified_at=VERIFIED_AT,
        ),
        SourceCreate(
            source_id=seed_id("imd-dwr-radar"),
            provider="India Meteorological Department Doppler Weather Radar",
            dataset_name="Kolkata DWR radar candidate feed",
            city_id="kolkata",
            category=SourceCategory.RADAR,
            endpoint="https://mausam.imd.gov.in/",
            access_method=AccessMethod.AUTHORIZED_FEED,
            format="Radar field format to be agreed",
            licence="Operational feed rights not established for this prototype",
            redistribution_policy=(
                "No acquisition/redistribution until authorization and technical feed terms are "
                "documented."
            ),
            automation_allowed=True,
            access_class=AccessClass.AUTHORIZATION_REQUIRED,
            authentication_type=AuthenticationType.BEARER_TOKEN,
            credential_ref="env://IMD_RADAR_TOKEN",
            authority_level=AuthorityLevel.NATIONAL_GOVERNMENT,
            spatial_resolution="Radar product dependent",
            temporal_resolution="Radar scan/product dependent",
            refresh_policy="Disabled until authorization is available",
            fallback_strategy=(
                "Use externally supplied forecast or replay/synthetic forcing; never describe "
                "IMERG as a street-scale radar replacement."
            ),
            status=SourceStatus.PLANNED,
            terms_url="https://mausam.imd.gov.in/",
            last_verified_at=VERIFIED_AT,
        ),
        SourceCreate(
            source_id=seed_id("cwc-hooghly-stage"),
            provider="Central Water Commission candidate portal",
            dataset_name="Hooghly/downstream water-level candidate series",
            city_id="kolkata",
            category=SourceCategory.HYDRAULIC_BOUNDARY,
            endpoint="https://ffs.india-water.gov.in/",
            access_method=AccessMethod.PORTAL,
            format="Portal/feed dependent",
            licence="Feed-specific reuse/automation terms require confirmation",
            redistribution_policy=(
                "Public display does not imply automated reuse rights; keep view-only until a "
                "permitted feed is identified."
            ),
            automation_allowed=False,
            access_class=AccessClass.PUBLIC_VIEW_ONLY,
            authentication_type=AuthenticationType.NONE,
            authority_level=AuthorityLevel.NATIONAL_GOVERNMENT,
            vertical_datum="Must accompany each stage series",
            spatial_resolution="Gauge/location dependent",
            temporal_resolution="Gauge/feed dependent",
            refresh_policy="No automated refresh until a permitted machine-readable feed exists",
            fallback_strategy=(
                "Use a versioned replay/synthetic downstream stage for SIH and label its source and "
                "mode explicitly."
            ),
            status=SourceStatus.PLANNED,
            terms_url="https://ffs.india-water.gov.in/",
            last_verified_at=VERIFIED_AT,
        ),
        SourceCreate(
            source_id=seed_id("kmc-lidar"),
            provider="KMC / authorized survey provider",
            dataset_name="High-resolution LiDAR/terrain candidate",
            city_id="kolkata",
            category=SourceCategory.LIDAR,
            endpoint="https://www.kmcgov.in/",
            access_method=AccessMethod.MANUAL_TRANSFER,
            format="LAS/LAZ/GeoTIFF if supplied",
            licence="Dataset-specific authorization/terms unknown until supplied",
            redistribution_policy="Do not redistribute without explicit authorization.",
            automation_allowed=False,
            access_class=AccessClass.UNKNOWN,
            authentication_type=AuthenticationType.UNKNOWN,
            authority_level=AuthorityLevel.MUNICIPAL_PRIMARY,
            spatial_resolution="Unknown until supplied",
            temporal_resolution="Survey epoch dependent",
            refresh_policy="No automated refresh",
            fallback_strategy=(
                "Use documented coarse elevation for scenario-ready modelling; do not claim "
                "LiDAR-level or centimetre-level accuracy."
            ),
            status=SourceStatus.PLANNED,
            terms_url="https://www.kmcgov.in/",
            last_verified_at=VERIFIED_AT,
        ),
        SourceCreate(
            source_id=seed_id("kmc-pump-scada"),
            provider="Kolkata Municipal Corporation",
            dataset_name="Pump SCADA / operational controls",
            city_id="kolkata",
            category=SourceCategory.PUMP_SCADA,
            endpoint="https://www.kmcgov.in/",
            access_method=AccessMethod.AUTHORIZED_FEED,
            format="API/telemetry format to be agreed",
            licence="Municipal operational data; authorization required",
            redistribution_policy="Do not expose raw operational feed without authorization.",
            automation_allowed=True,
            access_class=AccessClass.AUTHORIZATION_REQUIRED,
            authentication_type=AuthenticationType.BEARER_TOKEN,
            credential_ref="env://KMC_SCADA_TOKEN",
            authority_level=AuthorityLevel.MUNICIPAL_PRIMARY,
            spatial_resolution="Asset-level",
            temporal_resolution="Telemetry-dependent",
            refresh_policy="Disabled until authorization; then use only approved cadence",
            fallback_strategy=(
                "Use versioned assumed/scenario pump schedules explicitly labelled ASSUMED."
            ),
            status=SourceStatus.PLANNED,
            terms_url="https://www.kmcgov.in/",
            last_verified_at=VERIFIED_AT,
        ),
        SourceCreate(
            source_id=seed_id("kmc-drain-sensors"),
            provider="Kolkata Municipal Corporation / approved sensor operator",
            dataset_name="Drain level/flow sensor feed",
            city_id="kolkata",
            category=SourceCategory.DRAIN_SENSOR,
            endpoint="https://www.kmcgov.in/",
            access_method=AccessMethod.AUTHORIZED_FEED,
            format="Telemetry/API format to be agreed",
            licence="Authorization required",
            redistribution_policy="Do not expose raw sensor data without authorization.",
            automation_allowed=True,
            access_class=AccessClass.AUTHORIZATION_REQUIRED,
            authentication_type=AuthenticationType.BEARER_TOKEN,
            credential_ref="env://KMC_DRAIN_SENSOR_TOKEN",
            authority_level=AuthorityLevel.MUNICIPAL_PRIMARY,
            vertical_datum="Sensor-specific datum required",
            spatial_resolution="Sensor locations",
            temporal_resolution="Telemetry-dependent",
            refresh_policy="Disabled until authorization",
            fallback_strategy=(
                "Operate without assimilation using spin-up/hotstart rules and mark state quality."
            ),
            status=SourceStatus.PLANNED,
            terms_url="https://www.kmcgov.in/",
            last_verified_at=VERIFIED_AT,
        ),
        SourceCreate(
            source_id=seed_id("kolkata-cctv"),
            provider="Kolkata traffic/civic authorities candidate",
            dataset_name="Flood-relevant CCTV observations",
            city_id="kolkata",
            category=SourceCategory.CCTV,
            endpoint="https://www.kolkatatrafficpolice.gov.in/",
            access_method=AccessMethod.PORTAL,
            format="Image/video feed dependent",
            licence="Automated access/reuse rights not established",
            redistribution_policy=(
                "Do not scrape, store, or redistribute footage until authorization and privacy "
                "rules are documented."
            ),
            automation_allowed=False,
            access_class=AccessClass.UNKNOWN,
            authentication_type=AuthenticationType.UNKNOWN,
            authority_level=AuthorityLevel.STATE_GOVERNMENT,
            spatial_resolution="Camera locations",
            temporal_resolution="Feed dependent",
            refresh_policy="No automated acquisition",
            fallback_strategy="CCTV is optional validation evidence; omit when rights are unavailable.",
            status=SourceStatus.PLANNED,
            terms_url="https://www.kolkatatrafficpolice.gov.in/",
            last_verified_at=VERIFIED_AT,
        ),
        SourceCreate(
            source_id=seed_id("osm-road-speeds"),
            provider="OpenStreetMap contributors",
            dataset_name="OSM road class/maxspeed attributes for baseline routing",
            city_id="kolkata",
            category=SourceCategory.TRAFFIC,
            endpoint="https://download.geofabrik.de/asia/india/eastern-zone-latest.osm.pbf",
            access_method=AccessMethod.PBF_EXTRACT,
            format="OSM PBF",
            licence="Open Data Commons Open Database License (ODbL) 1.0",
            redistribution_policy="Attribute OpenStreetMap contributors and comply with ODbL.",
            automation_allowed=True,
            access_class=AccessClass.OPEN_AUTOMATED,
            authentication_type=AuthenticationType.NONE,
            authority_level=AuthorityLevel.COMMUNITY,
            horizontal_crs="WGS84 / OSM geographic coordinates",
            spatial_resolution="Road-edge attributes",
            temporal_resolution="Extract update dependent; not real-time traffic",
            refresh_policy="Refresh with the versioned OSM extract",
            fallback_source_id=OSM_GEOFABRIK_ID,
            fallback_strategy=(
                "Apply documented road-class default speeds marked ASSUMED; real-time traffic is an "
                "optional future adapter."
            ),
            status=SourceStatus.AVAILABLE,
            terms_url="https://www.openstreetmap.org/copyright",
            last_verified_at=VERIFIED_AT,
        ),
    ]


def main() -> None:
    from floodguard.registry.database import get_session_factory
    from floodguard.registry.repository import RegistryRepository
    from floodguard.registry.service import RegistryService

    factory = get_session_factory()
    with factory() as session:
        inserted = RegistryRepository(session).seed_if_missing(kolkata_seed_sources())
        readiness = RegistryService(session).readiness()
    print(
        f"registry seed complete: inserted={inserted}, total={readiness.total_sources}, "
        f"catalogue_complete={readiness.catalogue_complete}"
    )


if __name__ == "__main__":
    main()
