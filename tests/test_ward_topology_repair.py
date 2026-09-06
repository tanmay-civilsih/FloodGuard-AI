"""A ward-specific repair may reinterpret self-crossing linework but never move it."""

import json

import pytest

from floodguard.spatial.geometry_validation import TOPOLOGY_REPAIR_PROPERTY
from floodguard.spatial.vector import VectorNormalizationError, normalize_vector

BOWTIE = {
    "type": "Polygon",
    "coordinates": [[
        [88.35, 22.55], [88.36, 22.56], [88.36, 22.55],
        [88.35, 22.56], [88.35, 22.55],
    ]],
}


def feature(geometry: object, properties: dict[str, object] | None = None) -> bytes:
    return json.dumps({
        "type": "Feature", "properties": properties or {}, "geometry": geometry,
    }).encode()


def test_default_normalization_still_rejects_self_intersection() -> None:
    with pytest.raises(VectorNormalizationError, match="intersection"):
        normalize_vector(feature(BOWTIE), "ward.geojson", working_crs="EPSG:32645")


def test_explicit_ward_policy_repairs_without_moving_source_linework() -> None:
    result = normalize_vector(
        feature(BOWTIE), "ward.geojson", working_crs="EPSG:32645",
        repair_self_intersections=True,
    )
    features = result.qa_feature_collection["features"]
    assert isinstance(features, list)
    properties = features[0]["properties"]
    repair = properties[TOPOLOGY_REPAIR_PROPERTY]
    assert repair["method"] == "GEOS_MAKE_VALID_LINEWORK_SELF_INTERSECTION_V1"
    assert repair["linework_preserved"] is True
    assert repair["boundary_hausdorff_source_units"] <= repair["acceptance_tolerance_source_units"]
    assert repair["envelope_delta_source_units"] <= repair["acceptance_tolerance_source_units"]
    assert result.max_roundtrip_error_m < 0.05


def test_non_self_intersection_topology_error_is_not_auto_repaired() -> None:
    outside_hole = {
        "type": "Polygon",
        "coordinates": [
            [[88.0, 22.0], [88.1, 22.0], [88.1, 22.1], [88.0, 22.1], [88.0, 22.0]],
            [[88.2, 22.2], [88.3, 22.2], [88.3, 22.3], [88.2, 22.3], [88.2, 22.2]],
        ],
    }
    with pytest.raises(VectorNormalizationError, match="topology"):
        normalize_vector(
            feature(outside_hole), "ward.geojson", working_crs="EPSG:32645",
            repair_self_intersections=True,
        )


def test_reserved_repair_property_cannot_be_spoofed() -> None:
    with pytest.raises(VectorNormalizationError, match="reserved"):
        normalize_vector(
            feature(BOWTIE, {TOPOLOGY_REPAIR_PROPERTY: {"fake": True}}),
            "ward.geojson", working_crs="EPSG:32645", repair_self_intersections=True,
        )


def test_kml_self_intersection_uses_same_auditable_policy() -> None:
    kml = b'''<kml><Placemark><name>Ward test</name><Polygon><outerBoundaryIs>
    <LinearRing><coordinates>
    88.35,22.55,0 88.36,22.56,0 88.36,22.55,0 88.35,22.56,0 88.35,22.55,0
    </coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></kml>'''
    result = normalize_vector(
        kml, "ward.kml", working_crs="EPSG:32645", repair_self_intersections=True,
    )
    features = result.internal_feature_collection["features"]
    assert isinstance(features, list)
    assert TOPOLOGY_REPAIR_PROPERTY in features[0]["properties"]
