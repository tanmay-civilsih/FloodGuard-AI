"""Recompute cell-centre control residuals without certifying survey provenance."""

from __future__ import annotations

import math

from pydantic import BaseModel

from floodguard.terrain.contracts import TerrainGrid, TerrainPackage, ValidationCheckStatus

VALIDATION_ALGORITHM = "hydraulic-cell-centre-residuals-v1"
# Serialization/round-off consistency only, not an engineering acceptance tolerance.
SUMMARY_CONSISTENCY_TOLERANCE_M = 1e-6


class ControlResidual(BaseModel):
    control_id: str
    row: int
    column: int
    x_m: float
    y_m: float
    reference_elevation_m: float
    raw_elevation_m: float
    hydraulic_elevation_m: float
    residual_m: float


class VerticalEvaluation(BaseModel):
    algorithm_version: str = VALIDATION_ALGORITHM
    status: ValidationCheckStatus
    rmse_m: float | None
    mean_bias_m: float | None
    max_absolute_error_m: float | None
    control_point_count: int
    residuals: list[ControlResidual]
    limitations: list[str]


def evaluate_vertical_controls(
    package: TerrainPackage, hydraulic: TerrainGrid
) -> VerticalEvaluation:
    """Compute hydraulic minus observation residuals; never interpolate or fill nodata.

    Controls must be located at the declared cells' centres in the package CRS and datum.
    The raw package records their survey method, provenance and observation times. These
    calculations cannot prove survey authenticity, independence or adequate spatial coverage.
    """
    if hydraulic.model_dump(exclude={"elevations_m"}) != package.grid.model_dump(
        exclude={"elevations_m"}
    ):
        raise ValueError("validation grid metadata must match the source grid")
    validation = package.vertical_validation
    residuals: list[ControlResidual] = []
    for control in validation.control_points:
        if (
            package.vertical_datum != control.vertical_datum
            or package.vertical_unit is None
            or package.datum_transform_status.value != "COMPATIBLE"
        ):
            raise ValueError(
                "control observations require the same compatible vertical datum and metres"
            )
        row, column = control.row, control.column
        if row >= hydraulic.height or column >= hydraulic.width:
            raise ValueError("control observation lies outside the terrain grid")
        raw = package.grid.elevations_m[row][column]
        predicted = hydraulic.elevations_m[row][column]
        if raw is None or predicted is None:
            raise ValueError("control observations cannot target nodata")
        error = predicted - control.reference_elevation_m
        if not math.isfinite(error):
            raise ValueError("control residual must be finite")
        residuals.append(
            ControlResidual(
                control_id=control.control_id,
                row=row,
                column=column,
                x_m=hydraulic.origin_x_m + (column + 0.5) * hydraulic.cell_size_m,
                y_m=hydraulic.origin_y_m + (row + 0.5) * hydraulic.cell_size_m,
                reference_elevation_m=control.reference_elevation_m,
                raw_elevation_m=raw,
                hydraulic_elevation_m=predicted,
                residual_m=error,
            )
        )
    limitations = [
        *validation.limitations,
        "Computed residuals do not verify survey authenticity, independent holdout selection, "
        "spatial representativeness or road-sag/underpass/drain-rim evidence. "
        "Engineering acceptance remains pending; hydraulic validation is not granted.",
    ]
    if not residuals:
        return VerticalEvaluation(
            status=ValidationCheckStatus.NOT_ASSESSED,
            rmse_m=None,
            mean_bias_m=None,
            max_absolute_error_m=None,
            control_point_count=0,
            residuals=[],
            limitations=[
                *limitations,
                "No control observations supplied; reported summaries are unverified.",
            ],
        )
    maximum = max(abs(item.residual_m) for item in residuals)
    count = len(residuals)
    rmse = (
        maximum
        * math.sqrt(math.fsum((item.residual_m / maximum) ** 2 for item in residuals) / count)
        if maximum
        else 0.0
    )
    bias = math.fsum(item.residual_m / count for item in residuals)
    if validation.rmse_m is not None and not math.isclose(
        validation.rmse_m, rmse, rel_tol=0, abs_tol=SUMMARY_CONSISTENCY_TOLERANCE_M
    ):
        raise ValueError("reported RMSE does not match computed hydraulic control residuals")
    return VerticalEvaluation(
        status=(
            ValidationCheckStatus.PASSED
            if rmse <= validation.rmse_limit_m
            else ValidationCheckStatus.FAILED
        ),
        rmse_m=rmse,
        mean_bias_m=bias,
        max_absolute_error_m=maximum,
        control_point_count=count,
        residuals=residuals,
        limitations=limitations,
    )
