import numpy as np

from floodguard.spatial.resampling import (
    bilinear_resample_elevation,
    conservative_remap_rainfall,
    nearest_resample_categorical,
    rainfall_volume_m3,
    reference_rainfall_conservation_check,
)


def test_categorical_remap_uses_nearest_cell_center() -> None:
    source = np.array([[1, 2], [3, 4]])
    output = nearest_resample_categorical(
        source,
        [0.0, 10.0],
        [0.0, 10.0],
        [1.0, 9.0],
        [2.0, 8.0],
    )
    assert output.tolist() == [[1, 2], [3, 4]]


def test_elevation_remap_preserves_source_uncertainty() -> None:
    result = bilinear_resample_elevation(
        [[0.0, 10.0], [20.0, 30.0]],
        [0.0, 10.0],
        [0.0, 10.0],
        [0.0, 5.0, 10.0],
        [0.0, 5.0, 10.0],
        source_uncertainty_m=3.5,
    )
    assert result.elevation_m[1, 1] == 15.0
    assert result.source_uncertainty_m == 3.5


def test_rainfall_remap_conserves_area_integrated_volume() -> None:
    source = np.array([[[12.0, 35.0], [4.0, 20.0]]], dtype=np.float64)
    remap = conservative_remap_rainfall(
        source,
        [0.0, 100.0, 250.0],
        [0.0, 80.0, 200.0],
        [0.0, 40.0, 100.0, 160.0, 250.0],
        [0.0, 50.0, 80.0, 140.0, 200.0],
        timestep_seconds=300.0,
        tolerance=1e-12,
    )
    before = rainfall_volume_m3(
        source,
        [0.0, 100.0, 250.0],
        [0.0, 80.0, 200.0],
        timestep_seconds=300.0,
    )
    assert remap.conservation.passed is True
    assert remap.conservation.volume_before_m3 == before
    assert abs(remap.conservation.volume_after_m3 - before) < 1e-12


def test_reference_rainfall_gate_passes_strict_tolerance() -> None:
    result = reference_rainfall_conservation_check(tolerance=1e-12)
    assert result.passed is True
    assert result.relative_error <= 1e-12
