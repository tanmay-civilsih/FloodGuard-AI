"""Hydrologic-loss and roof-runoff conservation calculations for Sequence 7."""
from __future__ import annotations

import math
from dataclasses import dataclass

from floodguard.urban_gis.contracts import HydrologicLossMode, SurfaceHydrologyPolicy


@dataclass(frozen=True, slots=True)
class RoofRunoffConservation:
    generated_volume_m3: float
    transferred_volume_m3: float
    relative_error: float
    tolerance: float
    passed: bool


def effective_rain_rate_mm_h(rain_rate_mm_h: float, policy: SurfaceHydrologyPolicy) -> float:
    if not math.isfinite(rain_rate_mm_h) or rain_rate_mm_h < 0:
        raise ValueError("rain rate must be finite and non-negative")
    if policy.loss_mode is HydrologicLossMode.SIMPLIFIED_RUNOFF:
        assert policy.runoff_coefficient is not None
        return policy.runoff_coefficient * rain_rate_mm_h
    assert policy.infiltration_rate_mm_h is not None
    assert policy.other_loss_rate_mm_h is not None
    return max(0.0, rain_rate_mm_h - policy.infiltration_rate_mm_h - policy.other_loss_rate_mm_h)


def roof_generated_volume_m3(
    *,
    area_m2: float,
    rain_rate_mm_h: float,
    duration_s: float,
    policy: SurfaceHydrologyPolicy,
) -> float:
    for value, name in ((area_m2, "area"), (duration_s, "duration")):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    effective = effective_rain_rate_mm_h(rain_rate_mm_h, policy)
    return effective / 1000.0 / 3600.0 * area_m2 * duration_s


def check_roof_runoff_transfer(
    *,
    generated_volume_m3: float,
    transferred_volume_m3: float,
    relative_tolerance: float,
) -> RoofRunoffConservation:
    for value, name in (
        (generated_volume_m3, "generated volume"),
        (transferred_volume_m3, "transferred volume"),
        (relative_tolerance, "relative tolerance"),
    ):
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and non-negative")
    scale = max(generated_volume_m3, 1e-15)
    relative_error = abs(generated_volume_m3 - transferred_volume_m3) / scale
    return RoofRunoffConservation(
        generated_volume_m3=generated_volume_m3,
        transferred_volume_m3=transferred_volume_m3,
        relative_error=relative_error,
        tolerance=relative_tolerance,
        passed=relative_error <= relative_tolerance,
    )
