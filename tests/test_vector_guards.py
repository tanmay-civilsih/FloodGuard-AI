"""Reject malformed/unsupported source geometry without automatic repairs."""

import json
import math

import pytest

from floodguard.spatial.vector import VectorNormalizationError, normalize_vector


def normalize(geometry: object) -> object:
    return normalize_vector(json.dumps({
        "type": "Feature", "id": "source-feature", "geometry": geometry, "properties": {},
    }).encode(), "input.geojson", working_crs="EPSG:32645")


@pytest.mark.parametrize("xy", [
    [88.0, 100.0], [181.0, 22.0], [math.nan, 22.0], [88.0, math.inf],
    [True, 22.0], [88.0, 22.0, math.nan], [88.0], [88.0, 22.0, 1.0, 2.0],
])
def test_invalid_coordinates_cannot_report_zero_error(xy: list[float]) -> None:
    with pytest.raises(VectorNormalizationError):
        normalize({"type": "Point", "coordinates": xy})


@pytest.mark.parametrize("geometry", [
    {"type": "Unknown", "coordinates": [88.0, 22.0]},
    {"type": "Polygon", "coordinates": [[[88, 22], [88.1, 22.1]]]},
    {"type": "Polygon", "coordinates": [[[88, 22], [88.1, 22], [88, 22.1], [88.1, 22.1]]]},
    {"type": "Polygon", "coordinates": [[[88, 22], [88.1, 22.1], [88.1, 22],
                                           [88, 22.1], [88, 22]]]},
    {"type": "Polygon", "coordinates": []},
    {"type": "LineString", "coordinates": [[88, 22], [88, 22]]},
    {"type": "MultiPoint", "coordinates": []},
    {"type": "GeometryCollection", "geometries": []},
    None,
])
def test_invalid_structure_or_topology_is_rejected(geometry: object) -> None:
    with pytest.raises(VectorNormalizationError):
        normalize(geometry)


def test_polygon_hole_outside_shell_is_rejected() -> None:
    with pytest.raises(VectorNormalizationError, match="topology"):
        normalize({"type": "Polygon", "coordinates": [
            [[88, 22], [88.1, 22], [88.1, 22.1], [88, 22.1], [88, 22]],
            [[88.2, 22.2], [88.3, 22.2], [88.3, 22.3], [88.2, 22.3], [88.2, 22.2]],
        ]})


def test_valid_polygon_and_source_id_survive() -> None:
    result = normalize_vector(json.dumps({
        "type": "Feature", "id": "ward-7", "properties": {"name": "pilot"},
        "geometry": {"type": "Polygon", "coordinates": [
            [[88.35, 22.55], [88.36, 22.55], [88.36, 22.56],
             [88.35, 22.56], [88.35, 22.55]],
        ]},
    }).encode(), "ward.geojson", working_crs="EPSG:32645")
    assert result.max_roundtrip_error_m < 1e-5
    assert all(math.isfinite(value) for value in result.bounds_working)
    features = result.qa_feature_collection["features"]
    assert isinstance(features, list)
    assert features[0]["id"] == "ward-7"
    assert features[0]["properties"] == {"name": "pilot"}


def test_valid_geometry_collection_survives() -> None:
    normalize({"type": "GeometryCollection", "geometries": [
        {"type": "Point", "coordinates": [88.35, 22.55]},
        {"type": "LineString", "coordinates": [[88.35, 22.55], [88.36, 22.56]]},
    ]})


@pytest.mark.parametrize("payload", [
    b'{"type":"Feature","type":"FeatureCollection","features":[]}',
    b'{"type":"FeatureCollection","features":[42]}',
    b'{"type":"Feature","properties":{"overflow":1e999},"geometry":null}',
])
def test_ambiguous_or_nonfinite_json_is_rejected(payload: bytes) -> None:
    with pytest.raises(VectorNormalizationError):
        normalize_vector(payload, "bad.geojson", working_crs="EPSG:32645")


def test_kml_nonfinite_position_is_rejected() -> None:
    with pytest.raises(VectorNormalizationError):
        normalize_vector(
            b'<kml><Placemark><Point><coordinates>88,nan</coordinates></Point></Placemark></kml>',
            "bad.kml", working_crs="EPSG:32645",
        )


def test_invalid_crs_has_domain_error() -> None:
    with pytest.raises(VectorNormalizationError):
        normalize_vector(b'{"type":"FeatureCollection","features":[]}',
                         "bad.geojson", working_crs="EPSG:0")
