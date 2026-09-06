"""Strict geometry validation and narrowly governed source-topology repair.

Coordinates are x/y (longitude/latitude for geographic degree-based CRSs).
Extra z values remain source annotations, not vertically validated elevations.
Generic invalid input is rejected. The one optional repair path is limited to
polygon self-intersections where GEOS ``make_valid(linework)`` preserves the
source boundary linework and envelope within a very small source-CRS tolerance.
"""

from __future__ import annotations

import json
import math
from importlib import import_module
from typing import Any, cast

TOPOLOGY_REPAIR_PROPERTY = "_floodguard_topology_repair"
TOPOLOGY_REPAIR_METHOD = "GEOS_MAKE_VALID_LINEWORK_SELF_INTERSECTION_V1"


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


def _validate_geometry_structure(value: object, *, geographic: bool) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("geometry must be a non-null object")
    geometry = cast(dict[str, object], value)
    kind = geometry.get("type")
    if not isinstance(kind, str):
        raise ValueError("geometry type must be a string")
    coordinates = geometry.get("coordinates")
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
            _validate_geometry_structure(
                {"type": child_kind, "coordinates": child}, geographic=geographic
            )
    elif kind == "GeometryCollection":
        children = geometry.get("geometries")
        if not isinstance(children, list) or not children:
            raise ValueError("geometry collection requires nonempty geometries")
        for child in children:
            _validate_geometry_structure(child, geographic=geographic)
    else:
        raise ValueError(f"unsupported geometry type: {kind!r}")
    return geometry


def _shape(value: dict[str, object]) -> Any:
    geometry_api = import_module("shapely.geometry")
    try:
        return geometry_api.shape(value)
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("invalid geometry coordinate structure") from exc


def validate_geometry(value: object, *, geographic: bool) -> None:
    """Validate coordinate structure and GEOS topology without silently repairing it."""
    geometry_value = _validate_geometry_structure(value, geographic=geographic)
    geometry = _shape(geometry_value)
    validation_api = import_module("shapely.validation")
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError(f"invalid geometry topology: {validation_api.explain_validity(geometry)}")


def repair_linework_preserving_self_intersection(
    value: object, *, geographic: bool,
) -> tuple[dict[str, object], dict[str, object] | None]:
    """Repair only polygon self-intersections without moving source boundary linework.

    This is deliberately not a generic ``make_valid`` escape hatch. Other topology
    errors, collapsed/collection results, moved linework, changed envelopes, malformed
    coordinate arrays, and unsupported geometry types remain hard failures.
    """
    geometry_value = _validate_geometry_structure(value, geographic=geographic)
    kind = geometry_value.get("type")
    geometry = _shape(geometry_value)
    validation_api = import_module("shapely.validation")
    if not geometry.is_empty and geometry.is_valid:
        return geometry_value, None
    reason = str(validation_api.explain_validity(geometry))
    allowed_reason = reason.startswith("Self-intersection[") or reason.startswith(
        "Ring Self-intersection["
    )
    if kind not in {"Polygon", "MultiPolygon"} or not allowed_reason:
        raise ValueError(f"invalid geometry topology: {reason}")

    shapely_api = import_module("shapely")
    repaired = shapely_api.make_valid(geometry, method="linework", keep_collapsed=True)
    if repaired.is_empty or not repaired.is_valid or repaired.geom_type not in {
        "Polygon", "MultiPolygon",
    }:
        raise ValueError(
            "self-intersection repair did not produce a nonempty valid polygonal geometry"
        )

    tolerance = 1e-9 if geographic else 1e-6
    boundary_distance = float(geometry.boundary.hausdorff_distance(repaired.boundary))
    source_bounds = tuple(float(item) for item in geometry.bounds)
    repaired_bounds = tuple(float(item) for item in repaired.bounds)
    envelope_delta = max(
        abs(source - fixed) for source, fixed in zip(source_bounds, repaired_bounds, strict=True)
    )
    if (
        not math.isfinite(boundary_distance)
        or not math.isfinite(envelope_delta)
        or boundary_distance > tolerance
        or envelope_delta > tolerance
    ):
        raise ValueError(
            "self-intersection repair would alter source boundary linework or envelope"
        )

    geometry_api = import_module("shapely.geometry")
    mapped = json.loads(json.dumps(geometry_api.mapping(repaired), allow_nan=False))
    repaired_value = _validate_geometry_structure(mapped, geographic=geographic)
    repaired_check = _shape(repaired_value)
    if repaired_check.is_empty or not repaired_check.is_valid:
        raise ValueError("repaired polygon failed final topology validation")
    metadata: dict[str, object] = {
        "method": TOPOLOGY_REPAIR_METHOD,
        "source_validity_reason": reason,
        "source_geometry_type": kind,
        "repaired_geometry_type": repaired.geom_type,
        "boundary_hausdorff_source_units": boundary_distance,
        "envelope_delta_source_units": envelope_delta,
        "acceptance_tolerance_source_units": tolerance,
        "linework_preserved": True,
    }
    return repaired_value, metadata
