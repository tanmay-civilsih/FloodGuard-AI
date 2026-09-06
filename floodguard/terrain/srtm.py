"""Bounded conversion of an original SRTMGL1 HGT tile to a metric pilot grid.

Format: LP DAAC SRTM Collection User Guide v3, sections 2.0 and 2.1.4.
https://lpdaac.usgs.gov/documents/179/SRTM_User_Guide_V3.pdf
No download, vertical transformation, sink filling or DSM-to-DTM conversion occurs here.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray
from pydantic import Field, model_validator
from pyproj import Geod, Transformer

from floodguard.spatial.contracts import DatumTransformStatus
from floodguard.spatial.reference import validate_metric_working_crs
from floodguard.terrain.contracts import (
    SurfaceType,
    TerrainDerivation,
    TerrainGrid,
    TerrainInput,
    TerrainPackage,
    VerticalQuality,
    VerticalValidation,
)
from floodguard.terrain.grid import sha256

SRTM_ADAPTER_VERSION: Final = "srtmgl1-nearest-v1"
SRTM_SIDE = 3601
SRTM_BYTES = SRTM_SIDE * SRTM_SIDE * 2
SRTM_NODATA = -32768
# Resource limits for the JSON prototype, not claims about scientific accuracy.
MAX_PILOT_CELLS = 250_000
# Guide section 2.1.3 estimates 50-80 m information resolution despite 1-arc-second posts.
# Use the coarser end as a screening floor; upstream fill and local accuracy remain unverified.
SRTM_INFORMATION_FLOOR_M = 80.0
HGT_NAME = re.compile(r"^([NS])(\d{2})([EW])(\d{3})(?:\.SRTMGL1)?\.hgt$", re.I)
SRTM_METADATA = "https://lpdaac.usgs.gov/documents/179/SRTM_User_Guide_V3.pdf"


class SrtmTarget(TerrainInput):
    working_crs: str
    bounds_working: list[float] = Field(min_length=4, max_length=4)
    cell_size_m: float = Field(default=30.0, gt=0)

    @model_validator(mode="after")
    def validate_extent(self) -> SrtmTarget:
        validate_metric_working_crs(self.working_crs)
        xmin, ymin, xmax, ymax = self.bounds_working
        if xmin >= xmax or ymin >= ymax:
            raise ValueError("pilot bounds must have positive area")
        return self


class SrtmGridGeometry(TerrainInput):
    width: int
    height: int
    origin_x_m: float
    origin_y_m: float
    cell_size_m: float
    crs: str


def target_grid(target: SrtmTarget) -> SrtmGridGeometry:
    xmin, ymin, xmax, ymax = target.bounds_working
    step = target.cell_size_m
    ratios = [value / step for value in (xmin, ymin, xmax, ymax)]
    if not all(math.isfinite(value) for value in ratios):
        raise ValueError("pilot grid dimensions exceed the supported range")
    x_index, y_index = math.floor(ratios[0]), math.floor(ratios[1])
    width = math.ceil(ratios[2]) - x_index
    height = math.ceil(ratios[3]) - y_index
    if width < 1 or height < 1 or width * height > MAX_PILOT_CELLS:
        raise ValueError(f"pilot grid must contain 1 to {MAX_PILOT_CELLS} cells")
    return SrtmGridGeometry(
        width=width, height=height,
        origin_x_m=x_index * step, origin_y_m=y_index * step,
        cell_size_m=step, crs=target.working_crs,
    )


def required_srtm_tiles(target: SrtmTarget) -> list[str]:
    """Trace actual snapped cell centres, including cells beyond the unsnapped pilot bounds."""
    lon, lat = _wgs84_centres(**target_grid(target).model_dump())
    west, south = math.floor(float(lon.min())), math.floor(float(lat.min()))
    east = max(west, math.ceil(float(lon.max())) - 1)
    north = max(south, math.ceil(float(lat.max())) - 1)
    if (east - west + 1) * (north - south + 1) > 4:
        raise ValueError("pilot spans too many SRTM tiles; mosaics are unsupported")
    return [
        f"{('N' if y >= 0 else 'S')}{abs(y):02d}{('E' if x >= 0 else 'W')}{abs(x):03d}"
        for y in range(south, north + 1) for x in range(west, east + 1)
    ]


@dataclass(frozen=True, slots=True)
class HgtTile:
    west: int
    south: int
    elevations: NDArray[np.int16]


def decode_hgt(payload: bytes, filename: str) -> HgtTile:
    match = HGT_NAME.fullmatch(filename)
    if match is None:
        raise ValueError("expected an original tile name such as N22E088.hgt")
    if len(payload) != SRTM_BYTES:
        raise ValueError(
            f"SRTMGL1 HGT requires exactly {SRTM_BYTES} bytes (3601 x 3601 int16); "
            "extract the HGT from its ZIP first; GeoTIFF and 3-arc-second tiles are unsupported"
        )
    latitude = int(match[2]) * (1 if match[1].upper() == "N" else -1)
    longitude = int(match[4]) * (1 if match[3].upper() == "E" else -1)
    if not (-90 <= latitude < 90 and -180 <= longitude < 180):
        raise ValueError("HGT filename has invalid geographic coordinates")
    values = np.frombuffer(payload, dtype=">i2").reshape(SRTM_SIDE, SRTM_SIDE)
    return HgtTile(west=longitude, south=latitude, elevations=values)


def _wgs84_centres(
    *,
    width: int,
    height: int,
    origin_x_m: float,
    origin_y_m: float,
    cell_size_m: float,
    crs: str,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    validate_metric_working_crs(crs)
    if width < 1 or height < 1 or width * height > MAX_PILOT_CELLS:
        raise ValueError(f"pilot grid must contain 1 to {MAX_PILOT_CELLS} cells")
    if not all(math.isfinite(value) for value in (origin_x_m, origin_y_m, cell_size_m)):
        raise ValueError("grid coordinates and cell size must be finite")
    if cell_size_m <= 0:
        raise ValueError("cell size must be positive")
    x = origin_x_m + (np.arange(width, dtype=np.float64) + 0.5) * cell_size_m
    y = origin_y_m + (np.arange(height, dtype=np.float64) + 0.5) * cell_size_m
    xx, yy = np.meshgrid(x, y)
    inverse = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    longitude, latitude = inverse.transform(xx, yy, errcheck=True)
    lon = np.asarray(longitude, dtype=np.float64)
    lat = np.asarray(latitude, dtype=np.float64)
    if not np.all(np.isfinite(lon)) or not np.all(np.isfinite(lat)):
        raise ValueError("pilot coordinates do not project to finite WGS84 locations")
    return lon, lat


def sample_hgt_grid(
    tile: HgtTile,
    *,
    width: int,
    height: int,
    origin_x_m: float,
    origin_y_m: float,
    cell_size_m: float,
    crs: str,
) -> TerrainGrid:
    """Select nearest posts at metric cell centres; ties go east/south in source order."""
    lon, lat = _wgs84_centres(
        width=width, height=height, origin_x_m=origin_x_m, origin_y_m=origin_y_m,
        cell_size_m=cell_size_m, crs=crs,
    )
    if not (
        np.all((lon >= tile.west) & (lon <= tile.west + 1))
        and np.all((lat >= tile.south) & (lat <= tile.south + 1))
    ):
        raise ValueError(
            "pilot cell centres extend outside this HGT tile; no extrapolation is allowed"
        )
    columns = np.floor((lon - tile.west) * (SRTM_SIDE - 1) + 0.5).astype(np.int64)
    # HGT rows run north to south; TerrainGrid rows run from the southern origin northwards.
    rows = np.floor((tile.south + 1 - lat) * (SRTM_SIDE - 1) + 0.5).astype(np.int64)
    samples = tile.elevations[rows, columns]
    return TerrainGrid(
        width=width,
        height=height,
        origin_x_m=origin_x_m,
        origin_y_m=origin_y_m,
        cell_size_m=cell_size_m,
        crs=crs,
        elevations_m=[
            [None if value == SRTM_NODATA else float(value) for value in row] for row in samples
        ],
    )


def convert_srtm(
    payload: bytes,
    *,
    filename: str,
    target: SrtmTarget,
    pilot_area_id: str,
    boundary_reference: str,
) -> TerrainPackage:
    tile = decode_hgt(payload, filename)
    grid = sample_hgt_grid(tile, **target_grid(target).model_dump())
    return unassessed_srtm_package(
        tile,
        grid=grid,
        filename=filename,
        source_sha256=sha256(payload),
        pilot_area_id=pilot_area_id,
        boundary_reference=boundary_reference,
    )


def unassessed_srtm_package(
    tile: HgtTile,
    *,
    grid: TerrainGrid,
    filename: str,
    source_sha256: str,
    pilot_area_id: str,
    boundary_reference: str,
) -> TerrainPackage:
    """Source metadata for a grid already sampled from this original HGT tile."""
    native_m = native_post_spacing_m(tile)
    step = grid.cell_size_m
    return TerrainPackage(
        pilot_area_id=pilot_area_id,
        grid=grid,
        derivation=TerrainDerivation(
            adapter_version=SRTM_ADAPTER_VERSION,
            source_filename=filename,
            source_sha256=source_sha256,
            boundary_reference=boundary_reference,
            vertical_metadata_reference=SRTM_METADATA,
        ),
        source_surface_type=SurfaceType.DSM,
        vertical_datum="EGM96",
        vertical_unit="m",
        # Source datum is known, but compatibility with engineering levels is not established.
        datum_transform_status=DatumTransformStatus.UNRESOLVED,
        vertical_quality=VerticalQuality.COARSE_GLOBAL_DEM,
        native_horizontal_resolution_m=native_m,
        computational_resolution_m=step,
        effective_information_resolution_m=max(SRTM_INFORMATION_FLOOR_M, native_m, step),
        vertical_validation=VerticalValidation(
            limitations=[
                "No independent vertical controls or contextual engineering checks were imported."
            ]
        ),
        limitations=[
            "SRTMGL1 is coarse radar surface elevation, not surveyed bare-earth terrain; "
            "its acquisition epoch and upstream void filling limit urban use.",
            "The effective-information value uses an 80 m screening floor from the product guide; "
            "local resolution is not verified and upstream fill may be coarser.",
            "Nearest-post sampling does not recover street-scale depressions or add source detail; "
            "nodata is retained, and this worker performs no additional sink filling.",
            "The crop follows a documented pilot extent, not a delineated hydraulic catchment.",
            "EGM96 compatibility with local drain, stage and survey references is unresolved.",
            "Depression and multi-level structure assessments remain NOT_ASSESSED.",
        ],
    )


def native_post_spacing_m(tile: HgtTile) -> float:
    """Larger WGS84 axis spacing over the tile, conservatively rounded up to a metre."""
    geod = Geod(ellps="WGS84")
    _, _, east_spacing = geod.inv(tile.west, tile.south, tile.west + 1 / 3600, tile.south)
    _, _, north_spacing = geod.inv(tile.west, tile.south, tile.west, tile.south + 1 / 3600)
    _, _, north_top = geod.inv(tile.west, tile.south + 1 - 1 / 3600, tile.west, tile.south + 1)
    _, _, east_top = geod.inv(tile.west, tile.south + 1, tile.west + 1 / 3600, tile.south + 1)
    return float(math.ceil(max(east_spacing, north_spacing, north_top, east_top)))
