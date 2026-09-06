import json

import pytest

from floodguard.drainage.contracts import DrainEvidenceScope
from floodguard.drainage.serialization import canonical_bytes
from floodguard.twin.bootstrap import pilot_request
from floodguard.twin.contracts import ComponentRole as R
from floodguard.twin.contracts import TwinBuildRequest
from floodguard.twin.reference import reference_snapshot
from floodguard.twin.snapshot import evaluate
from tests.twin_fixtures import bound_fixture_snapshot


def replace(snapshot, role, edit):
    data = json.loads(snapshot.components[role])
    edit(data)
    snapshot.add(role, canonical_bytes(data), snapshot.sources[role])


def test_aligned_reference_has_no_scenario_gaps_but_no_real_claim() -> None:
    assert evaluate(reference_snapshot()) == ([], True, False)


@pytest.mark.parametrize("role", [R.VISUAL_CITY, R.WATERBODY, R.PARAMETERS, R.CATCHMENT])
def test_missing_components_remain_explicit_scenario_blockers(role) -> None:
    s = reference_snapshot()
    del s.components[role], s.sources[role]
    s.missing[role] = "Not yet constructed"
    blockers, _, _ = evaluate(s)
    assert any(role.value in b for b in blockers)


@pytest.mark.parametrize(
    "case", ["datum", "terrain_not_ready", "nodata", "terrain_coverage", "pilot_coverage"]
)
def test_readiness_not_inflated_by_component_labels(case) -> None:
    s = reference_snapshot()
    if case == "datum":
        for role in (R.VISUAL_TERRAIN, R.HYDRAULIC_TERRAIN):
            replace(s, role, lambda d: d.update(vertical_datum="OTHER_DATUM"))
    elif case == "terrain_not_ready":
        s.evidence["terrain-metadata"] = canonical_bytes({"readiness_status": "VISUAL_READY"})
    elif case == "nodata":
        replace(s, R.HYDRAULIC_TERRAIN, lambda d: d["grid"]["elevations_m"][0].__setitem__(0, None))
    elif case == "terrain_coverage":
        replace(s, R.HYDRAULIC_TERRAIN, lambda d: d["grid"].update(origin_x_m=0))
    else:
        s.pilot_area.geometry["coordinates"][0][1][0] -= 20
        s.pilot_area.geometry["coordinates"][0][2][0] -= 20
    assert evaluate(s)[0]


@pytest.mark.parametrize(
    "case",
    [
        "crs",
        "scope",
        "ward",
        "drain_identity",
        "exchanges",
        "pumps",
        "parameter_set",
        "roof_target",
        "roof_count",
        "source_hash",
        "source_version",
    ],
)
def test_incompatible_or_unbound_components_rejected(case) -> None:
    s = reference_snapshot()
    if case == "crs":
        replace(s, R.HYDRAULIC_TERRAIN, lambda d: d["grid"].update(crs="EPSG:32644"))
    elif case == "scope":
        s.sources[R.WARD].evidence_scope = DrainEvidenceScope.REAL_PILOT_PROVISIONAL
    elif case == "ward":
        replace(s, R.WARD, lambda d: d["features"][0]["properties"].update(WARD="fake"))
    elif case == "drain_identity":
        replace(s, R.DRAIN_GRAPH, lambda d: d.update(city_id="other"))
    elif case == "exchanges":
        replace(s, R.EXCHANGE, lambda d: d.update(exchanges=[]))
    elif case == "pumps":
        replace(s, R.PUMP, lambda d: d.update(pumps=[]))
    elif case == "parameter_set":
        replace(s, R.PARAMETERS, lambda d: d.update(surface_hydrology=[]))
    elif case == "roof_target":
        replace(
            s,
            R.ROOF_RUNOFF,
            lambda d: d["rules"][0].update(
                target_kind="EXPLICIT_DRAIN_TARGET",
                receiving_geometry=None,
                explicit_drain_target="missing",
            ),
        )
    elif case == "roof_count":
        replace(s, R.ROOF_RUNOFF, lambda d: d.update(rules=[]))
    elif case == "source_hash":
        s.sources[R.WARD].source_sha256 = "b" * 64
    else:
        s.sources[R.EXCHANGE].product_id = "other"
    with pytest.raises(ValueError):
        evaluate(s)


def test_missing_selection_requires_reason_and_no_latest_defaults() -> None:
    request = pilot_request().model_dump(mode="json")
    request["missing_reasons"] = {}
    with pytest.raises(ValueError, match="urban_gis"):
        TwinBuildRequest.model_validate(request)
    request = pilot_request().model_dump(mode="json")
    request["missing_reasons"]["terrain"] = "absent"
    with pytest.raises(ValueError, match="selected terrain"):
        TwinBuildRequest.model_validate(request)


def test_provisional_cross_ward_requires_recreation_from_actual_bound_bytes() -> None:
    # This is a synthetic test of the source-binding mechanism, not Kolkata gate evidence.
    snapshot = bound_fixture_snapshot()
    blockers, compatible, cross = evaluate(snapshot)
    assert not blockers and compatible and cross
    snapshot.evidence["drain-source-reconstruction"] += b"altered"
    with pytest.raises(ValueError, match="SHA-256"):
        evaluate(snapshot)


def test_parameter_artifact_cannot_disagree_with_the_selected_graph() -> None:
    snapshot = reference_snapshot()
    parameters = json.loads(snapshot.evidence["drain-parameters"])
    parameters["nodes"][0]["invert_elevation"]["value"] = 100
    snapshot.evidence["drain-parameters"] = canonical_bytes(parameters)
    with pytest.raises(ValueError, match="parameter artifact"):
        evaluate(snapshot)
