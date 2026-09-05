"""Deterministic terrain-grid serialization and small-grid QA helpers."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pyproj import Transformer

from floodguard.terrain.contracts import (
    TerrainGrid,
    TerrainPackage,
)

FloatGrid = NDArray[np.float64]


def grid_array(grid: TerrainGrid) -> FloatGrid:
    """Return a copy with null source cells represented as NaN."""
    values = np.full((grid.height, grid.width), np.nan, dtype=np.float64)
    for row_index, row in enumerate(grid.elevations_m):
        for column_index, value in enumerate(row):
            if value is not None:
                values[row_index, column_index] = value
    return values


def grid_from_array(template: TerrainGrid, values: FloatGrid) -> TerrainGrid:
    """Build a validated grid while preserving the immutable spatial metadata."""
    if values.shape != (template.height, template.width):
        raise ValueError("terrain array shape does not match the grid metadata")
    elevations: list[list[float | None]] = []
    for row in values:
        elevations.append([
            None if not math.isfinite(float(value)) else float(value)
            for value in row
        ])
    return template.model_copy(update={"elevations_m": elevations})


def package_bytes(package: TerrainPackage) -> bytes:
    """Canonical bytes used for immutable source-package fingerprints."""
    return json.dumps(
        package.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def decode_package(payload: bytes) -> TerrainPackage:
    """Decode a versioned JSON terrain package from the immutable raw vault."""
    try:
        raw: Any = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("terrain input must be a UTF-8 JSON terrain package") from exc
    if not isinstance(raw, dict):
        raise ValueError("terrain input package must be a JSON object")
    return TerrainPackage.model_validate(raw)


def artifact_bytes(
    *,
    product: str,
    terrain_id: str,
    package: TerrainPackage,
    grid: TerrainGrid | None = None,
) -> bytes:
    """Serialize a terrain artifact with explicit product identity and lineage."""
    document: dict[str, Any] = {
        "artifact_version": "sequence-6-grid-v1",
        "product": product,
        "terrain_id": terrain_id,
        "pilot_area_id": package.pilot_area_id,
        "source_surface_type": package.source_surface_type.value,
        "native_horizontal_resolution_m": package.native_horizontal_resolution_m,
        "computational_resolution_m": package.computational_resolution_m,
        "effective_information_resolution_m": package.effective_information_resolution_m,
        "vertical_quality": package.vertical_quality.value,
        "vertical_datum": package.vertical_datum,
        "vertical_unit": package.vertical_unit,
        "datum_transform_status": package.datum_transform_status.value,
        "grid": (grid or package.grid).model_dump(mode="json"),
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _transform_bounds(
    bounds: list[float],
    *,
    transformer: Transformer,
) -> list[float]:
    minimum_x, minimum_y, maximum_x, maximum_y = bounds
    points = [
        transformer.transform(minimum_x, minimum_y),
        transformer.transform(minimum_x, maximum_y),
        transformer.transform(maximum_x, minimum_y),
        transformer.transform(maximum_x, maximum_y),
    ]
    longitudes = [float(point[0]) for point in points]
    latitudes = [float(point[1]) for point in points]
    return [min(longitudes), min(latitudes), max(longitudes), max(latitudes)]


def qa_geojson(
    *,
    package: TerrainPackage,
    visual: TerrainGrid,
    hydraulic: TerrainGrid,
    terrain_id: str,
    max_cells: int = 2500,
) -> dict[str, Any]:
    """Create a bounded WGS84 QA layer without pretending it is a simulation raster."""
    if max_cells < 1:
        raise ValueError("max_cells must be positive")
    transformer = Transformer.from_crs(visual.crs, "EPSG:4326", always_xy=True)
    stride = max(
        1,
        math.ceil(math.sqrt((visual.width * visual.height) / max_cells)),
    )
    features: list[dict[str, Any]] = []
    visual_values = grid_array(visual)
    hydraulic_values = grid_array(hydraulic)
    for row in range(0, visual.height, stride):
        for column in range(0, visual.width, stride):
            visual_value = visual_values[row, column]
            hydraulic_value = hydraulic_values[row, column]
            if not math.isfinite(float(visual_value)):
                continue
            x0 = visual.origin_x_m + column * visual.cell_size_m
            y0 = visual.origin_y_m + row * visual.cell_size_m
            x1 = x0 + visual.cell_size_m * stride
            y1 = y0 + visual.cell_size_m * stride
            corners = [
                transformer.transform(x0, y0),
                transformer.transform(x1, y0),
                transformer.transform(x1, y1),
                transformer.transform(x0, y1),
                transformer.transform(x0, y0),
            ]
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[float(x), float(y)] for x, y in corners]],
                    },
                    "properties": {
                        "feature_kind": "TERRAIN_CELL",
                        "terrain_id": terrain_id,
                        "raw_elevation_m": float(visual_value),
                        "hydraulic_elevation_m": (
                            None
                            if not math.isfinite(float(hydraulic_value))
                            else float(hydraulic_value)
                        ),
                        "conditioning_delta_m": (
                            None
                            if not math.isfinite(float(hydraulic_value))
                            else float(hydraulic_value - visual_value)
                        ),
                    },
                }
            )

    for structure in package.multi_level_structures:
        bounds = _transform_bounds(structure.bounds_working, transformer=transformer)
        west, south, east, north = bounds
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[west, south], [east, south], [east, north], [west, north], [west, south]]
                    ],
                },
                "properties": {
                    "feature_kind": "MULTI_LEVEL_STRUCTURE",
                    "terrain_id": terrain_id,
                    "structure_id": structure.structure_id,
                    "kind": structure.kind.value,
                    "lower_elevation_m": structure.lower_elevation_m,
                    "upper_elevation_m": structure.upper_elevation_m,
                    "upper_level_role": structure.upper_level_role,
                    "lower_level_role": structure.lower_level_role,
                    "confidence": structure.confidence,
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
