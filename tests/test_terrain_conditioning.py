import pytest

from floodguard.terrain.conditioning import condition_package
from floodguard.terrain.contracts import (
    TerrainIntervention,
    TerrainInterventionKind,
)
from tests.terrain_fixtures import synthetic_package


def test_conditioning_keeps_visual_source_and_applies_only_explicit_changes() -> None:
    package = synthetic_package()
    result = condition_package(package)

    assert result.visual.elevations_m == package.grid.elevations_m
    assert result.hydraulic.elevations_m[2][2] == 90.0
    assert result.hydraulic.elevations_m[0][0] == 101.0
    assert result.hydraulic.elevations_m[1][1] == 99.0
    assert result.preserved_depression_count == 1
    assert result.filled_artifact_count == 1
    assert result.removed_obstruction_count == 1
    assert result.max_adjustment_m == 2.0


def test_no_interventions_means_no_automatic_sink_filling_or_dsm_conversion() -> None:
    package = synthetic_package().model_copy(update={"interventions": []})
    result = condition_package(package)

    assert result.visual.elevations_m == package.grid.elevations_m
    assert result.hydraulic.elevations_m == package.grid.elevations_m
    assert result.preserved_depression_count == 0
    assert result.max_adjustment_m == 0.0


@pytest.mark.parametrize(
    ("kind", "target"),
    [
        (TerrainInterventionKind.FILL_DOCUMENTED_ARTIFACT, 99.0),
        (TerrainInterventionKind.REMOVE_DOCUMENTED_OBSTRUCTION, 101.0),
    ],
)
def test_conditioning_rejects_directionally_invalid_interventions(
    kind: TerrainInterventionKind,
    target: float,
) -> None:
    package = synthetic_package().model_copy(
        update={
            "interventions": [
                TerrainIntervention(
                    row=0,
                    column=0,
                    kind=kind,
                    target_elevation_m=target,
                    source_reference="qa://bad",
                    reason="The direction is invalid for this intervention kind.",
                )
            ]
        }
    )
    with pytest.raises(ValueError, match="cannot"):
        condition_package(package)


def test_conditioning_rejects_unbounded_and_duplicate_interventions() -> None:
    package = synthetic_package().model_copy(
        update={
            "interventions": [
                TerrainIntervention(
                    row=0,
                    column=0,
                    kind=TerrainInterventionKind.FILL_DOCUMENTED_ARTIFACT,
                    target_elevation_m=120.0,
                    source_reference="qa://large",
                    reason="The test target exceeds the configured adjustment limit.",
                )
            ]
        }
    )
    with pytest.raises(ValueError, match="adjustment limit"):
        condition_package(package)

    duplicate = synthetic_package().model_copy(
        update={"interventions": [synthetic_package().interventions[0]] * 2}
    )
    with pytest.raises(ValueError, match="unique cells"):
        condition_package(duplicate)
