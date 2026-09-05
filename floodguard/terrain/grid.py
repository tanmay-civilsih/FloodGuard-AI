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
        elevations.append(
            [None if not math.isfinite(float(value)) else float(value) for value in row]
        )
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

    def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate terrain JSON key: {key}")
            result[key] = value
        return result

    try:
        raw: Any = json.loads(payload.decode("utf-8"), object_pairs_hook=unique_keys)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
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
        "derivation": package.derivation.model_dump(mode="json") if package.derivation else None,
        "grid": (grid or package.grid).model_dump(mode="json"),
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _transformed_ring(
    bounds: list[float],
    *,
    transformer: Transformer,
) -> list[list[float]]:
    minimum_x, minimum_y, maximum_x, maximum_y = bounds
    ring: list[list[float]] = []
    for x, y in [
        (minimum_x, minimum_y),
        (maximum_x, minimum_y),
        (maximum_x, maximum_y),
        (minimum_x, maximum_y),
        (minimum_x, minimum_y),
    ]:
        longitude, latitude = transformer.transform(x, y, errcheck=True)
        if not (
            math.isfinite(longitude)
            and math.isfinite(latitude)
            and -180 <= longitude <= 180
            and -90 <= latitude <= 90
        ):
            raise ValueError("terrain QA transformation produced invalid WGS84 coordinates")
        ring.append([float(longitude), float(latitude)])
    return ring


def _sample_ordinals(population: int, count: int) -> set[int]:
    count = min(population, count)
    if count <= 0:
        return set()
    if count == 1:
        return {population // 2}
    return {index * (population - 1) // (count - 1) for index in range(count)}


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
    metadata = package.grid.model_dump(exclude={"elevations_m"})
    if any(grid.model_dump(exclude={"elevations_m"}) != metadata for grid in (visual, hydraulic)):
        raise ValueError("QA grids must share source grid metadata")
    transformer = Transformer.from_crs(visual.crs, "EPSG:4326", always_xy=True)
    valid_cells = sum(value is not None for row in visual.elevations_m for value in row)
    priority = sorted({(item.row, item.column) for item in package.interventions})
    for row, column in priority:
        if (
            row >= visual.height
            or column >= visual.width
            or visual.elevations_m[row][column] is None
        ):
            raise ValueError("QA intervention must address an in-grid elevation cell")
    priority_set = set(priority)
    selected = {priority[index] for index in _sample_ordinals(len(priority), max_cells)}
    remaining = max_cells - len(selected)
    background = _sample_ordinals(valid_cells - len(priority), remaining)
    ordinal = 0
    for row, values in enumerate(visual.elevations_m):
        for column, value in enumerate(values):
            if value is None or (row, column) in priority_set:
                continue
            if ordinal in background:
                selected.add((row, column))
            ordinal += 1
    features: list[dict[str, Any]] = []
    for row, column in sorted(selected):
        visual_value = visual.elevations_m[row][column]
        hydraulic_value = hydraulic.elevations_m[row][column]
        x0 = visual.origin_x_m + column * visual.cell_size_m
        y0 = visual.origin_y_m + row * visual.cell_size_m
        x1 = x0 + visual.cell_size_m
        y1 = y0 + visual.cell_size_m
        corners = _transformed_ring([x0, y0, x1, y1], transformer=transformer)
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [corners],
                },
                "properties": {
                    "feature_kind": "TERRAIN_CELL",
                    "terrain_id": terrain_id,
                    "row": row,
                    "column": column,
                    "raw_elevation_m": visual_value,
                    "hydraulic_elevation_m": hydraulic_value,
                    "conditioning_delta_m": (
                        None
                        if hydraulic_value is None or visual_value is None
                        else float(hydraulic_value - visual_value)
                    ),
                },
            }
        )

    for structure in package.multi_level_structures:
        ring = _transformed_ring(structure.bounds_working, transformer=transformer)
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [ring],
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
                    "source_reference": structure.source_reference,
                },
            }
        )
    points = _transformed_ring(visual.bounds, transformer=transformer)
    for feature in features:
        points.extend(feature["geometry"]["coordinates"][0])
    return {
        "type": "FeatureCollection",
        "features": features,
        "bbox": [
            min(p[0] for p in points),
            min(p[1] for p in points),
            max(p[0] for p in points),
            max(p[1] for p in points),
        ],
        "sampling": {
            "method": "actual-cells-intervention-first-v1",
            "total_cells": visual.width * visual.height,
            "valid_cells": valid_cells,
            "displayed_cells": len(selected),
            "omitted_cells": valid_cells - len(selected),
            "omitted_intervention_cells": len(priority_set - selected),
            "max_cells": max_cells,
            "sampled": len(selected) < valid_cells,
        },
    }


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
