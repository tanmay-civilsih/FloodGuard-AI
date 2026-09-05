import math

import pytest
from pyproj import Transformer

from floodguard.terrain.conditioning import condition_package
from floodguard.terrain.contracts import TerrainPackage
from floodguard.terrain.grid import qa_geojson
from tests.terrain_fixtures import synthetic_package


def _qa(package: TerrainPackage, cap: int = 2500):
    surfaces = condition_package(package)
    return qa_geojson(
        package=package,
        visual=surfaces.visual,
        hydraulic=surfaces.hydraulic,
        terrain_id="test",
        max_cells=cap,
    )


@pytest.mark.parametrize(("width", "height"), [(3001, 1), (1, 3001), (51, 49)])
@pytest.mark.parametrize("cap", [1, 99, 2500])
def test_qa_strictly_caps_actual_cell_footprints(width: int, height: int, cap: int) -> None:
    data = synthetic_package().model_dump()
    data["grid"].update(
        width=width, height=height, elevations_m=[[100.0] * width for _ in range(height)]
    )
    data.update(
        interventions=[],
        multi_level_structures=[],
        depression_assessment="CONFIRMED_NONE",
        multi_level_assessment="CONFIRMED_NONE",
    )
    package = TerrainPackage.model_validate(data)
    result = _qa(package, cap)
    assert len(result["features"]) == min(width * height, cap)
    assert result["sampling"]["omitted_cells"] == width * height - len(result["features"])
    inverse = Transformer.from_crs("EPSG:4326", package.grid.crs, always_xy=True)
    for feature in result["features"]:
        row, column = feature["properties"]["row"], feature["properties"]["column"]
        ring = feature["geometry"]["coordinates"][0]
        points = [inverse.transform(*point) for point in ring]
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        assert min(xs) == pytest.approx(300000 + column * 10, rel=0, abs=1e-6)
        assert min(ys) == pytest.approx(2500000 + row * 10, rel=0, abs=1e-6)
        assert max(xs) - min(xs) == pytest.approx(10, rel=0, abs=1e-6)
        assert max(ys) - min(ys) == pytest.approx(10, rel=0, abs=1e-6)
        assert max(xs) <= package.grid.bounds[2] + 1e-6
        assert max(ys) <= package.grid.bounds[3] + 1e-6
        assert ring[0] == ring[-1]


def test_qa_keeps_interventions_and_reports_omissions() -> None:
    package = synthetic_package()
    full = _qa(package, 4)
    cells = [f for f in full["features"] if f["properties"]["feature_kind"] == "TERRAIN_CELL"]
    locations = {(f["properties"]["row"], f["properties"]["column"]) for f in cells}
    assert {(0, 0), (1, 1), (2, 2)} <= locations
    assert len(cells) == 4
    assert full["sampling"]["omitted_intervention_cells"] == 0
    tiny = _qa(package, 1)
    assert tiny["sampling"]["displayed_cells"] == 1
    assert tiny["sampling"]["omitted_intervention_cells"] == 2
    assert _qa(package, 4) == full


def test_nodata_holes_are_not_painted_or_counted_as_valid() -> None:
    data = synthetic_package().model_dump()
    data["grid"]["elevations_m"][3] = [None] * 5
    result = _qa(TerrainPackage.model_validate(data))
    assert result["sampling"]["valid_cells"] == 15
    assert result["sampling"]["total_cells"] == 20
    assert not result["sampling"]["sampled"]
    assert all(f["properties"].get("row") != 3 for f in result["features"])
    assert all(math.isfinite(value) for value in result["bbox"])


def test_structure_corners_and_provenance_are_not_replaced_by_a_bounding_box() -> None:
    package = synthetic_package()
    result = _qa(package)
    feature = next(
        f for f in result["features"] if f["properties"]["feature_kind"] == "MULTI_LEVEL_STRUCTURE"
    )
    assert feature["properties"]["source_reference"] == "survey://underpass-01"
    inverse = Transformer.from_crs("EPSG:4326", package.grid.crs, always_xy=True)
    ring = [inverse.transform(*point) for point in feature["geometry"]["coordinates"][0]]
    for actual, expected in zip(
        ring,
        [
            (300000, 2500000),
            (300040, 2500000),
            (300040, 2500020),
            (300000, 2500020),
            (300000, 2500000),
        ],
        strict=True,
    ):
        assert actual == pytest.approx(expected, rel=0, abs=1e-6)


def test_qa_rejects_nonfinite_projection_output(monkeypatch) -> None:
    class InvalidProjection:
        def transform(self, x, y, *, errcheck):
            assert errcheck is True
            return float("inf"), 22

    monkeypatch.setattr(
        "floodguard.terrain.grid.Transformer.from_crs", lambda *args, **kwargs: InvalidProjection()
    )
    with pytest.raises(ValueError, match="invalid WGS84 coordinates"):
        _qa(synthetic_package())


def test_qa_rejects_invalid_limit_and_mismatched_grids() -> None:
    package = synthetic_package()
    with pytest.raises(ValueError, match="positive"):
        _qa(package, 0)
    with pytest.raises(ValueError, match="share source grid"):
        qa_geojson(
            package=package,
            visual=package.grid,
            hydraulic=package.grid.model_copy(update={"origin_x_m": 0}),
            terrain_id="bad",
        )
