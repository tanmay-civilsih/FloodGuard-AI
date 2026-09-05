"""Affine georeferencing with explicit control-point residual diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, sqrt

import numpy as np
from pyproj import Transformer

from floodguard.reconstruction.contracts import (
    GeoreferenceControlResult,
    ReconstructionCalibration,
)


class GeoreferenceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AffineFit:
    coefficients: tuple[float, float, float, float, float, float]
    control_results: tuple[GeoreferenceControlResult, ...]
    rmse_m: float
    max_error_m: float

    def transform(self, x: float, y: float) -> tuple[float, float]:
        a, b, c, d, e, f = self.coefficients
        return a * x + b * y + c, d * x + e * y + f


def fit_affine(
    calibration: ReconstructionCalibration,
    *,
    working_crs: str,
) -> AffineFit:
    transformer = Transformer.from_crs(
        calibration.target_crs,
        working_crs,
        always_xy=True,
    )
    page_matrix = np.asarray(
        [[item.page_x, item.page_y, 1.0] for item in calibration.control_points],
        dtype=float,
    )
    if np.linalg.matrix_rank(page_matrix) < 3:
        raise GeoreferenceError("georeference control points are collinear")
    targets = np.asarray(
        [
            transformer.transform(item.target_x, item.target_y)
            for item in calibration.control_points
        ],
        dtype=float,
    )
    solution, _, _, _ = np.linalg.lstsq(page_matrix, targets, rcond=None)
    predicted = page_matrix @ solution
    residuals = np.sqrt(np.sum((predicted - targets) ** 2, axis=1))
    coefficients = (
        float(solution[0, 0]),
        float(solution[1, 0]),
        float(solution[2, 0]),
        float(solution[0, 1]),
        float(solution[1, 1]),
        float(solution[2, 1]),
    )
    results = tuple(
        GeoreferenceControlResult(
            name=item.name,
            page_x=item.page_x,
            page_y=item.page_y,
            target_easting_m=float(target[0]),
            target_northing_m=float(target[1]),
            residual_m=float(residual),
            match_description=item.match_description,
        )
        for item, target, residual in zip(
            calibration.control_points,
            targets,
            residuals,
            strict=True,
        )
    )
    rmse = sqrt(float(np.mean(residuals**2)))
    maximum = float(np.max(residuals))
    if not all(np.isfinite(value) for value in coefficients):
        raise GeoreferenceError("affine georeference produced non-finite coefficients")
    if hypot(coefficients[0], coefficients[3]) <= 0 or hypot(
        coefficients[1], coefficients[4]
    ) <= 0:
        raise GeoreferenceError("affine georeference has a zero spatial scale")
    return AffineFit(
        coefficients=coefficients,
        control_results=results,
        rmse_m=rmse,
        max_error_m=maximum,
    )
