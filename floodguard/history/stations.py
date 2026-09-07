"""Authorized station interval normalization, separate from gridded POWER extraction.

Callers retain original files in the governed raw vault before using this adapter.
There is no implicit provider, access permission, zero fill or counter-reset repair.
"""

from typing import Literal

from pyproj import Transformer

from floodguard.contracts.time import UtcDateTime
from floodguard.forcing.contracts import Input, Text
from floodguard.history.contracts import ObservationRecord, SourceAvailabilityRecord
from floodguard.history.observations import deduplicate, rate_mm_h


class StationInterval(Input):
    station_id: Text
    x: float
    y: float
    horizontal_crs: Text
    start: UtcDateTime
    end: UtcDateTime
    value: float | None
    units: Literal["mm", "mm/h", "mm/day"]
    qc: Literal["VALID", "MISSING", "REJECTED"]
    support_m: float
    source: SourceAvailabilityRecord


def normalize_stations(rows: list[StationInterval]) -> list[ObservationRecord]:
    records = []
    for original in rows:
        row = StationInterval.model_validate_json(original.model_dump_json())
        lon, lat = Transformer.from_crs(
            row.horizontal_crs,
            "EPSG:4326",
            always_xy=True,
        ).transform(row.x, row.y, errcheck=True)
        if (row.qc == "VALID") != (row.value is not None):
            raise ValueError("station QC and missing value disagree")
        value = None if row.value is None else rate_mm_h(row.value, row.units, row.start, row.end)
        records.append(
            ObservationRecord(
                observation_id=f"{row.source.dataset_version_id}:{row.station_id}:{row.start.isoformat()}",
                station_or_geometry_id=row.station_id,
                quantity="RAINFALL_RATE",
                value=value,
                units="mm/h",
                interval_start=row.start,
                interval_end=row.end,
                longitude=lon,
                latitude=lat,
                evidence_kind="MEASURED",
                support="POINT",
                native_resolution_m=row.support_m,
                qc=row.qc,
                source=row.source,
            )
        )
    return deduplicate(records)
