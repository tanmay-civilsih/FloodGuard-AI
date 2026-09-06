"""Exact twin binding, no-extrapolation time series and independent coverage assessment."""

from __future__ import annotations

import itertools
import math
from bisect import bisect_right
from datetime import datetime
from typing import Any

from shapely.geometry import box, shape  # type: ignore[import-untyped]

from floodguard.drainage.model_contracts import DrainModelInput, HydraulicReadiness
from floodguard.drainage.serialization import canonical_bytes
from floodguard.forcing.contracts import (
    Assessment,
    BoundarySeries,
    BuildRequest,
    ControlSeries,
    Coverage,
    ForcingWindow,
    Mode,
)
from floodguard.forcing.rain import RemappedRain, remap, zarr_bytes
from floodguard.twin.contracts import ComponentRole, TwinManifest
from floodguard.twin.snapshot import object_data


def interpolate(times: list[datetime], values: list[float], when: datetime, method: str) -> float:
    if method not in {"LINEAR", "STEP_HOLD"}:
        raise ValueError("unsupported interpolation")
    if not times or len(times) != len(values) or any(b <= a for a, b in itertools.pairwise(times)):
        raise ValueError("invalid interpolation series")
    if not all(math.isfinite(value) for value in values):
        raise ValueError("interpolation values must be finite")
    if when < times[0] or when > times[-1]:
        raise ValueError("temporal extrapolation is forbidden")
    i = bisect_right(times, when) - 1
    if method == "STEP_HOLD" or i == len(times) - 1:
        return values[i]
    weight = (when - times[i]).total_seconds() / (times[i + 1] - times[i]).total_seconds()
    return values[i] * (1 - weight) + values[i + 1] * weight


def normalized_stage(series: BoundarySeries, datum: str | None) -> list[float]:
    if datum is None or series.vertical_transform_status == "UNRESOLVED":
        raise ValueError("hydraulic boundary vertical reference is unresolved")
    if series.vertical_transform_status == "COMPATIBLE":
        if series.vertical_datum != datum:
            raise ValueError("hydraulic boundary datum differs from active twin")
        return list(series.stage_m)
    if series.target_vertical_datum != datum or series.vertical_offset_m is None:
        raise ValueError("boundary transform does not target active twin datum")
    values = [s + series.vertical_offset_m for s in series.stage_m]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("normalized stage exceeds finite numerical range")
    return values


def control_at(series: ControlSeries, when: datetime) -> tuple[str, float]:
    """Continuous values may interpolate; discrete operating states always hold at knots."""
    series = ControlSeries.model_validate_json(series.model_dump_json())
    value = interpolate(series.time, series.control_value, when, series.interpolation_method)
    state = series.operating_state[bisect_right(series.time, when) - 1]
    if state in {"OFF", "UNAVAILABLE", "CLOSED"}:
        value = 0.0
    return state, value


def window_assessment(
    window: ForcingWindow,
    start: datetime,
    end: datetime,
    model: DrainModelInput | None,
    datum: str | None,
) -> tuple[Coverage, datetime | None, datetime | None, list[str], dict[str, Any]]:
    blockers = []
    boundaries = {b.boundary_id: b for b in window.boundaries}
    controls = {c.asset_id: c for c in window.controls}
    required_boundaries: set[str] = set()
    required_controls: set[str] = set()
    if model is None:
        blockers.append(
            "Exact twin lacks drainage definitions; required forcing cannot be established."
        )
        if boundaries or controls:
            raise ValueError("cannot bind hydraulic series to a twin without drainage definitions")
    else:
        outfalls = {o.drain_node_id for o in model.definitions.outfalls}
        required_boundaries = {
            o.drain_node_id for o in model.definitions.outfalls if o.boundary_type == "FIXED_STAGE"
        }
        required_controls = {p.drain_node_id for p in model.definitions.pumps}
        if set(boundaries) - outfalls:
            raise ValueError("boundary ID does not belong to the exact twin outfalls")
        if set(controls) - required_controls or any(
            c.asset_kind != "PUMP" for c in controls.values()
        ):
            raise ValueError(
                "control asset is absent from twin; gate/sluice static adapters unavailable"
            )
    missing = required_boundaries - set(boundaries)
    missing_controls = required_controls - set(controls)
    blockers.extend(f"Missing required boundary: {name}" for name in sorted(missing))
    blockers.extend(f"Missing required control: {name}" for name in sorted(missing_controls))
    normalized = {}
    for name, boundary in boundaries.items():
        normalized[name] = {
            **boundary.model_dump(mode="json"),
            "normalized_stage_m": normalized_stage(boundary, datum),
            "normalized_vertical_datum": datum,
        }
    spans = [(window.rain.time_edges[0], window.rain.time_edges[-1])]
    spans.extend((b.time[0], b.time[-1]) for b in boundaries.values())
    spans.extend((c.time[0], c.time[-1]) for c in controls.values())
    low = max(start, *(a for a, _ in spans))
    high = min(end, *(b for _, b in spans))
    if low >= high or missing or missing_controls or model is None:
        coverage = Coverage.INSUFFICIENT
    elif low == start and high == end:
        coverage = Coverage.BLENDED if window.rain.mode is Mode.RADAR_NWP_BLEND else Coverage.FULL
    else:
        coverage = Coverage.PARTIAL
    if coverage in {Coverage.INSUFFICIENT, Coverage.PARTIAL}:
        blockers.append(f"Forcing horizon is {coverage.value}; no temporal extension is permitted.")
    return (
        coverage,
        low if low < high else None,
        high if low < high else None,
        blockers,
        {
            "boundaries": normalized,
            "controls": [c.model_dump(mode="json") for c in window.controls],
            "required_boundary_ids": sorted(required_boundaries),
            "required_control_ids": sorted(required_controls),
            "static_free_boundary_ids": sorted(
                {o.drain_node_id for o in model.definitions.outfalls if o.boundary_type == "FREE"}
                - set(boundaries)
            )
            if model
            else [],
        },
    )


def prepare(
    request: BuildRequest,
    manifest: TwinManifest,
    twin_artifacts: dict[str, bytes],
    *,
    encode: bool = True,
) -> tuple[Assessment, dict[str, bytes]]:
    if request.twin_id != manifest.twin_id:
        raise ValueError("forcing request must bind exact twin identity")
    grid = request.target_grid
    if grid.horizontal_crs != manifest.horizontal_crs:
        raise ValueError("forcing and twin CRS differ")
    footprint = box(grid.x_edges_m[0], grid.y_edges_m[0], grid.x_edges_m[-1], grid.y_edges_m[-1])
    if not footprint.covers(shape(manifest.pilot_area.geometry)):
        raise ValueError("rainfall grid does not cover the twin pilot")
    terrain = (
        object_data(twin_artifacts[ComponentRole.HYDRAULIC_TERRAIN.value])
        if (ComponentRole.HYDRAULIC_TERRAIN.value in twin_artifacts)
        else {}
    )
    datum = (
        terrain.get("vertical_datum")
        if manifest.vertical_reference_status == "COMPATIBLE"
        else None
    )
    model = None
    if "drain-input" in twin_artifacts:
        model = DrainModelInput.model_validate(object_data(twin_artifacts["drain-input"])["model"])
    coverage, low, high, blockers, dynamic = window_assessment(
        request.forecast,
        request.valid_from,
        request.valid_to,
        model,
        datum,
    )
    if manifest.hydraulic_readiness is not HydraulicReadiness.HYDRAULIC_SCENARIO_READY:
        blockers.append("Twin is not scenario-ready; hydraulic use is refused.")
    if manifest.vertical_reference_status != "COMPATIBLE":
        blockers.append("Twin vertical reference is unresolved; hydraulic use is refused.")
    artifacts = {"boundaries-and-controls.json": canonical_bytes(dynamic)}
    result: RemappedRain = remap(request.forecast.rain, grid)
    if encode:
        artifacts["rain.zarr.zip"] = zarr_bytes(request.forecast.rain, grid, result)
    antecedent_status = "MISSING"
    if request.antecedent is not None:
        ant = request.antecedent
        ant_coverage, _, _, ant_blockers, ant_dynamic = window_assessment(
            ant,
            ant.rain.time_edges[0],
            request.valid_from,
            model,
            datum,
        )
        ant_result = remap(ant.rain, grid)
        antecedent_status = "COMPLETE" if ant_coverage is Coverage.FULL else "INCOMPLETE"
        artifacts["antecedent.json"] = canonical_bytes(
            {
                "status": antecedent_status,
                "blockers": ant_blockers,
                **ant_dynamic,
                "valid_from": ant.rain.time_edges[0].isoformat(),
                "valid_to": ant.rain.time_edges[-1].isoformat(),
                "rainfall_volume_m3_by_member": ant_result.volumes,
            }
        )
        if encode:
            artifacts["antecedent-rain.zarr.zip"] = zarr_bytes(ant.rain, grid, ant_result)
    else:
        artifacts["antecedent.json"] = canonical_bytes(
            {
                "status": "MISSING",
                "reason": request.antecedent_missing_reason,
                "initial_state_policy": "No dry state inferred; Sequence 14 owns initialization.",
            }
        )
    assessment = Assessment.model_validate(
        dict(
            coverage=coverage,
            common_valid_from=low,
            common_valid_to=high,
            hydraulic_use_eligible=not blockers,
            blockers=blockers,
            antecedent_status=antecedent_status,
            rainfall_volume_m3_by_member=result.volumes,
            maximum_remap_relative_error=result.maximum_relative_error,
        )
    )
    return assessment, artifacts
