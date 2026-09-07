"""Concrete unacquired feed candidates; registration never grants access or downloads."""

import json
from uuid import uuid5

from floodguard.history.power import NAMESPACE
from floodguard.registry.contracts import SourceCreate
from floodguard.registry.database import get_session_factory
from floodguard.registry.service import RegistryService, SourceNotFoundError


def candidates() -> list[SourceCreate]:
    specs = [
        (
            "era5-pressure-levels",
            "ECMWF / Copernicus",
            "ERA5 hourly pressure levels",
            "ATMOSPHERIC_STATE",
            "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-pressure-levels",
            "INTERNATIONAL_AGENCY",
            "USER_ACCOUNT",
            "env://CDS_API_KEY",
            "AUTHORIZATION_REQUIRED",
            "CDS account/token and accepted product terms required.",
        ),
        (
            "era5-single-levels",
            "ECMWF / Copernicus",
            "ERA5 hourly single levels",
            "ATMOSPHERIC_STATE",
            "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels",
            "INTERNATIONAL_AGENCY",
            "USER_ACCOUNT",
            "env://CDS_API_KEY",
            "AUTHORIZATION_REQUIRED",
            "Requires global fields with checkpoint-specific inputs.",
        ),
        (
            "imerg-final-v07",
            "NASA GPM / GES DISC",
            "GPM_3IMERGHH_07 Final half-hourly rainfall",
            "HISTORICAL_RAINFALL",
            "https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGHH_07/summary",
            "INTERNATIONAL_AGENCY",
            "EARTHDATA_LOGIN",
            "env://EARTHDATA_TOKEN",
            "AUTHORIZATION_REQUIRED",
            "Selected archive not acquired; Final is retrospective.",
        ),
        (
            "imd-kolkata-aws-archive",
            "India Meteorological Department",
            "Kolkata AWS/ARG numerical rainfall archive candidate",
            "RAINFALL_OBSERVATION",
            "https://mausam.imd.gov.in/",
            "NATIONAL_GOVERNMENT",
            "UNKNOWN",
            None,
            "UNKNOWN",
            "Station, numerical fields, accumulation intervals, QC and archive access unverified.",
        ),
        (
            "imd-kolkata-radar-archive",
            "India Meteorological Department",
            "Kolkata numerical radar archive candidate",
            "RADAR",
            "https://mausam.imd.gov.in/",
            "NATIONAL_GOVERNMENT",
            "UNKNOWN",
            None,
            "UNKNOWN",
            "Numerical sample and historical retention unverified; images are insufficient.",
        ),
        (
            "kmc-flood-evidence",
            "Kolkata Municipal Corporation",
            "Ward 7 dated flood depth/extent and water-level evidence candidate",
            "FLOOD_OBSERVATION",
            "https://www.kmcgov.in/",
            "MUNICIPAL_PRIMARY",
            "UNKNOWN",
            None,
            "UNKNOWN",
            "No dated observations or datum supplied. Portal is contact context, not a feed.",
        ),
    ]
    records = []
    for key, provider, name, category, url, authority, auth, credential, access, note in specs:
        records.append(
            SourceCreate.model_validate(
                {
                    "source_id": uuid5(NAMESPACE, key),
                    "provider": provider,
                    "dataset_name": name,
                    "city_id": "kolkata",
                    "category": category,
                    "endpoint": url,
                    "access_method": "PORTAL",
                    "format": "Candidate product; numerical sample and decoder acceptance pending",
                    "licence": "Product-specific terms must be accepted before acquisition",
                    "redistribution_policy": "Selected-file redistribution terms unverified",
                    "automation_allowed": False,
                    "access_class": access,
                    "authentication_type": auth,
                    "credential_ref": credential,
                    "authority_level": authority,
                    "refresh_policy": "Operator verification and product selection required",
                    "fallback_strategy": "No implicit substitution or permission changes",
                    "status": "PLANNED",
                    "terms_url": url,
                    "notes": note,
                }
            )
        )
    return records


def main() -> None:
    with get_session_factory()() as session:
        registry = RegistryService(session)
        retained = []
        for source in candidates():
            try:
                result = registry.get_source(source.source_id)
            except SourceNotFoundError:
                result = registry.create_source(source)
            retained.append(result.model_dump(mode="json"))
        print(json.dumps(retained, indent=2))


if __name__ == "__main__":
    main()
