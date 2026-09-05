import json
import math
from datetime import UTC

import pytest
from pydantic import ValidationError

from floodguard.terrain.conditioning import condition_package
from floodguard.terrain.contracts import TerrainPackage, TerrainReadinessStatus
from floodguard.terrain.grid import package_bytes
from floodguard.terrain.service import TerrainConditioningError
from floodguard.terrain.validation import evaluate_vertical_controls
from tests.terrain_fixtures import source_and_version, synthetic_package
from tests.test_terrain_service import _service


def observed_package() -> TerrainPackage:
    data = synthetic_package().model_dump()
    data["vertical_validation"].update(
        method="Synthetic independent cell-centre level survey (test only)",
        control_points=[
            {
                "control_id": name,
                "row": row,
                "column": column,
                "reference_elevation_m": elevation,
                "vertical_datum": "EGM2008",
                "source_reference": f"survey://synthetic-control/{name}",
                "measured_at": "2026-01-02T12:00:00+05:30",
            }
            for name, row, column, elevation in [("A", 0, 0, 98), ("B", 1, 1, 98), ("C", 2, 2, 92)]
        ],
    )
    return TerrainPackage.model_validate(data)


def test_analytic_residual_benchmark_uses_conditioned_not_raw_surface() -> None:
    package = observed_package()
    evaluation = evaluate_vertical_controls(package, condition_package(package).hydraulic)
    assert [item.residual_m for item in evaluation.residuals] == [3, 1, -2]
    assert [item.raw_elevation_m for item in evaluation.residuals] == [100, 101, 90]
    assert evaluation.rmse_m == pytest.approx(math.sqrt(14 / 3))
    assert evaluation.mean_bias_m == pytest.approx(2 / 3)
    assert evaluation.max_absolute_error_m == 3
    assert evaluation.control_point_count == 3
    assert evaluation.status.value == "PASSED"
    assert evaluation.residuals[0].x_m == 300_005
    assert evaluation.residuals[0].y_m == 2_500_005
    assert package.vertical_validation.control_points[0].measured_at.tzinfo is UTC


def test_no_observations_never_fabricates_zero_error() -> None:
    package = synthetic_package()
    result = evaluate_vertical_controls(package, condition_package(package).hydraulic)
    assert result.rmse_m is None
    assert result.control_point_count == 0
    assert result.status.value == "NOT_ASSESSED"
    assert result.residuals == []


def test_exact_controls_report_zero_error_without_division_by_zero() -> None:
    data = observed_package().model_dump()
    for point, elevation in zip(
        data["vertical_validation"]["control_points"], [101, 99, 90], strict=True
    ):
        point["reference_elevation_m"] = elevation
    data["vertical_validation"].update(rmse_m=0, control_point_count=3)
    package = TerrainPackage.model_validate(data)
    result = evaluate_vertical_controls(package, condition_package(package).hydraulic)
    assert result.rmse_m == result.mean_bias_m == result.max_absolute_error_m == 0


def test_large_finite_errors_do_not_overflow_rmse_squaring() -> None:
    data = observed_package().model_dump()
    for point in data["vertical_validation"]["control_points"]:
        point["reference_elevation_m"] = -1e200
    package = TerrainPackage.model_validate(data)
    result = evaluate_vertical_controls(package, condition_package(package).hydraulic)
    assert result.rmse_m == pytest.approx(1e200)
    assert result.status.value == "FAILED"


def test_unverified_summary_is_retained_only_as_reported_evidence() -> None:
    data = synthetic_package().model_dump()
    data["vertical_validation"].update(method="claimed survey", rmse_m=0, control_point_count=100)
    source, version, raw_object, payload = source_and_version(
        package_bytes(TerrainPackage.model_validate(data))
    )
    service, session = _service(raw_object.object_key, payload)
    try:
        built = service.build_from_raw(source, version, raw_object)
        record = service.get(built.terrain_id)
        assert record.vertical_rmse_m is None
        assert record.control_point_count == 0
        audit = json.loads(service.read_artifact(built.terrain_id, "AUDIT"))
        assert audit["vertical_validation"]["reported_summary"]["control_point_count"] == 100
    finally:
        session.close()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["vertical_validation"].update(control_point_count=100),
        lambda p: p["vertical_validation"].update(method=None),
        lambda p: p["vertical_validation"]["control_points"][0].update(measured_at="2026-01-01"),
        lambda p: p["vertical_validation"]["control_points"][0].update(source_reference="  "),
        lambda p: p["vertical_validation"]["control_points"][0].update(
            reference_elevation_m=float("inf")
        ),
        lambda p: p["vertical_validation"]["control_points"][1].update(control_id="A"),
        lambda p: p["vertical_validation"]["control_points"][1].update(row=0, column=0),
    ],
)
def test_invalid_control_observation_contracts(mutate) -> None:
    data = observed_package().model_dump()
    mutate(data)
    with pytest.raises(ValidationError):
        TerrainPackage.model_validate(data)


@pytest.mark.parametrize(
    ("updates", "match"),
    [
        ({"vertical_datum": "other"}, "same compatible vertical datum"),
        ({"row": 4}, "outside"),
        ({"column": 5}, "outside"),
    ],
)
def test_control_reference_and_domain_must_match(updates, match: str) -> None:
    data = observed_package().model_dump()
    data["vertical_validation"]["control_points"][0].update(updates)
    package = TerrainPackage.model_validate(data)
    with pytest.raises(ValueError, match=match):
        evaluate_vertical_controls(package, condition_package(package).hydraulic)


def test_nodata_is_not_interpolated_for_validation() -> None:
    data = observed_package().model_dump()
    data["vertical_validation"]["control_points"][0].update(row=3, column=4)
    data["grid"]["elevations_m"][3][4] = None
    package = TerrainPackage.model_validate(data)
    with pytest.raises(ValueError, match="nodata"):
        evaluate_vertical_controls(package, condition_package(package).hydraulic)


def test_claimed_rmse_must_match_observations() -> None:
    data = observed_package().model_dump()
    data["vertical_validation"]["rmse_m"] = 0.01
    package = TerrainPackage.model_validate(data)
    with pytest.raises(ValueError, match="reported RMSE"):
        evaluate_vertical_controls(package, condition_package(package).hydraulic)


@pytest.mark.parametrize("limit", [1, 5])
def test_build_persists_computed_evidence_without_certifying_hydraulics(limit: float) -> None:
    data = observed_package().model_dump()
    data["vertical_validation"]["rmse_limit_m"] = limit
    package = TerrainPackage.model_validate(data)
    source, version, raw_object, payload = source_and_version(package_bytes(package))
    service, session = _service(raw_object.object_key, payload)
    try:
        built = service.build_from_raw(source, version, raw_object)
        expected = (
            TerrainReadinessStatus.VISUAL_READY
            if limit == 1
            else TerrainReadinessStatus.HYDRAULIC_SCENARIO_READY
        )
        assert built.readiness_status is expected
        record = service.get(built.terrain_id)
        assert record.control_point_count == 3
        assert record.vertical_rmse_m == pytest.approx(math.sqrt(14 / 3))
        audit = json.loads(service.read_artifact(built.terrain_id, "AUDIT"))
        evidence = audit["vertical_validation"]
        assert evidence["reported_summary"]["rmse_m"] is None
        assert len(evidence["control_observations"]) == 3
        assert evidence["computed_evaluation"]["residuals"][0]["residual_m"] == 3
        assert evidence["control_observations"][0]["measured_at"].endswith("Z")
        assert not service.build_from_raw(source, version, raw_object).created
    finally:
        session.close()


@pytest.mark.parametrize("product", ["RAW_ELEVATION", "VISUAL_TERRAIN", "AUDIT"])
def test_corrupt_artifacts_are_not_served(product: str) -> None:
    source, version, raw_object, payload = source_and_version()
    service, session = _service(raw_object.object_key, payload)
    try:
        built = service.build_from_raw(source, version, raw_object)
        record = service.get(built.terrain_id)
        if product == "RAW_ELEVATION":
            service.object_store.raw_objects[record.raw_elevation_object_key] = b"corrupt"
        else:
            key = (
                record.audit_object_key if product == "AUDIT" else record.visual_terrain_object_key
            )
            service.object_store.spatial_objects[key] = b"corrupt"
        with pytest.raises(TerrainConditioningError, match="integrity check"):
            service.read_artifact(built.terrain_id, product)
    finally:
        session.close()
