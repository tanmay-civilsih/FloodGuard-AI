import pytest

from floodguard.urban_gis.contracts import SurfaceHydrologyPolicy
from floodguard.urban_gis.policy import (
    check_roof_runoff_transfer,
    effective_rain_rate_mm_h,
    roof_generated_volume_m3,
)


def test_simplified_runoff_and_volume_conservation() -> None:
    policy = SurfaceHydrologyPolicy(
        loss_mode="SIMPLIFIED_RUNOFF",
        parameter_status="ASSUMED",
        source_reference="fixture://roof-policy",
        runoff_coefficient=0.8,
    )
    assert effective_rain_rate_mm_h(10.0, policy) == 8.0
    generated = roof_generated_volume_m3(
        area_m2=100.0,
        rain_rate_mm_h=10.0,
        duration_s=3600.0,
        policy=policy,
    )
    assert generated == pytest.approx(0.8)
    assert check_roof_runoff_transfer(
        generated_volume_m3=generated,
        transferred_volume_m3=generated,
        relative_tolerance=1e-9,
    ).passed


def test_explicit_losses_never_create_negative_effective_rain() -> None:
    policy = SurfaceHydrologyPolicy(
        loss_mode="EXPLICIT_LOSS",
        parameter_status="ASSUMED",
        source_reference="fixture://soil-policy",
        infiltration_rate_mm_h=8.0,
        other_loss_rate_mm_h=4.0,
    )
    assert effective_rain_rate_mm_h(10.0, policy) == 0.0


def test_roof_conservation_detects_unaccounted_volume() -> None:
    result = check_roof_runoff_transfer(
        generated_volume_m3=1.0,
        transferred_volume_m3=0.99,
        relative_tolerance=1e-6,
    )
    assert not result.passed
