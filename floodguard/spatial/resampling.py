"""Variable-specific resampling policies required by Sequence 4."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from floodguard.spatial.contracts import RainfallConservationResult

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class RainfallRemap:
    rain_rate_mm_h: FloatArray
    conservation: RainfallConservationResult


@dataclass(frozen=True, slots=True)
class ElevationRemap:
    elevation_m: FloatArray
    source_uncertainty_m: float | None


def _as_increasing_edges(
    values: NDArray[np.float64] | list[float],
    *,
    name: str,
) -> FloatArray:
    edges = np.asarray(values, dtype=np.float64)
    if edges.ndim != 1 or edges.size < 2:
        raise ValueError(f"{name} must be a one-dimensional edge array")
    if not np.all(np.isfinite(edges)) or not np.all(np.isfinite(np.diff(edges))):
        raise ValueError(f"{name} and cell widths must be finite")
    if not np.all(np.diff(edges) > 0):
        raise ValueError(f"{name} must be strictly increasing")
    return edges


def _as_increasing_centers(
    values: NDArray[np.float64] | list[float],
    *,
    name: str,
) -> FloatArray:
    centers = np.asarray(values, dtype=np.float64)
    if centers.ndim != 1 or centers.size < 1:
        raise ValueError(f"{name} must be a one-dimensional center array")
    if not np.all(np.isfinite(centers)):
        raise ValueError(f"{name} must be finite")
    if centers.size > 1 and not np.all(np.diff(centers) > 0):
        raise ValueError(f"{name} must be strictly increasing")
    return centers


def _require_supported_centers(source: FloatArray, target: FloatArray, *, name: str) -> None:
    # These contracts contain centres, not footprint edges; do not infer edge support.
    if target[0] < source[0] or target[-1] > source[-1]:
        raise ValueError(f"{name} lies outside the source centre domain; extrapolation is disabled")


def _cell_areas(x_edges: FloatArray, y_edges: FloatArray) -> FloatArray:
    with np.errstate(over="ignore", invalid="ignore"):
        areas = np.diff(y_edges)[:, np.newaxis] * np.diff(x_edges)[np.newaxis, :]
    if not np.all(np.isfinite(areas)) or np.any(areas <= 0):
        raise ValueError("cell areas must be finite and positive")
    return areas


def nearest_resample_categorical(
    values: NDArray[np.generic],
    source_x: NDArray[np.float64] | list[float],
    source_y: NDArray[np.float64] | list[float],
    destination_x: NDArray[np.float64] | list[float],
    destination_y: NDArray[np.float64] | list[float],
) -> NDArray[np.generic]:
    """Nearest-neighbour remapping for categorical cell-center data."""
    data = np.asarray(values)
    sx = _as_increasing_centers(source_x, name="source_x")
    sy = _as_increasing_centers(source_y, name="source_y")
    dx = _as_increasing_centers(destination_x, name="destination_x")
    dy = _as_increasing_centers(destination_y, name="destination_y")
    if data.shape != (sy.size, sx.size):
        raise ValueError("categorical array shape must equal (len(source_y), len(source_x))")
    _require_supported_centers(sx, dx, name="destination_x")
    _require_supported_centers(sy, dy, name="destination_y")
    x_indices = np.abs(sx[np.newaxis, :] - dx[:, np.newaxis]).argmin(axis=1)
    y_indices = np.abs(sy[np.newaxis, :] - dy[:, np.newaxis]).argmin(axis=1)
    return data[np.ix_(y_indices, x_indices)]


def bilinear_resample_elevation(
    elevation_m: NDArray[np.float64] | list[list[float]],
    source_x: NDArray[np.float64] | list[float],
    source_y: NDArray[np.float64] | list[float],
    destination_x: NDArray[np.float64] | list[float],
    destination_y: NDArray[np.float64] | list[float],
    *,
    source_uncertainty_m: float | None,
) -> ElevationRemap:
    """Interpolate finite in-domain centres; reject nodata and all extrapolation.

    Source uncertainty is retained, not interpreted as validated interpolation error.
    Masked/nodata rasters require an explicit adapter before using this utility.
    """
    data = np.asarray(elevation_m, dtype=np.float64)
    sx = _as_increasing_centers(source_x, name="source_x")
    sy = _as_increasing_centers(source_y, name="source_y")
    dx = _as_increasing_centers(destination_x, name="destination_x")
    dy = _as_increasing_centers(destination_y, name="destination_y")
    if data.shape != (sy.size, sx.size):
        raise ValueError("elevation array shape must equal (len(source_y), len(source_x))")
    if not np.all(np.isfinite(data)):
        raise ValueError("elevation values must be finite; nodata requires an explicit adapter")
    if source_uncertainty_m is not None and (
        not math.isfinite(source_uncertainty_m) or source_uncertainty_m < 0
    ):
        raise ValueError("source_uncertainty_m must be finite and non-negative")
    _require_supported_centers(sx, dx, name="destination_x")
    _require_supported_centers(sy, dy, name="destination_y")

    x_interpolated = np.vstack([np.interp(dx, sx, row) for row in data])
    output = np.vstack(
        [np.interp(dy, sy, x_interpolated[:, column]) for column in range(dx.size)]
    ).T
    if not np.all(np.isfinite(output)):
        raise ValueError("elevation interpolation produced non-finite values")
    return ElevationRemap(output.astype(np.float64), source_uncertainty_m)


def rainfall_volume_m3(
    rain_rate_mm_h: NDArray[np.float64] | list[list[float]] | list[list[list[float]]],
    x_edges_m: NDArray[np.float64] | list[float],
    y_edges_m: NDArray[np.float64] | list[float],
    *,
    timestep_seconds: float,
) -> float:
    """Area-integrated rainfall volume for one or more equal-duration timesteps."""
    if not math.isfinite(timestep_seconds) or timestep_seconds <= 0:
        raise ValueError("timestep_seconds must be finite and positive")
    x_edges = _as_increasing_edges(x_edges_m, name="x_edges_m")
    y_edges = _as_increasing_edges(y_edges_m, name="y_edges_m")
    rates = np.asarray(rain_rate_mm_h, dtype=np.float64)
    if rates.ndim == 2:
        rates = rates[np.newaxis, :, :]
    if rates.ndim != 3 or rates.shape[1:] != (y_edges.size - 1, x_edges.size - 1):
        raise ValueError("rainfall shape must be (time, y_cells, x_cells) or (y_cells, x_cells)")
    if rates.shape[0] == 0:
        raise ValueError("rainfall requires at least one timestep")
    if np.any(rates < 0) or not np.all(np.isfinite(rates)):
        raise ValueError("rainfall rates must be finite and non-negative")
    cell_area = _cell_areas(x_edges, y_edges)
    with np.errstate(over="ignore", invalid="ignore"):
        volume_per_timestep = (rates / (1000.0 * 3600.0)) * cell_area * timestep_seconds
        volume = float(np.sum(volume_per_timestep, dtype=np.float64))
    if not math.isfinite(volume):
        raise ValueError("rainfall volume exceeds the finite numerical range")
    return volume


def _overlap_matrix(destination_edges: FloatArray, source_edges: FloatArray) -> FloatArray:
    overlap = np.zeros(
        (destination_edges.size - 1, source_edges.size - 1),
        dtype=np.float64,
    )
    for destination_index in range(destination_edges.size - 1):
        destination_low = destination_edges[destination_index]
        destination_high = destination_edges[destination_index + 1]
        for source_index in range(source_edges.size - 1):
            source_low = source_edges[source_index]
            source_high = source_edges[source_index + 1]
            overlap[destination_index, source_index] = max(
                0.0,
                min(destination_high, source_high) - max(destination_low, source_low),
            )
    return overlap


def conservative_remap_rainfall(
    rain_rate_mm_h: NDArray[np.float64] | list[list[float]] | list[list[list[float]]],
    source_x_edges_m: NDArray[np.float64] | list[float],
    source_y_edges_m: NDArray[np.float64] | list[float],
    destination_x_edges_m: NDArray[np.float64] | list[float],
    destination_y_edges_m: NDArray[np.float64] | list[float],
    *,
    timestep_seconds: float,
    tolerance: float,
) -> RainfallRemap:
    """Conservative remapping on exactly matching, finite metric footprints.

    Boundary edges must be canonical and identical. No coordinate-relative tolerance,
    implicit grid snapping or zero rainfall outside source coverage is permitted.
    ``tolerance`` is dimensionless and applies only to the volume diagnostic.
    """
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and non-negative")
    if not math.isfinite(timestep_seconds) or timestep_seconds <= 0:
        raise ValueError("timestep_seconds must be finite and positive")
    sx = _as_increasing_edges(source_x_edges_m, name="source_x_edges_m")
    sy = _as_increasing_edges(source_y_edges_m, name="source_y_edges_m")
    dx = _as_increasing_edges(destination_x_edges_m, name="destination_x_edges_m")
    dy = _as_increasing_edges(destination_y_edges_m, name="destination_y_edges_m")
    source_extent = [sx[0], sx[-1], sy[0], sy[-1]]
    destination_extent = [dx[0], dx[-1], dy[0], dy[-1]]
    if not np.array_equal(source_extent, destination_extent):
        raise ValueError("source and destination rainfall grids must cover the same domain")

    rates = np.asarray(rain_rate_mm_h, dtype=np.float64)
    was_2d = rates.ndim == 2
    if was_2d:
        rates = rates[np.newaxis, :, :]
    if rates.ndim != 3 or rates.shape[1:] != (sy.size - 1, sx.size - 1):
        raise ValueError("rainfall shape must match the source grid")
    if rates.shape[0] == 0:
        raise ValueError("rainfall requires at least one timestep")
    if np.any(rates < 0) or not np.all(np.isfinite(rates)):
        raise ValueError("rainfall rates must be finite and non-negative")

    x_overlap = _overlap_matrix(dx, sx)
    y_overlap = _overlap_matrix(dy, sy)
    destination_area = _cell_areas(dx, dy)
    output = np.zeros(
        (rates.shape[0], dy.size - 1, dx.size - 1),
        dtype=np.float64,
    )
    for time_index in range(rates.shape[0]):
        weighted = y_overlap @ rates[time_index] @ x_overlap.T
        output[time_index] = weighted / destination_area

    before = rainfall_volume_m3(rates, sx, sy, timestep_seconds=timestep_seconds)
    after = rainfall_volume_m3(output, dx, dy, timestep_seconds=timestep_seconds)
    numerical_epsilon = float(np.finfo(np.float64).eps)
    denominator = max(abs(before), numerical_epsilon)
    relative_error = abs(before - after) / denominator
    conservation = RainfallConservationResult(
        volume_before_m3=before,
        volume_after_m3=after,
        relative_error=relative_error,
        tolerance=tolerance,
        passed=relative_error <= tolerance,
    )
    returned = output[0] if was_2d else output
    return RainfallRemap(returned, conservation)


def reference_rainfall_conservation_check(*, tolerance: float) -> RainfallConservationResult:
    """Deterministic non-uniform grid check used by readiness and local verification."""
    source = np.array(
        [
            [[12.0, 35.0], [4.0, 20.0]],
            [[5.0, 0.0], [22.0, 11.0]],
        ],
        dtype=np.float64,
    )
    remap = conservative_remap_rainfall(
        source,
        [0.0, 100.0, 250.0],
        [0.0, 80.0, 200.0],
        [0.0, 40.0, 100.0, 160.0, 250.0],
        [0.0, 50.0, 80.0, 140.0, 200.0],
        timestep_seconds=300.0,
        tolerance=tolerance,
    )
    return remap.conservation
