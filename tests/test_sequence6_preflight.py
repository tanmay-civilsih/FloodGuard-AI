"""Synthetic policy tests never approve a real map or freeze a release."""

from copy import deepcopy

import pytest

from scripts.sequence6_preflight import (
    MANUAL_ACCEPTANCE,
    select_product,
    terrain_blockers,
    validate_base_url,
)

PILOT = "kolkata-ward-7"
PIPELINE = "sequence-6-terrain-v7"
TERRAIN_ID = "11111111-1111-4111-8111-111111111111"


def evidence():
    product = {"pilot_area_id": PILOT, "pipeline_version": PIPELINE, "terrain_id": TERRAIN_ID,
               "created_at": "2026-09-06T00:00:00+00:00",
               "readiness_status": "HYDRAULIC_SCENARIO_READY"}
    plan = {"pilot_area_id": PILOT, "boundary_reference": "test://fixture-only-boundary"}
    assessment = {"reviewed_by": "Synthetic fixture reviewer",
                  "reviewed_at": "2026-09-06T00:00:00+00:00",
                  "vertical_reference_evidence": "Synthetic fixture, not survey evidence",
                  "surface_use_evidence": "Synthetic fixture, not survey evidence",
                  "depression_evidence": "Synthetic fixture, not survey evidence",
                  "multi_level_evidence": "Synthetic fixture, not survey evidence",
                  "depression_assessment": "CONFIRMED_NONE",
                  "multi_level_assessment": "CONFIRMED_NONE",
                  "datum_transform_status": "COMPATIBLE", "local_vertical_datum": "EGM96"}
    audit = {"terrain_id": TERRAIN_ID, "pipeline_version": PIPELINE,
             "readiness_status": "HYDRAULIC_SCENARIO_READY",
             "derivation": {"boundary_reference": plan["boundary_reference"]},
             "terrain_assessment": assessment}
    return product, audit, plan


def test_synthetic_consistency_does_not_remove_human_acceptance() -> None:
    product, audit, plan = evidence()
    assert terrain_blockers(product, audit, plan) == []
    assert len(MANUAL_ACCEPTANCE) == 4


@pytest.mark.parametrize("field", ["pilot_area_id", "pipeline_version"])
def test_other_pilot_or_historical_policy_cannot_pass(field: str) -> None:
    product, _, _ = evidence()
    product[field] = "other"
    assert select_product([product], pilot=PILOT, pipeline=PIPELINE) is None


def test_latest_low_readiness_is_not_replaced_with_older_best_case() -> None:
    old, audit, plan = evidence()
    new = deepcopy(old)
    new["created_at"] = "2026-09-06T01:00:00+00:00"
    new["readiness_status"] = "VISUAL_READY"
    selected = select_product([old, new], pilot=PILOT, pipeline=PIPELINE)
    assert selected is new
    assert terrain_blockers(new, audit, plan)


def test_naive_inventory_timestamp_is_rejected() -> None:
    product, _, _ = evidence()
    product["created_at"] = "2026-09-06T00:00:00"
    with pytest.raises(ValueError, match="timezone"):
        select_product([product], pilot=PILOT, pipeline=PIPELINE)


def test_changed_approved_boundary_is_rejected() -> None:
    product, audit, plan = evidence()
    plan["boundary_reference"] = "test://different-reconstruction"
    messages = terrain_blockers(product, audit, plan)
    assert any("currently approved" in message for message in messages)


def test_missing_assessment_is_not_a_freeze() -> None:
    product, audit, plan = evidence()
    del audit["terrain_assessment"]
    messages = terrain_blockers(product, audit, plan)
    assert any("assessment is missing" in message for message in messages)


@pytest.mark.parametrize("field", ["reviewed_by", "reviewed_at", "vertical_reference_evidence",
                                  "surface_use_evidence", "depression_evidence",
                                  "multi_level_evidence"])
def test_empty_evidence_is_a_blocker(field: str) -> None:
    product, audit, plan = evidence()
    audit["terrain_assessment"][field] = " "
    assert terrain_blockers(product, audit, plan)


def test_unresolved_datum_is_a_blocker() -> None:
    product, audit, plan = evidence()
    audit["terrain_assessment"]["datum_transform_status"] = "UNRESOLVED"
    assert terrain_blockers(product, audit, plan)


@pytest.mark.parametrize("url", ["file:///tmp/test", "http://user:pass@localhost:8000",
                                "http://localhost:8000/other",
                                "http://localhost:8000?token=private"])
def test_base_url_does_not_accept_credentials_paths_or_non_http(url: str) -> None:
    with pytest.raises(ValueError):
        validate_base_url(url)


def test_plain_api_origin_is_supported() -> None:
    assert validate_base_url("http://localhost:8000/") == "http://localhost:8000"
