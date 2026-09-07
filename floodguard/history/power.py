"""NASA POWER hourly point extraction; numerical reanalysis, never gauge truth."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlencode
from uuid import UUID, uuid5

from pydantic import ValidationError

from floodguard.contracts.time import utc_now
from floodguard.history.contracts import ObservationRecord, PowerSelection, SourceAvailabilityRecord
from floodguard.registry.contracts import (
    AccessClass,
    AccessMethod,
    AuthenticationType,
    AuthorityLevel,
    SourceCategory,
    SourceCreate,
    SourceStatus,
)

NAMESPACE = UUID("1a1b6a90-2c38-4589-a19c-c511bb0ade02")
DOCS = "https://power.larc.nasa.gov/docs/services/api/temporal/hourly/"
SOURCES = "https://power.larc.nasa.gov/docs/methodology/data/sources/"
TIME_DOCS = "https://power.larc.nasa.gov/docs/faqs/other/"
BASE = "https://power.larc.nasa.gov/api/temporal/hourly/point"
RESOLUTION_M = 65000.0  # Conservative approximate support; not a measured cell edge.


def selection_url(selection: PowerSelection) -> str:
    return (
        BASE
        + "?"
        + urlencode(
            {
                "parameters": "PRECTOTCORR",
                "community": "AG",
                "longitude": selection.longitude,
                "latitude": selection.latitude,
                "start": selection.start.strftime("%Y%m%d"),
                "end": (selection.end - timedelta(days=1)).strftime("%Y%m%d"),
                "format": "JSON",
                "time-standard": "UTC",
            }
        )
    )


def source_definition(selection: PowerSelection, city_id: str) -> SourceCreate:
    url = selection_url(selection)
    return SourceCreate(
        source_id=uuid5(NAMESPACE, f"{city_id}:{url}"),
        city_id=city_id,
        provider="NASA POWER / GMAO",
        dataset_name="POWER hourly PRECTOTCORR selection (MERRA-2 reanalysis candidate)",
        category=SourceCategory.HISTORICAL_RAINFALL,
        endpoint=url,
        access_method=AccessMethod.HTTP,
        format="POWER JSON hourly UTC",
        licence="NASA POWER publicly accessible data; acknowledge NASA POWER and GMAO",
        redistribution_policy="Retain acknowledgement and provenance; no endorsement implied",
        automation_allowed=True,
        access_class=AccessClass.OPEN_AUTOMATED,
        authentication_type=AuthenticationType.NONE,
        authority_level=AuthorityLevel.INTERNATIONAL_AGENCY,
        horizontal_crs="EPSG:4326",
        spatial_resolution="0.5 latitude x 0.625 longitude degrees",
        temporal_resolution="Hourly; header rate units must be decoded",
        refresh_policy="Explicit historical selection; retry whole bounded response if interrupted",
        fallback_strategy="No silent substitute; missing/rejected intervals remain unavailable",
        status=SourceStatus.AVAILABLE,
        terms_url=DOCS,
        last_verified_at=utc_now(),
        notes=f"API-based permitted access. {SOURCES}; {TIME_DOCS}. Not gauge/radar data.",
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def decode_power(
    payload: bytes,
    selection: PowerSelection,
    availability: SourceAvailabilityRecord,
) -> tuple[list[ObservationRecord], dict[str, Any]]:
    if len(payload) > 2_000_000:
        raise ValueError("POWER response exceeds bounded historical adapter size")
    try:
        data = json.loads(payload, object_pairs_hook=_unique_object)
        if data.get("type") != "Feature" or data["geometry"]["type"] != "Point":
            raise ValueError("POWER response must identify point-extracted data")
        header = data["header"]
        if header["time_standard"] != "UTC" or header["sources"] != ["MERRA2"]:
            raise ValueError("only explicit UTC MERRA2 historical responses are accepted")
        if header["start"] != selection.start.strftime("%Y%m%d") or header["end"] != (
            selection.end - timedelta(days=1)
        ).strftime("%Y%m%d"):
            raise ValueError("provider response dates differ from requested selection")
        lon, lat = data["geometry"]["coordinates"][:2]
        if (
            not math.isfinite(lon)
            or not math.isfinite(lat)
            or abs(lon - selection.longitude) > 0.002
            or abs(lat - selection.latitude) > 0.002
        ):
            raise ValueError("provider point differs from requested location")
        units = data["parameters"]["PRECTOTCORR"]["units"]
        factors = {"mm/day": 1 / 24, "mm/hour": 1.0, "mm/hr": 1.0, "mm/h": 1.0}
        if units not in factors:
            raise ValueError("unsupported or ambiguous precipitation units")
        fill = float(header["fill_value"])
        if not math.isfinite(fill) or fill >= 0:
            raise ValueError("invalid precipitation missing-value sentinel")
        raw_values = data["properties"]["parameter"]["PRECTOTCORR"]
        values = {
            datetime.strptime(key, "%Y%m%d%H").replace(tzinfo=UTC): value
            for key, value in raw_values.items()
        }
        if any(t < selection.start or t >= selection.end for t in values):
            raise ValueError("response contains observations outside selection")
        records = []
        cursor = selection.start
        while cursor < selection.end:
            raw = values.get(cursor)
            if raw is not None and type(raw) not in {int, float}:
                raise ValueError("rainfall values must be numeric or null")
            value = None if raw is None or raw == fill else float(raw) * factors[units]
            qc: Literal["VALID", "MISSING", "REJECTED"] = "MISSING" if value is None else "VALID"
            if value is not None and (not 0 <= value < float("inf")):
                value, qc = None, "REJECTED"
            records.append(
                ObservationRecord(
                    observation_id=f"{availability.dataset_version_id}:PRECTOTCORR:{cursor.isoformat()}",
                    station_or_geometry_id=f"POWER_REQUEST:{selection.longitude},{selection.latitude}",
                    quantity="RAINFALL_RATE",
                    value=value,
                    units="mm/h",
                    interval_start=cursor,
                    interval_end=cursor + timedelta(hours=1),
                    longitude=selection.longitude,
                    latitude=selection.latitude,
                    evidence_kind="REANALYSIS",
                    support="GRID_CELL_ESTIMATE",
                    native_resolution_m=RESOLUTION_M,
                    qc=qc,
                    source=availability,
                )
            )
            cursor += timedelta(hours=1)
        return records, {
            "adapter": "nasa-power-hourly-v1",
            "provider_header": header,
            "raw_units": units,
            "rate_multiplier_to_mm_h": factors[units],
            "timestamp_semantics": "Start of hour; average rate over [start,end).",
            "timestamp_evidence": TIME_DOCS,
            "spatial_support": "MERRA2 0.5 x 0.625 degrees; 65000 m conservative approximation.",
            "point_semantics": "Requested location, not a measured station or cell boundary.",
            "unit_note": "Response units govern; hourly documentation and response may differ.",
            "messages": data.get("messages", []),
        }
    except (KeyError, TypeError, OverflowError, ValidationError) as exc:
        raise ValueError("POWER response schema or values are invalid") from exc
