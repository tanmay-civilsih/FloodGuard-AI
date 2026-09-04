import json

from floodguard.spatial.vector import normalize_vector

KML = b'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark>
<name>Pilot polygon</name><Polygon><outerBoundaryIs><LinearRing><coordinates>
88.3500,22.5500,0 88.3600,22.5500,0 88.3600,22.5600,0
88.3500,22.5600,0 88.3500,22.5500,0
</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>'''


def test_kml_is_reprojected_to_metric_kolkata_crs_and_back_for_qa() -> None:
    result = normalize_vector(KML, "ward.kml", working_crs="EPSG:32645")
    assert result.source_crs == "EPSG:4326"
    assert result.working_crs == "EPSG:32645"
    assert result.feature_count == 1
    assert result.geometry_types == ["Polygon"]
    assert result.bounds_working[0] > 600_000
    assert result.bounds_working[1] > 2_000_000
    assert result.max_roundtrip_error_m < 1e-5
    assert abs(result.bounds_wgs84[0] - 88.35) < 1e-9
    assert abs(result.bounds_wgs84[1] - 22.55) < 1e-9


def test_geojson_properties_are_preserved() -> None:
    payload = json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"ward": "98"},
                    "geometry": {"type": "Point", "coordinates": [88.35, 22.55]},
                }
            ],
        }
    ).encode()
    result = normalize_vector(payload, "wards.geojson", working_crs="EPSG:32645")
    features = result.qa_feature_collection["features"]
    assert isinstance(features, list)
    feature = features[0]
    assert isinstance(feature, dict)
    assert feature["properties"] == {"ward": "98"}
