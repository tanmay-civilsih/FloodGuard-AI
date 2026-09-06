"""Strict GeoJSON structure/finite-coordinate checks and GEOS topology validation.

Invalid input is rejected, never automatically closed, repaired or simplified.
Coordinates are x/y (longitude/latitude for geographic degree-based CRSs).
Extra z values remain source annotations, not vertically validated elevations.
"""

from __future__ import annotations

import math
from importlib import import_module


def _position(value: object, *, geographic: bool) -> None:
    if not isinstance(value, list) or len(value) not in {2, 3}:
        raise ValueError("positions require exactly two or three ordinates")
    for coordinate in value:
        if (
            isinstance(coordinate, bool)
            or not isinstance(coordinate, int | float)
            or not math.isfinite(coordinate)
        ):
            raise ValueError("coordinate ordinates must be finite numbers, not booleans")
    if geographic and not (-180 <= value[0] <= 180 and -90 <= value[1] <= 90):
        raise ValueError("longitude/latitude outside geographic bounds")


def _positions(value: object, *, geographic: bool, ring: bool = False) -> None:
    minimum = 4 if ring else 2
    if not isinstance(value, list) or len(value) < minimum:
        raise ValueError(f"coordinate sequence requires at least {minimum} positions")
    for position in value:
        _position(position, geographic=geographic)
    if ring and value[0] != value[-1]:
        raise ValueError("polygon rings must be explicitly closed")


def validate_geometry(value: object, *, geographic: bool) -> None:
    """Validate shape before GEOS so its permissive ring closure cannot repair input."""
    if not isinstance(value, dict):
        raise ValueError("geometry must be a non-null object")
    kind = value.get("type")
    if not isinstance(kind, str):
        raise ValueError("geometry type must be a string")
    coordinates = value.get("coordinates")
    if kind == "Point":
        _position(coordinates, geographic=geographic)
    elif kind == "LineString":
        _positions(coordinates, geographic=geographic)
    elif kind == "Polygon":
        if not isinstance(coordinates, list) or not coordinates:
            raise ValueError("polygon requires at least one ring")
        for ring in coordinates:
            _positions(ring, geographic=geographic, ring=True)
    elif kind in {"MultiPoint", "MultiLineString", "MultiPolygon"}:
        if not isinstance(coordinates, list) or not coordinates:
            raise ValueError("multi-geometry requires nonempty coordinates")
        child_kind = {"MultiPoint": "Point", "MultiLineString": "LineString",
                      "MultiPolygon": "Polygon"}[kind]
        for child in coordinates:
            validate_geometry({"type": child_kind, "coordinates": child}, geographic=geographic)
    elif kind == "GeometryCollection":
        children = value.get("geometries")
        if not isinstance(children, list) or not children:
            raise ValueError("geometry collection requires nonempty geometries")
        for child in children:
            validate_geometry(child, geographic=geographic)
    else:
        raise ValueError(f"unsupported geometry type: {kind!r}")

    # Isolate the untyped GEOS boundary. Shapely is a pinned runtime dependency.
    geometry_api = import_module("shapely.geometry")
    validation_api = import_module("shapely.validation")
    try:
        geometry = geometry_api.shape(value)
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("invalid geometry coordinate structure") from exc
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError(f"invalid geometry topology: {validation_api.explain_validity(geometry)}")
