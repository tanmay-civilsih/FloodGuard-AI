import json

import pytest
from pydantic import ValidationError

from floodguard.terrain.contracts import TerrainPackage
from floodguard.terrain.grid import decode_package, package_bytes
from tests.terrain_fixtures import synthetic_package


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize(
    "field", ["native_horizontal_resolution_m", "max_conditioning_adjustment_m"]
)
def test_nonfinite_package_numbers_are_rejected(field: str, value: float) -> None:
    data = synthetic_package().model_dump()
    data[field] = value
    with pytest.raises(ValidationError):
        TerrainPackage.model_validate(data)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["grid"].update(origin_x_m=float("nan")),
        lambda p: p["grid"].update(cell_size_m=float("inf")),
        lambda p: p["grid"].update(elevations_m=[[None] * 5 for _ in range(4)]),
        lambda p: p["grid"].update(origin_x_m=1e308, cell_size_m=1e308),
        lambda p: p["multi_level_structures"][0].update(lower_elevation_m=float("nan")),
        lambda p: p["multi_level_structures"][0].update(bounds_working=[0, 0, 1, 1]),
        lambda p: p["multi_level_structures"].append(p["multi_level_structures"][0]),
        lambda p: p.update(multi_level_assessment="CONFIRMED_NONE"),
        lambda p: p.update(depression_assessment="CONFIRMED_NONE"),
        lambda p: p.update(interventions=[]),
        lambda p: p.update(vertical_quality="UNKNOWN", vertical_unit="ft"),
        lambda p: p.update(effective_information_resolution_m=5),
        lambda p: p.update(limitations=["  "]),
        lambda p: p["vertical_validation"].update(rmse_limit_m=float("inf")),
        lambda p: p["vertical_validation"].update(typo="silently ignored before"),
        lambda p: p["interventions"][0].update(source_reference="  "),
    ],
)
def test_invalid_or_contradictory_evidence_is_rejected(mutate) -> None:
    data = synthetic_package().model_dump()
    mutate(data)
    with pytest.raises(ValidationError):
        TerrainPackage.model_validate(data)


def test_effective_resolution_cannot_overstate_a_coarser_computational_grid() -> None:
    data = synthetic_package().model_dump()
    data["grid"]["cell_size_m"] = 60
    data["computational_resolution_m"] = 60
    with pytest.raises(ValidationError, match="finer source or grid"):
        TerrainPackage.model_validate(data)


@pytest.mark.parametrize("payload", [b'{"a":1,"a":2}', b'{"grid":{"a":1,"a":2}}'])
def test_duplicate_json_keys_are_rejected(payload: bytes) -> None:
    with pytest.raises(ValueError, match="duplicate terrain JSON key"):
        decode_package(payload)


def test_package_round_trip_and_invalid_encoding() -> None:
    package = synthetic_package()
    assert decode_package(package_bytes(package)) == package
    with pytest.raises(ValueError, match="UTF-8"):
        decode_package(b"\xff")
    data = json.loads(package_bytes(package))
    data["grid"]["origin_y_m"] = float("nan")
    with pytest.raises(ValueError):
        decode_package(json.dumps(data).encode())
