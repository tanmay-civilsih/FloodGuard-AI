"""Regression coverage for finite, covered, conservative spatial remapping."""

import math

import numpy as np
import pytest

from floodguard.spatial.resampling import (
    bilinear_resample_elevation,
    conservative_remap_rainfall,
    nearest_resample_categorical,
    rainfall_volume_m3,
    reference_rainfall_conservation_check,
)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, 0.0, -1.0])
def test_invalid_rainfall_duration_is_rejected(value: float) -> None:
    with pytest.raises(ValueError, match="timestep_seconds"):
        rainfall_volume_m3([[1.0]], [0.0, 1.0], [0.0, 1.0], timestep_seconds=value)
    with pytest.raises(ValueError, match="timestep_seconds"):
        conservative_remap_rainfall(
            [[1.0]], [0.0, 1.0], [0.0, 1.0], [0.0, 1.0], [0.0, 1.0],
            timestep_seconds=value, tolerance=1e-12,
        )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, -1.0])
def test_invalid_conservation_tolerance_is_rejected(value: float) -> None:
    with pytest.raises(ValueError, match="tolerance"):
        reference_rainfall_conservation_check(tolerance=value)


@pytest.mark.parametrize("shift", [5.0, -5.0, 0.001])
def test_large_utm_coordinates_do_not_relax_domain_equality(shift: float) -> None:
    with pytest.raises(ValueError, match="same domain"):
        conservative_remap_rainfall(
            [[100.0]], [640000.0, 640100.0], [2500000.0, 2500100.0],
            [640000.0 - shift, 640100.0 + shift], [2500000.0, 2500100.0],
            timestep_seconds=3600.0, tolerance=1e-12,
        )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_grid_edges_are_rejected(value: float) -> None:
    with pytest.raises(ValueError):
        rainfall_volume_m3([[1.0]], [0.0, value], [0.0, 1.0], timestep_seconds=1.0)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_elevation_or_uncertainty_is_rejected(value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        bilinear_resample_elevation(
            [[value]], [0.0], [0.0], [0.0], [0.0], source_uncertainty_m=None,
        )
    with pytest.raises(ValueError, match="finite"):
        bilinear_resample_elevation(
            [[1.0]], [0.0], [0.0], [0.0], [0.0], source_uncertainty_m=value,
        )


def test_elevation_does_not_extend_edge_values() -> None:
    with pytest.raises(ValueError, match="extrapolation"):
        bilinear_resample_elevation(
            [[0.0, 10.0], [20.0, 30.0]], [0.0, 10.0], [0.0, 10.0],
            [1000.0], [1000.0], source_uncertainty_m=3.5,
        )


def test_categorical_coverage_is_explicit() -> None:
    with pytest.raises(ValueError, match="extrapolation"):
        nearest_resample_categorical(np.array([[1]]), [0.0], [0.0], [1.0], [0.0])


def test_nonfinite_single_center_is_rejected() -> None:
    with pytest.raises(ValueError, match="finite"):
        nearest_resample_categorical(np.array([[1]]), [math.nan], [0.0], [0.0], [0.0])


def test_linear_elevation_field_and_source_uncertainty_are_preserved() -> None:
    result = bilinear_resample_elevation(
        [[0.0, 10.0], [20.0, 30.0]], [0.0, 10.0], [0.0, 10.0],
        [0.0, 5.0, 10.0], [0.0, 5.0, 10.0], source_uncertainty_m=3.5,
    )
    np.testing.assert_allclose(result.elevation_m, [[0, 5, 10], [10, 15, 20], [20, 25, 30]])
    assert result.source_uncertainty_m == 3.5


@pytest.mark.parametrize("seed", range(10))
def test_nonuniform_multitime_rainfall_conserves_volume(seed: int) -> None:
    rng = np.random.default_rng(seed)
    rates = rng.uniform(0, 100, (3, 2, 2))
    remap = conservative_remap_rainfall(
        rates, [640000.0, 640040.0, 640100.0], [2500000.0, 2500030.0, 2500100.0],
        [640000.0, 640020.0, 640100.0], [2500000.0, 2500060.0, 2500100.0],
        timestep_seconds=300.0, tolerance=1e-12,
    )
    assert remap.conservation.passed
    assert np.all(np.isfinite(remap.rain_rate_mm_h))
    assert np.all(remap.rain_rate_mm_h >= 0)


def test_zero_rainfall_is_valid() -> None:
    result = conservative_remap_rainfall(
        [[0.0]], [0.0, 1.0], [0.0, 1.0], [0.0, 0.5, 1.0], [0.0, 1.0],
        timestep_seconds=1.0, tolerance=0.0,
    )
    assert result.conservation.passed
    assert result.conservation.volume_after_m3 == 0


def test_empty_time_axis_is_not_a_valid_dry_event() -> None:
    with pytest.raises(ValueError, match="timestep"):
        rainfall_volume_m3(np.zeros((0, 1, 1)), [0.0, 1.0], [0.0, 1.0], timestep_seconds=1)


def test_overflow_cannot_be_a_valid_volume() -> None:
    with pytest.raises(ValueError, match="finite"):
        rainfall_volume_m3([[1e308]], [0.0, 1e100], [0.0, 1e100], timestep_seconds=1e308)
