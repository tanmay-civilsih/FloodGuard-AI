"""Vector parsing and metric reprojection for Sequence 4."""

from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pyproj import CRS, Transformer


class VectorNormalizationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NormalizedVector:
    internal_feature_collection: dict[str, object]
    qa_feature_collection: dict[str, object]
    source_crs: str
    working_crs: str
    feature_count: int
    geometry_types: list[str]
    bounds_working: list[float]
    bounds_wgs84: list[float]
    max_roundtrip_error_m: float


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_coordinate_text(text: str | None) -> list[list[float]]:
    if text is None:
        return []
    positions: list[list[float]] = []
    for token in text.replace("\n", " ").replace("\t", " ").split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            position = [float(parts[0]), float(parts[1])]
            if len(parts) >= 3 and parts[2] != "":
                position.append(float(parts[2]))
        except ValueError as exc:
            raise VectorNormalizationError(f"invalid KML coordinate token: {token}") from exc
        positions.append(position)
    return positions


def _first_descendant(element: ET.Element, local_name: str) -> ET.Element | None:
    for descendant in element.iter():
        if _local_name(descendant.tag) == local_name:
            return descendant
    return None


def _descendants(element: ET.Element, local_name: str) -> list[ET.Element]:
    return [item for item in element.iter() if _local_name(item.tag) == local_name]


def _parse_kml_geometry(element: ET.Element) -> dict[str, object]:
    geometry_type = _local_name(element.tag)
    if geometry_type == "Point":
        coordinates = _first_descendant(element, "coordinates")
        positions = _parse_coordinate_text(coordinates.text if coordinates is not None else None)
        if not positions:
            raise VectorNormalizationError("KML Point has no coordinates")
        return {"type": "Point", "coordinates": positions[0]}

    if geometry_type == "LineString":
        coordinates = _first_descendant(element, "coordinates")
        positions = _parse_coordinate_text(coordinates.text if coordinates is not None else None)
        if len(positions) < 2:
            raise VectorNormalizationError("KML LineString has fewer than two positions")
        return {"type": "LineString", "coordinates": positions}

    if geometry_type == "Polygon":
        outer = _first_descendant(element, "outerBoundaryIs")
        if outer is None:
            raise VectorNormalizationError("KML Polygon has no outer boundary")
        outer_coords = _first_descendant(outer, "coordinates")
        outer_positions = _parse_coordinate_text(
            outer_coords.text if outer_coords is not None else None
        )
        if len(outer_positions) < 4:
            raise VectorNormalizationError("KML Polygon outer ring has fewer than four positions")
        rings: list[list[list[float]]] = [outer_positions]
        for inner in _descendants(element, "innerBoundaryIs"):
            inner_coords = _first_descendant(inner, "coordinates")
            inner_positions = _parse_coordinate_text(
                inner_coords.text if inner_coords is not None else None
            )
            if len(inner_positions) >= 4:
                rings.append(inner_positions)
        return {"type": "Polygon", "coordinates": rings}

    if geometry_type == "MultiGeometry":
        geometries: list[dict[str, object]] = []
        for child in element:
            child_type = _local_name(child.tag)
            if child_type in {"Point", "LineString", "Polygon", "MultiGeometry"}:
                geometries.append(_parse_kml_geometry(child))
        if not geometries:
            raise VectorNormalizationError("KML MultiGeometry has no supported geometries")
        child_types = {str(item["type"]) for item in geometries}
        if child_types == {"Point"}:
            return {
                "type": "MultiPoint",
                "coordinates": [item["coordinates"] for item in geometries],
            }
        if child_types == {"LineString"}:
            return {
                "type": "MultiLineString",
                "coordinates": [item["coordinates"] for item in geometries],
            }
        if child_types == {"Polygon"}:
            return {
                "type": "MultiPolygon",
                "coordinates": [item["coordinates"] for item in geometries],
            }
        return {"type": "GeometryCollection", "geometries": geometries}

    raise VectorNormalizationError(f"unsupported KML geometry: {geometry_type}")


def _find_top_level_kml_geometry(placemark: ET.Element) -> ET.Element | None:
    def walk(element: ET.Element) -> ET.Element | None:
        for child in element:
            name = _local_name(child.tag)
            if name in {"Point", "LineString", "Polygon", "MultiGeometry"}:
                return child
            found = walk(child)
            if found is not None:
                return found
        return None

    return walk(placemark)


def _kml_properties(placemark: ET.Element) -> dict[str, object]:
    properties: dict[str, object] = {}
    for child in placemark:
        name = _local_name(child.tag)
        if name in {"name", "description"} and child.text is not None:
            properties[name] = child.text.strip()
    for data in _descendants(placemark, "Data"):
        key = data.attrib.get("name")
        value = _first_descendant(data, "value")
        if key and value is not None and value.text is not None:
            properties[key] = value.text.strip()
    for simple_data in _descendants(placemark, "SimpleData"):
        key = simple_data.attrib.get("name")
        if key and simple_data.text is not None:
            properties[key] = simple_data.text.strip()
    return properties


def parse_kml(payload: bytes) -> tuple[dict[str, object], str]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise VectorNormalizationError(f"invalid KML XML: {exc}") from exc
    features: list[dict[str, object]] = []
    for element in root.iter():
        if _local_name(element.tag) != "Placemark":
            continue
        geometry_node = _find_top_level_kml_geometry(element)
        if geometry_node is None:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": _kml_properties(element),
                "geometry": _parse_kml_geometry(geometry_node),
            }
        )
    if not features:
        raise VectorNormalizationError("KML contains no supported Placemark geometries")
    return {"type": "FeatureCollection", "features": features}, "EPSG:4326"


def _legacy_geojson_crs(payload: dict[str, object]) -> str:
    crs_value = payload.get("crs")
    if not isinstance(crs_value, dict):
        return "EPSG:4326"
    properties = crs_value.get("properties")
    if not isinstance(properties, dict):
        return "EPSG:4326"
    name = properties.get("name")
    if not isinstance(name, str):
        return "EPSG:4326"
    upper = name.upper()
    marker = "EPSG::"
    if marker in upper:
        return f"EPSG:{upper.rsplit(marker, 1)[-1]}"
    if "EPSG:" in upper:
        return f"EPSG:{upper.rsplit('EPSG:', 1)[-1]}"
    return name


def parse_geojson(payload: bytes) -> tuple[dict[str, object], str]:
    try:
        loaded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VectorNormalizationError(f"invalid GeoJSON: {exc}") from exc
    if not isinstance(loaded, dict):
        raise VectorNormalizationError("GeoJSON root must be an object")
    source_crs = _legacy_geojson_crs(cast(dict[str, object], loaded))
    root_type = loaded.get("type")
    if root_type == "FeatureCollection":
        features = loaded.get("features")
        if not isinstance(features, list):
            raise VectorNormalizationError("GeoJSON FeatureCollection requires features")
        return {"type": "FeatureCollection", "features": features}, source_crs
    if root_type == "Feature":
        return {"type": "FeatureCollection", "features": [loaded]}, source_crs
    raise VectorNormalizationError("only GeoJSON FeatureCollection or Feature is supported")


def parse_vector(payload: bytes, filename: str) -> tuple[dict[str, object], str]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".kml":
        return parse_kml(payload)
    if suffix in {".geojson", ".json"}:
        return parse_geojson(payload)
    raise VectorNormalizationError(f"unsupported vector file extension: {suffix or '<none>'}")


def _transform_position(
    position_value: object,
    forward: Transformer,
    inverse: Transformer,
) -> tuple[list[float], float]:
    if not isinstance(position_value, list) or len(position_value) < 2:
        raise VectorNormalizationError("geometry position must contain at least x and y")
    x_value, y_value = position_value[0], position_value[1]
    if not isinstance(x_value, int | float) or not isinstance(y_value, int | float):
        raise VectorNormalizationError("geometry x/y coordinates must be numeric")
    x, y = float(x_value), float(y_value)
    target_x, target_y = forward.transform(x, y)
    source_x, source_y = inverse.transform(target_x, target_y)
    check_x, check_y = forward.transform(source_x, source_y)
    error_m = math.hypot(check_x - target_x, check_y - target_y)
    transformed = [float(target_x), float(target_y)]
    for extra in position_value[2:]:
        if isinstance(extra, int | float):
            transformed.append(float(extra))
    return transformed, error_m


def _transform_coordinates(
    value: object,
    forward: Transformer,
    inverse: Transformer,
) -> tuple[object, float]:
    if not isinstance(value, list):
        raise VectorNormalizationError("geometry coordinates must be arrays")
    if (
        len(value) >= 2
        and isinstance(value[0], int | float)
        and isinstance(value[1], int | float)
    ):
        return _transform_position(value, forward, inverse)
    transformed: list[object] = []
    max_error = 0.0
    for child in value:
        child_value, child_error = _transform_coordinates(child, forward, inverse)
        transformed.append(child_value)
        max_error = max(max_error, child_error)
    return transformed, max_error


def _transform_geometry(
    geometry_value: object,
    forward: Transformer,
    inverse: Transformer,
) -> tuple[dict[str, object] | None, float]:
    if geometry_value is None:
        return None, 0.0
    if not isinstance(geometry_value, dict):
        raise VectorNormalizationError("feature geometry must be an object or null")
    geometry = cast(dict[str, object], geometry_value)
    geometry_type = geometry.get("type")
    if not isinstance(geometry_type, str):
        raise VectorNormalizationError("geometry type is missing")
    if geometry_type == "GeometryCollection":
        geometries = geometry.get("geometries")
        if not isinstance(geometries, list):
            raise VectorNormalizationError("GeometryCollection requires geometries")
        transformed_geometries: list[dict[str, object]] = []
        max_error = 0.0
        for item in geometries:
            transformed, error = _transform_geometry(item, forward, inverse)
            if transformed is not None:
                transformed_geometries.append(transformed)
            max_error = max(max_error, error)
        return {"type": geometry_type, "geometries": transformed_geometries}, max_error
    coordinates, error = _transform_coordinates(geometry.get("coordinates"), forward, inverse)
    return {"type": geometry_type, "coordinates": coordinates}, error


def _coordinate_pairs(value: object) -> list[tuple[float, float]]:
    if not isinstance(value, list):
        return []
    if (
        len(value) >= 2
        and isinstance(value[0], int | float)
        and isinstance(value[1], int | float)
    ):
        return [(float(value[0]), float(value[1]))]
    pairs: list[tuple[float, float]] = []
    for child in value:
        pairs.extend(_coordinate_pairs(child))
    return pairs


def _geometry_pairs(geometry_value: object) -> list[tuple[float, float]]:
    if not isinstance(geometry_value, dict):
        return []
    geometry = cast(dict[str, object], geometry_value)
    if geometry.get("type") == "GeometryCollection":
        geometries = geometry.get("geometries")
        if not isinstance(geometries, list):
            return []
        pairs: list[tuple[float, float]] = []
        for item in geometries:
            pairs.extend(_geometry_pairs(item))
        return pairs
    return _coordinate_pairs(geometry.get("coordinates"))


def _bounds(feature_collection: dict[str, object]) -> list[float]:
    features = feature_collection.get("features")
    if not isinstance(features, list):
        raise VectorNormalizationError("FeatureCollection requires a feature list")
    pairs: list[tuple[float, float]] = []
    for feature_value in features:
        if not isinstance(feature_value, dict):
            continue
        pairs.extend(_geometry_pairs(feature_value.get("geometry")))
    if not pairs:
        raise VectorNormalizationError("FeatureCollection contains no coordinates")
    xs = [item[0] for item in pairs]
    ys = [item[1] for item in pairs]
    return [min(xs), min(ys), max(xs), max(ys)]


def _transform_feature_collection(
    feature_collection: dict[str, object],
    *,
    source_crs: str,
    target_crs: str,
) -> tuple[dict[str, object], float, list[str]]:
    source = CRS.from_user_input(source_crs)
    target = CRS.from_user_input(target_crs)
    forward = Transformer.from_crs(source, target, always_xy=True)
    inverse = Transformer.from_crs(target, source, always_xy=True)
    features_value = feature_collection.get("features")
    if not isinstance(features_value, list):
        raise VectorNormalizationError("FeatureCollection requires a feature list")
    transformed_features: list[dict[str, object]] = []
    geometry_types: set[str] = set()
    max_error = 0.0
    for feature_value in features_value:
        if not isinstance(feature_value, dict):
            continue
        feature = cast(dict[str, object], feature_value)
        geometry, error = _transform_geometry(feature.get("geometry"), forward, inverse)
        max_error = max(max_error, error)
        if geometry is not None and isinstance(geometry.get("type"), str):
            geometry_types.add(cast(str, geometry["type"]))
        properties_value = feature.get("properties")
        properties = properties_value if isinstance(properties_value, dict) else {}
        transformed_features.append(
            {"type": "Feature", "properties": properties, "geometry": geometry}
        )
    if not transformed_features:
        raise VectorNormalizationError("FeatureCollection contains no valid features")
    return (
        {"type": "FeatureCollection", "features": transformed_features},
        max_error,
        sorted(geometry_types),
    )


def normalize_vector(
    payload: bytes,
    filename: str,
    *,
    working_crs: str,
) -> NormalizedVector:
    source_collection, source_crs = parse_vector(payload, filename)
    internal, max_error, geometry_types = _transform_feature_collection(
        source_collection,
        source_crs=source_crs,
        target_crs=working_crs,
    )
    qa, _, _ = _transform_feature_collection(
        internal,
        source_crs=working_crs,
        target_crs="EPSG:4326",
    )
    internal["floodguard_crs"] = working_crs
    return NormalizedVector(
        internal_feature_collection=internal,
        qa_feature_collection=qa,
        source_crs=source_crs,
        working_crs=working_crs,
        feature_count=len(cast(list[object], internal["features"])),
        geometry_types=geometry_types,
        bounds_working=_bounds(internal),
        bounds_wgs84=_bounds(qa),
        max_roundtrip_error_m=max_error,
    )
