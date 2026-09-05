"""Explicit terrain conditioning; no automatic sink filling or DSM-to-DTM conversion."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from floodguard.terrain.contracts import (
    TerrainGrid,
    TerrainInterventionKind,
    TerrainPackage,
)
from floodguard.terrain.grid import grid_array, grid_from_array


@dataclass(frozen=True, slots=True)
class ConditioningResult:
    visual: TerrainGrid
    hydraulic: TerrainGrid
    preserved_depression_count: int
    filled_artifact_count: int
    removed_obstruction_count: int
    max_adjustment_m: float


def condition_package(package: TerrainPackage) -> ConditioningResult:
    """Apply only cell-level interventions explicitly documented in the package.

    Genuine depressions are preserved by default.  A DSM remains a DSM in the
    visual product and is lowered only at cells carrying a documented
    ``REMOVE_DOCUMENTED_OBSTRUCTION`` intervention.
    """
    source = grid_array(package.grid)
    visual = source.copy()
    hydraulic = source.copy()
    seen: set[tuple[int, int]] = set()
    preserved = 0
    filled = 0
    removed = 0
    maximum_adjustment = 0.0
    for intervention in package.interventions:
        location = (intervention.row, intervention.column)
        if location in seen:
            raise ValueError("terrain interventions must address unique cells")
        seen.add(location)
        row, column = location
        if row >= package.grid.height or column >= package.grid.width:
            raise ValueError("terrain intervention lies outside the source grid")
        current = hydraulic[row, column]
        if not np.isfinite(current):
            raise ValueError("terrain interventions cannot target a nodata cell")
        if intervention.kind is TerrainInterventionKind.PRESERVE_DEPRESSION:
            preserved += 1
            continue
        target = intervention.target_elevation_m
        if target is None:
            raise ValueError("conditioning intervention target is required")
        adjustment = float(target - current)
        if abs(adjustment) > package.max_conditioning_adjustment_m:
            raise ValueError("terrain intervention exceeds the configured adjustment limit")
        if (
            intervention.kind is TerrainInterventionKind.FILL_DOCUMENTED_ARTIFACT
            and adjustment < 0
        ):
            raise ValueError("fill intervention cannot lower terrain")
        if (
            intervention.kind is TerrainInterventionKind.REMOVE_DOCUMENTED_OBSTRUCTION
            and adjustment > 0
        ):
            raise ValueError("obstruction removal cannot raise terrain")
        hydraulic[row, column] = float(target)
        maximum_adjustment = max(maximum_adjustment, abs(adjustment))
        if intervention.kind is TerrainInterventionKind.FILL_DOCUMENTED_ARTIFACT:
            filled += 1
        else:
            removed += 1
    return ConditioningResult(
        visual=grid_from_array(package.grid, visual),
        hydraulic=grid_from_array(package.grid, hydraulic),
        preserved_depression_count=preserved,
        filled_artifact_count=filled,
        removed_obstruction_count=removed,
        max_adjustment_m=maximum_adjustment,
    )
